"""Conservative extractive answers and explicit escalation."""
from .retrieve import search

DONT_KNOW = "I don't know based on the provided documents. A human will follow up."


def answer_question(index, question, threshold=0.08):
    if not question.strip():
        return {"answer": "Please ask a question.", "escalated": True, "sources": []}
    results = search(index, question)
    if not results or results[0]["score"] <= 0 or results[0]["score"] < threshold:
        return {"answer": DONT_KNOW, "escalated": True, "sources": []}
    sources = [{"doc": item["chunk"]["doc"], "section": item["chunk"]["section"],
                "score": round(item["score"], 3), "snippet": item["chunk"]["text"][:600]}
               for item in results if item["score"] > 0 and item["score"] >= threshold * 0.5]
    return {"answer": results[0]["chunk"]["text"][:600], "escalated": False, "sources": sources}
