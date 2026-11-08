"""Prompt template from the notebook (Step 5), plus a response-format block.

The grounding instruction, "I do not know" rule and citation requirement are
kept byte-for-byte from the notebook. The extra formatting block only controls
HOW the answer is presented to a human in the chat UI: plain Markdown, no raw
LaTeX, compact [Source N] tags that map to the structured source cards.

Hits are passed in instead of retrieved again, so /ask does not pay for two
embedding calls.
"""
from __future__ import annotations

from .retriever import Hit

NOTEBOOK_INSTRUCTION = (
    "Answer the question using ONLY the context below. "
    'If the answer is not in the context, say "I do not know". '
    "Do not guess. Cite the source file for each fact you use."
)

RESPONSE_FORMAT = (
    "\nResponse format:\n"
    "- Write clear, friendly Markdown: short paragraphs, bullet lists for enumerations, "
    "**bold** only for key terms.\n"
    "- NEVER emit raw LaTeX (no \\[ ... \\], $$, \\frac, \\text). Write formulas as "
    "simple inline code, e.g. `Precision = TP / (TP + FP)`.\n"
    "- Cite each fact with a compact [Source N] tag matching the numbered context blocks. "
    "The full file names are shown separately in the Sources panel, so do not paste "
    "long file paths or 【...】 markers into the prose.\n"
    "- Be concise, do not repeat the question, and start directly with the answer.\n"
)


def build_prompt(question: str, hits: list[Hit]) -> str:
    context = ""
    for i, hit in enumerate(hits, start=1):
        context += f"\n[Source {i}: {hit.source}]\n{hit.text}\n"
    return (
        f"{NOTEBOOK_INSTRUCTION}\n"
        f"\nContext:{context}"
        f"{RESPONSE_FORMAT}"
        f"\nQuestion: {question}\nAnswer:"
    )


def build_plain_prompt(question: str) -> str:
    """Step 6's no-retrieval baseline: the bare question, nothing else."""
    return question
