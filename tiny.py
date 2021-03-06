"""A simple search engine in python."""

import re, pathlib, collections, array, struct, csv, math


# === Phase 1: Split text into words

def words(text):
    return re.findall(r"\w+", text.lower())


# === Phase 2: Create an index

Document = collections.namedtuple("Document", "filename size")
Hit = collections.namedtuple("Hit", "doc_id offsets")


def make_index(dir):
    dir = pathlib.Path(dir)
    tiny_dir = dir / ".tiny"
    tiny_dir.mkdir(exist_ok=True)

    # Build the index in memory.
    documents = []
    index = collections.defaultdict(list)  # {str: [Hit]}
    terms = {}  # {str: (int, int)}

    for path in dir.glob("**/*.txt"):
        text = path.read_text()
        doc_words = words(text)
        doc = Document(path.relative_to(dir), len(doc_words))
        doc_id = len(documents)
        documents.append(doc)

        # Build an index for this one document.
        doc_index = collections.defaultdict(
            lambda: Hit(doc_id, array.array('I')))
        for i, word in enumerate(words(text)):
            doc_index[word].offsets.append(i)

        # Merge that into the big index.
        for word, hit in doc_index.items():
            index[word].append(hit)

    # Save the document list.
    with open(tiny_dir / "documents.csv", 'w') as f:
        out = csv.writer(f)
        for doc in documents:
            out.writerow(doc)

    # Save the index itself.
    with open(tiny_dir / "index.dat", 'wb') as f:
        start = 0
        for word, hits in index.items():
            bytes = b""
            for hit in hits:
                bytes += struct.pack("=II",
                                     hit.doc_id,
                                     len(hit.offsets))
                bytes += hit.offsets.tobytes()
            f.write(bytes)
            terms[word] = (start, len(bytes))
            start += len(bytes)

    # Save the table of terms.
    with open(tiny_dir / "terms.csv", 'w') as f:
        out = csv.writer(f)
        for word, (start, length) in terms.items():
            out.writerow([word, start, length])


# === Phase 3: Querying the index

class Index:
    """Class for reading a .tiny index."""

    def __init__(self, dir):
        """Create an Index that reads `$DIR/.tiny`."""
        dir = pathlib.Path(dir)
        tiny_dir = dir / ".tiny"
        self.dir = dir
        self.index_file = tiny_dir / "index.dat"

        self.documents = []
        for [line, max_tf] in csv.reader(open(tiny_dir / "documents.csv")):
            self.documents.append(Document(pathlib.Path(line), int(max_tf)))

        self.terms = {}
        for word, start, length in csv.reader(open(tiny_dir / "terms.csv")):
            self.terms[word] = (int(start), int(length))

    def lookup(self, word):
        """Return a list of Hits for the given word."""
        if word not in self.terms:
            return []

        start, length = self.terms[word]
        with open(self.index_file, 'rb') as f:
            f.seek(start)
            bytes = f.read(length)

        read_pos = 0
        hits = []
        while read_pos < len(bytes):
            doc_id, hit_count = struct.unpack("=II", bytes[read_pos:read_pos+8])
            read_pos += 8
            offset_bytes = bytes[read_pos:read_pos + 4 * hit_count]
            read_pos += 4 * hit_count
            offsets = array.array('I')
            offsets.frombytes(offset_bytes)
            hits.append(Hit(doc_id, offsets))
        assert read_pos == len(bytes)
        return hits

    def search(self, query):
        """Find documents matching the given query.

        Return a list of (document, score) pairs."""
        scores = collections.defaultdict(float)

        for word in words(query):
            hits = self.lookup(word)
            if hits:
                df = len(hits) / len(self.documents)
                idf = math.log(1 / df)
                for hit in hits:
                    tf = 1000 * len(hit.offsets) / self.documents[hit.doc_id].size
                    scores[hit.doc_id] += tf * idf

        results = sorted(scores.items(),
                         key=lambda pair: pair[1],
                         reverse=True)
        return [(self.documents[doc_id].filename, score)
                for doc_id, score in results[:10]]


if __name__ == '__main__':
    import sys
    make_index(sys.argv[1])
