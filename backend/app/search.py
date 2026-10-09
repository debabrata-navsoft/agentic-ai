"""Document search written from scratch: chunking, a BM25 inverted index, and extractive answers.

No AI model or external service is involved. A query is matched against passages by word overlap,
weighted so rare words count more (BM25). The "answer" is the best-matching sentences quoted from
those passages, not newly generated text.
"""

import heapq
import logging
import math
import re
import threading
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from operator import itemgetter
from pathlib import Path

log = logging.getLogger(__name__)

SUFFIXES = {".txt", ".md", ".pdf"}
CHUNK_CHARS = 800

STOPWORDS = set(
    """a an and are as at be but by for from has have he her his i if in into is it its me my no not
    of on or our she so than that the their them then there these they this to was we were what when
    where which who whom why will with would you your do does did can could should shall how about all
    any been being had just more most other over own same some such only very also""".split()
)


def stem(word: str) -> str:
    """A deliberately tiny stemmer so 'kings' matches 'king' and 'loved' matches 'love'."""
    if len(word) <= 4 or word.endswith("ss"):
        return word
    if word.endswith("ies"):
        return word[:-3] + "y"
    if word.endswith(("ches", "shes", "xes", "zes", "sses")):
        return word[:-2]
    for suffix in ("ing", "ed", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


def words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOPWORDS]


def tokenize(text: str) -> list[str]:
    return [stem(w) for w in words(text)]


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if len(s.strip()) > 2]


def chunk(text: str, size: int = CHUNK_CHARS) -> list[str]:
    """Group paragraphs into passages of about `size` characters; split oversized paragraphs by sentence."""
    chunks, current = [], ""
    for para in filter(None, (p.strip() for p in re.split(r"\n\s*\n", text))):
        for piece in [para] if len(para) <= size else split_sentences(para):
            if current and len(current) + len(piece) > size:
                chunks.append(current)
                current = ""
            current = f"{current}\n\n{piece}" if current else piece
    return chunks + [current] if current else chunks


def read_document(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader

        return "\n\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    return path.read_text(encoding="utf-8", errors="replace")


@dataclass(frozen=True)
class Passage:
    doc: str
    index: int
    text: str
    tf: Counter = field(init=False, compare=False, repr=False)  # term counts, computed once per passage

    def __post_init__(self):
        object.__setattr__(self, "tf", Counter(tokenize(self.text)))


class Index:
    """An immutable BM25 index over passages. Rebuild to change it; readers never see partial state."""

    K1, B = 1.5, 0.75

    def __init__(self, passages: list[Passage]):
        self.passages = passages
        self.postings: dict[str, list[tuple[int, int]]] = defaultdict(list)  # term -> [(passage, tf)]
        lengths = [p.tf.total() for p in passages]
        for i, p in enumerate(passages):
            for term, tf in p.tf.items():
                self.postings[term].append((i, tf))
        avg = sum(lengths) / len(lengths) if lengths else 1.0
        # The length-normalisation part of BM25 depends only on the passage, so precompute it.
        self.norm = [self.K1 * (1 - self.B + self.B * n / avg) for n in lengths]

    def idf(self, term: str) -> float:
        n, df = len(self.passages), len(self.postings.get(term, ()))
        return math.log(1 + (n - df + 0.5) / (df + 0.5))

    def search(self, query: str, k: int = 5) -> list[tuple[Passage, float]]:
        scores: dict[int, float] = defaultdict(float)
        for term in set(tokenize(query)):
            idf = self.idf(term)
            for i, tf in self.postings.get(term, ()):
                scores[i] += idf * tf * (self.K1 + 1) / (tf + self.norm[i])
        return [(self.passages[i], s) for i, s in heapq.nlargest(k, scores.items(), key=itemgetter(1))]

    def answer(self, query: str, hits: list[tuple[Passage, float]], max_sentences: int = 2) -> str:
        """Quote the sentences from the top passages that cover the most (and rarest) query terms."""
        terms = set(tokenize(query))
        best: dict[str, tuple] = {}  # keyed by sentence, so a line repeated across passages is quoted once
        for rank, (passage, _) in enumerate(hits[:3]):
            for pos, sentence in enumerate(split_sentences(passage.text)):
                if sentence not in best and (matched := terms & set(tokenize(sentence))):
                    best[sentence] = (sum(map(self.idf, matched)) - 0.1 * rank, rank, pos)
        top = heapq.nlargest(max_sentences, best.items(), key=lambda kv: kv[1])
        return " ".join(s for s, _ in sorted(top, key=lambda kv: kv[1][1:]))


class DocumentStore:
    """Files on disk under `root`, plus the index built from them.

    Each search checks the folder's files (name, size, mtime), so files copied in by hand are picked up.
    Only new or changed files are re-parsed; unchanged ones reuse their cached passages.
    """

    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._files: dict[str, tuple[tuple[int, int], list[Passage]]] = {}  # name -> ((size, mtime), passages)
        self.index = Index([])
        self.refresh()

    def _parse(self, path: Path) -> list[Passage]:
        try:
            return [Passage(path.name, i, t) for i, t in enumerate(chunk(read_document(path)))]
        except Exception as e:  # a corrupt upload shouldn't break search for everything else
            log.warning("skipping %s: %s", path.name, e)
            return []

    def refresh(self) -> Index:
        """Return the current index, rebuilding it first if any file was added, removed or changed."""
        with self._lock:
            stamps = {
                f.name: (st.st_size, st.st_mtime_ns)
                for f in sorted(self.root.iterdir())
                if f.suffix.lower() in SUFFIXES and f.is_file() and (st := f.stat())
            }
            if stamps != {name: stamp for name, (stamp, _) in self._files.items()}:
                old = self._files
                self._files = {
                    name: old[name] if name in old and old[name][0] == stamp else (stamp, self._parse(self.root / name))
                    for name, stamp in stamps.items()
                }
                self.index = Index([p for _, passages in self._files.values() for p in passages])
            return self.index

    def documents(self) -> list[dict]:
        self.refresh()
        return [{"name": n, "size": stamp[0], "passages": len(ps)} for n, (stamp, ps) in self._files.items()]

    def add(self, name: str, data: bytes) -> str:
        safe = Path(name).name
        if Path(safe).suffix.lower() not in SUFFIXES:
            raise ValueError(f"Only {', '.join(sorted(SUFFIXES))} files are supported.")
        (self.root / safe).write_bytes(data)
        return safe

    def delete(self, name: str) -> bool:
        path = self.root / Path(name).name
        if not path.is_file():
            return False
        path.unlink()
        return True

    def search(self, query: str, k: int = 5) -> dict:
        index = self.refresh()  # one snapshot for the whole request
        hits = index.search(query, k)
        return {
            "query": query,
            "terms": sorted(set(words(query))),
            "answer": index.answer(query, hits),
            "results": [{"doc": p.doc, "passage": p.index, "text": p.text, "score": round(s, 3)} for p, s in hits],
            "searched_passages": len(index.passages),
        }
