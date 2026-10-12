import json
import re
from pathlib import Path
from collections import Counter
from math import log

ROOT = Path(__file__).resolve().parent.parent
TRANSCRIPTS_DIR = ROOT / "data" / "transcripts"
INDEX_PATH = ROOT / "data" / "transcript_index.json"


def tokenize(text):
    return re.findall(r"[a-z0-9']+", text.lower())


def chunk_text(text, chunk_size=900, overlap=150):
    text = re.sub(r"\s+", " ", text).strip()
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = end - overlap
    return chunks


def build_index():
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    records = []
    files = list(TRANSCRIPTS_DIR.glob("*.txt"))

    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        episode = path.stem.replace("_", " ").replace("-", " ")
        for number, chunk in enumerate(chunk_text(text)):
            records.append({
                "episode": episode,
                "source": path.name,
                "chunk": number,
                "text": chunk,
                "terms": dict(Counter(tokenize(chunk))),
            })

    INDEX_PATH.write_text(
        json.dumps(records, ensure_ascii=False), encoding="utf-8"
    )
    return {"indexed_files": len(files), "chunks": len(records)}


def search_transcripts(query, top_k=4):
    if not INDEX_PATH.exists():
        return []

    records = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    query_terms = set(tokenize(query))
    if not records or not query_terms:
        return []

    doc_frequency = Counter()
    for record in records:
        doc_frequency.update(set(record.get("terms", {})))

    total = len(records)
    results = []

    for record in records:
        terms = record.get("terms") or dict(Counter(tokenize(record["text"])))
        score = 0.0
        for term in query_terms:
            frequency = terms.get(term, 0)
            if frequency:
                score += (1 + log(frequency)) * log(
                    1 + total / (1 + doc_frequency[term])
                )

        if score > 0:
            results.append({
                "episode": record["episode"],
                "source": record["source"],
                "text": record["text"],
                "score": round(score, 3),
            })

    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:top_k]
