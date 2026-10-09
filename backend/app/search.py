"""Document search written from scratch: chunking, a BM25 inverted index, and extractive answers.

No AI model or external service is involved. A query is matched against passages by word overlap,
weighted so rare words count more (BM25). The "answer" is the best-matching sentences quoted from
those passages, not newly generated text.
"""

import logging
import math
import re
import threading
from collections import Counter, defaultdict
from dataclasses import dataclass
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


def tokenize(text: str) -> list[str]:
    return [stem(w) for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOPWORDS]


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if len(s.strip()) > 2]


def chunk(text: str, size: int = CHUNK_CHARS) -> list[str]:
    """Group paragraphs into passages of about `size` characters; split oversized paragraphs by sentence."""
    pieces: list[str] = []
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para:
            continue
        if len(para) <= size:
            pieces.append(para)
        else:
            pieces.extend(split_sentences(para))

    chunks, current = [], ""
    for piece in pieces:
        if current and len(current) + len(piece) > size:
            chunks.append(current)
            current = ""
        current = f"{current}\n\n{piece}" if current else piece
    if current:
        chunks.append(current)
    return chunks


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


class Index:
    """An immutable BM25 index over passages. Rebuild to change it; readers never see partial state."""

    K1, B = 1.5, 0.75

    def __init__(self, passages: list[Passage]):
        self.passages = passages
        self.postings: dict[str, list[tuple[int, int]]] = defaultdict(list)  # term -> [(passage, tf)]
        self.lengths = []
        for i, p in enumerate(passages):
            terms = tokenize(p.text)
            self.lengths.append(len(terms))
            for term, tf in Counter(terms).items():
                self.postings[term].append((i, tf))
        self.avg_len = sum(self.lengths) / len(self.lengths) if self.lengths else 0.0

    def idf(self, term: str) -> float:
        n, df = len(self.passages), len(self.postings.get(term, ()))
        return math.log(1 + (n - df + 0.5) / (df + 0.5))

    def search(self, query: str, k: int = 5) -> list[tuple[Passage, float]]:
        scores: dict[int, float] = defaultdict(float)
        for term in set(tokenize(query)):
            idf = self.idf(term)
            for i, tf in self.postings.get(term, ()):
                norm = 1 - self.B + self.B * self.lengths[i] / self.avg_len
                scores[i] += idf * tf * (self.K1 + 1) / (tf + self.K1 * norm)
        best = sorted(scores.items(), key=lambda s: s[1], reverse=True)[:k]
        return [(self.passages[i], score) for i, score in best]

    def answer(self, query: str, hits: list[tuple[Passage, float]], max_sentences: int = 2) -> str:
        """Quote the sentences from the top passages that cover the most (and rarest) query terms."""
        terms = set(tokenize(query))
        scored = []
        for rank, (passage, _) in enumerate(hits[:3]):
            for pos, sentence in enumerate(split_sentences(passage.text)):
                matched = terms & set(tokenize(sentence))
                if matched:
                    score = sum(self.idf(t) for t in matched) - 0.1 * rank
                    scored.append((score, rank, pos, sentence))
        top = sorted(scored, reverse=True)[:max_sentences]
        return " ".join(s for *_, s in sorted(top, key=lambda t: (t[1], t[2])))


class DocumentStore:
    """Files on disk under `root`, plus the index built from them.

    The index is rebuilt whenever the folder's files change, including files copied in by hand.
    """

    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._signature: tuple = ()
        self.index = Index([])
        self.refresh()

    def _files(self) -> list[Path]:
        return sorted(f for f in self.root.iterdir() if f.is_file() and f.suffix.lower() in SUFFIXES)

    def refresh(self) -> Index:
        """Return the current index, rebuilding it first if any file was added, removed or changed."""
        with self._lock:
            files = self._files()
            signature = tuple((f.name, f.stat().st_size, f.stat().st_mtime_ns) for f in files)
            if signature != self._signature:
                passages = []
                for f in files:
                    try:
                        text = read_document(f)
                    except Exception as e:  # a corrupt upload shouldn't break search for everything else
                        log.warning("skipping %s: %s", f.name, e)
                        continue
                    passages += [Passage(f.name, i, t) for i, t in enumerate(chunk(text))]
                self.index, self._signature = Index(passages), signature
            return self.index

    def documents(self) -> list[dict]:
        counts = Counter(p.doc for p in self.refresh().passages)
        return [
            {"name": f.name, "size": f.stat().st_size, "passages": counts.get(f.name, 0)} for f in self._files()
        ]

    def add(self, name: str, data: bytes) -> str:
        safe = Path(name).name
        if Path(safe).suffix.lower() not in SUFFIXES:
            raise ValueError(f"Only {', '.join(sorted(SUFFIXES))} files are supported.")
        (self.root / safe).write_bytes(data)
        self.refresh()
        return safe

    def delete(self, name: str) -> bool:
        path = self.root / Path(name).name
        if not path.is_file():
            return False
        path.unlink()
        self.refresh()
        return True

    def search(self, query: str, k: int = 5) -> dict:
        index = self.refresh()  # one snapshot for the whole request
        hits = index.search(query, k)
        return {
            "query": query,
            "terms": sorted({w for w in re.findall(r"[a-z0-9]+", query.lower()) if w not in STOPWORDS}),
            "answer": index.answer(query, hits),
            "results": [{"doc": p.doc, "passage": p.index, "text": p.text, "score": round(s, 3)} for p, s in hits],
            "searched_passages": len(index.passages),
        }
