"""Lexical TF-IDF retrieval; no semantic vectors."""
import math
import re
from collections import Counter

STOPWORDS = set("the a an is are to of in on for and or how do i you we it what can please".split())


def tokenize(text):
    return [term for term in re.findall(r"[a-z0-9]+", text.lower()) if len(term) >= 2 and term not in STOPWORDS]


def search(index, query, top_k=3):
    chunks = index["chunks"]
    counts = [Counter(tokenize(chunk["text"])) for chunk in chunks]
    df = Counter(term for count in counts for term in count)
    idf = {term: math.log((len(chunks) + 1) / (freq + 1)) + 1 for term, freq in df.items()}
    query_counts = Counter(tokenize(query))
    # Include out-of-vocabulary terms in the query norm, with df=0.
    qvec = {term: count * idf.get(term, math.log(len(chunks) + 1) + 1) for term, count in query_counts.items()}
    qnorm = math.sqrt(sum(value * value for value in qvec.values()))
    results = []
    for chunk, count in zip(chunks, counts):
        vec = {term: freq * idf[term] for term, freq in count.items()}
        norm = math.sqrt(sum(value * value for value in vec.values()))
        dot = sum(value * qvec.get(term, 0) for term, value in vec.items())
        score = dot / (norm * qnorm) if norm and qnorm else 0.0
        results.append({"chunk": chunk, "score": min(1.0, max(0.0, score))})
    return sorted(results, key=lambda result: -result["score"])[:max(0, top_k)]
