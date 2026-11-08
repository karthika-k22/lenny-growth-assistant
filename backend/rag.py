import json
import re
from pathlib import Path
from collections import Counter
from math import log

ROOT = Path(__file__).resolve().parent.parent

KNOWLEDGE_BASE_DIR = ROOT / "data" / "knowledge_base"
TRANSCRIPTS_DIR = ROOT / "data" / "transcripts"
INDEX_PATH = ROOT / "data" / "knowledge_index.json"

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200

SYNONYMS = {
    "prioritize": {"prioritization", "priority", "ranking"},
    "prioritization": {"prioritize", "priority", "ranking"},
    "churn": {"leaving", "dropout", "attrition"},
    "retention": {"returning", "repeat", "frequency", "loyalty"},
    "acquisition": {"attract", "attracting", "discovery", "traffic"},
    "conversion": {"purchase", "purchasing", "checkout"},
    "experimentation": {"experiment", "testing", "abtesting"},
    "experiment": {"experimentation", "testing", "abtesting"},
    "users": {"customers", "buyers", "people"},
    "customer": {"user", "buyer"},
    "growth": {"scaling", "expansion"},
    "marketplace": {"platform", "buyers", "sellers"},
    "referral": {"wordofmouth", "recommendation"},
    "northstar": {"north", "star", "primary", "metric"},
    "revenue": {"income", "sales", "monetization"},
}

STOP_WORDS = {
    "product", "products", "team", "teams", "work",
    "a", "an", "the", "is", "are", "was", "were",
    "be", "been", "being", "to", "of", "in", "on",
    "for", "and", "or", "but", "with", "by", "from",
    "at", "as", "it", "its", "this", "that", "these",
    "those", "how", "what", "why", "when", "where",
    "who", "which", "can", "could", "should", "would",
    "do", "does", "did", "we", "you", "they", "i",
    "our", "your", "their", "company",
}


def tokenize(text):
    return re.findall(r"[a-z0-9']+", text.lower())


def expand_query_terms(query):
    original_terms = set(tokenize(query)) - STOP_WORDS
    expanded_terms = set(original_terms)

    for term in original_terms:
        expanded_terms.update(SYNONYMS.get(term, set()))

    return original_terms, expanded_terms


def split_long_text(text, chunk_size, overlap):
    chunks = []
    start = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end].strip())

        if end == len(text):
            break

        start = end - overlap

    return chunks


def chunk_paragraphs(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    paragraphs = [
        paragraph.strip()
        for paragraph in re.split(r"\n\s*\n", text)
        if paragraph.strip()
    ]

    chunks = []
    current = ""

    for paragraph in paragraphs:
        if len(paragraph) > chunk_size:
            if current:
                chunks.append(current)
                current = ""

            chunks.extend(
                split_long_text(paragraph, chunk_size, overlap)
            )
            continue

        candidate = f"{current}\n\n{paragraph}" if current else paragraph

        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current:
                chunks.append(current)

            current = paragraph

    if current:
        chunks.append(current)

    return chunks


def chunk_markdown(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    lines = text.splitlines()
    sections = []
    current_heading = ""
    current_content = []

    for line in lines:
        if re.match(r"^\s{0,3}#{1,6}\s+", line):
            if current_content:
                sections.append((
                    current_heading,
                    "\n".join(current_content).strip()
                ))

            current_heading = line.strip()
            current_content = []
        else:
            current_content.append(line)

    if current_content:
        sections.append((
            current_heading,
            "\n".join(current_content).strip()
        ))

    chunks = []

    for heading, content in sections:
        if not content:
            continue

        section_text = f"{heading}\n{content}" if heading else content

        if len(section_text) <= chunk_size:
            chunks.append(section_text)
            continue

        paragraphs = chunk_paragraphs(
            content,
            chunk_size - len(heading),
            overlap
        )

        for paragraph in paragraphs:
            chunk = f"{heading}\n{paragraph}" if heading else paragraph
            chunks.append(chunk)

    return chunks


def get_source_files():
    files = []

    if KNOWLEDGE_BASE_DIR.exists():
        files.extend(KNOWLEDGE_BASE_DIR.glob("*.md"))

    if TRANSCRIPTS_DIR.exists():
        files.extend(TRANSCRIPTS_DIR.glob("*.txt"))

    return sorted(files)


def build_index():
    KNOWLEDGE_BASE_DIR.mkdir(parents=True, exist_ok=True)
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

    records = []
    files = get_source_files()

    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        episode = path.stem.replace("_", " ").replace("-", " ")

        if path.suffix.lower() == ".md":
            chunks = chunk_markdown(text)
        else:
            chunks = chunk_paragraphs(text)

        for number, chunk in enumerate(chunks):
            records.append({
                "episode": episode,
                "source": path.name,
                "chunk": number,
                "text": chunk,
                "terms": dict(Counter(tokenize(chunk))),
            })

    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)

    INDEX_PATH.write_text(
        json.dumps(records, ensure_ascii=False),
        encoding="utf-8",
    )

    return {
        "indexed_files": len(files),
        "chunks": len(records),
    }


def search_transcripts(query, top_k=4):
    if not INDEX_PATH.exists():
        return []

    if not isinstance(query, str) or not query.strip():
        return []

    if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k <= 0:
        return []

    records = json.loads(
        INDEX_PATH.read_text(encoding="utf-8")
    )

    original_terms, expanded_terms = expand_query_terms(query)

    if not records or not original_terms:
        return []

    doc_frequency = Counter()

    for record in records:
        doc_frequency.update(set(record.get("terms", {})))

    total = len(records)

    def score_records(search_query):
        query_terms, expanded = expand_query_terms(search_query)
        scored = []

        if not query_terms:
            return scored

        for record in records:
            terms = record.get("terms") or dict(
                Counter(tokenize(record["text"]))
            )

            score = 0.0

            for term in query_terms:
                frequency = terms.get(term, 0)

                if frequency:
                    score += 2.0 * (1 + log(frequency)) * log(
                        1 + total / (1 + doc_frequency[term])
                    )

            for term in expanded - query_terms:
                frequency = terms.get(term, 0)

                if frequency:
                    score += 0.5 * (1 + log(frequency)) * log(
                        1 + total / (1 + doc_frequency[term])
                    )

            matched_original = sum(
                1 for term in query_terms if terms.get(term, 0) > 0
            )

            score += 2.0 * matched_original / len(query_terms)

            if score > 0:
                scored.append({
                    "episode": record["episode"],
                    "source": record["source"],
                    "text": record["text"],
                    "score": round(score, 3),
                })

        scored.sort(
            key=lambda item: item["score"],
            reverse=True,
        )

        return scored

    topics = {
        "retention": {
            "retention", "churn", "loyalty", "frequency",
            "repeat", "returning",
        },
        "marketplace": {
            "marketplace", "supply", "demand", "buyers",
            "sellers", "seller", "buyer",
        },
        "acquisition": {
            "acquisition", "traffic", "discovery", "attract",
        },
        "conversion": {
            "conversion", "purchase", "purchasing", "checkout",
        },
        "experimentation": {
            "experimentation", "experiment", "testing",
            "abtesting",
        },
    }

    detected_topics = [
        topic
        for topic, keywords in topics.items()
        if original_terms.intersection(keywords)
    ]

    # Preserve original ranking for single-topic questions.
    if len(detected_topics) < 2:
        return score_records(query)[:top_k]

    topic_results = []

    for topic in detected_topics:
        topic_terms = original_terms.intersection(topics[topic])

        if topic == "marketplace" and {"supply", "demand"}.intersection(topic_terms):
            topic_terms.discard("marketplace")

        topic_query = " ".join(sorted(topic_terms))
        scored = score_records(topic_query)

        if scored:
            topic_results.append(scored)

    if not topic_results:
        return score_records(query)[:top_k]

    selected = []
    selected_keys = set()

    # First pass: retrieve one relevant result per topic.
    for scored in topic_results:
        for result in scored:
            key = (result["source"], result["text"])

            if key not in selected_keys:
                selected.append(result)
                selected_keys.add(key)
                break

    # Second pass: fill remaining slots from topic-specific results.
    for scored in topic_results:
        for result in scored:
            key = (result["source"], result["text"])

            if key not in selected_keys:
                selected.append(result)
                selected_keys.add(key)

            if len(selected) >= top_k:
                break

        if len(selected) >= top_k:
            break

    # Final fallback: use the original query ranking.
    if len(selected) < top_k:
        original_results = score_records(query)

        for result in original_results:
            key = (result["source"], result["text"])

            if key not in selected_keys:
                selected.append(result)
                selected_keys.add(key)

            if len(selected) >= top_k:
                break

    selected.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    return selected[:top_k]
