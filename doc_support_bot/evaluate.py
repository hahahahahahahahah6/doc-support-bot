"""Measured response behavior, not a claim of answer accuracy."""
from .answer import answer_question
from .retrieve import search


def evaluate(index, qa_pairs):
    total = answered = covered = 0
    score_sum = 0.0
    for pair in qa_pairs:
        result = answer_question(index, pair["question"])
        top = search(index, pair["question"], top_k=1)
        total += 1
        score_sum += top[0]["score"] if top else 0
        answered += int(not result["escalated"])
        covered += int(not result["escalated"] and bool(result["sources"]))
    escalated = total - answered
    return {"total": total, "answered": answered, "escalated": escalated,
            "answer_rate": answered / total if total else 0.0,
            "escalation_rate": escalated / total if total else 0.0,
            "citation_coverage": covered / answered if answered else 0.0,
            "mean_top_score": score_sum / total if total else 0.0}
