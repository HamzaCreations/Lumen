"""Prompt contract tests: notebook parity + human-friendly formatting rules."""
from __future__ import annotations

from app.prompt import NOTEBOOK_INSTRUCTION, build_plain_prompt, build_prompt
from app.retriever import Hit


def test_notebook_instruction_is_preserved_verbatim():
    assert NOTEBOOK_INSTRUCTION == (
        "Answer the question using ONLY the context below. "
        'If the answer is not in the context, say "I do not know". '
        "Do not guess. Cite the source file for each fact you use."
    )


def test_grounded_prompt_contains_context_and_format_rules():
    hits = [
        Hit(id=0, source="12_evaluation_metrics.txt", score=0.662,
            semantic_score=0.662, text="Precision = TP / (TP + FP)"),
    ]
    prompt = build_prompt("What is precision?", hits)
    assert prompt.startswith(NOTEBOOK_INSTRUCTION)
    assert "[Source 1: 12_evaluation_metrics.txt]" in prompt
    assert "Precision = TP / (TP + FP)" in prompt
    assert "Response format:" in prompt
    assert "NEVER emit raw LaTeX" in prompt
    assert "compact [Source N] tag" in prompt
    assert prompt.endswith("Question: What is precision?\nAnswer:")


def test_plain_prompt_is_the_bare_question():
    assert build_plain_prompt("What is precision?") == "What is precision?"
