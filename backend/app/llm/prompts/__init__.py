"""Editable prompt templates (``*.md``) with ``[[PLACEHOLDER]]`` substitution.

Templates are plain Markdown so you can tune them without touching Python. Substitution is a plain
string replace (no ``str.format``), so JSON braces in the templates need no escaping.
"""

from pathlib import Path

_DIR = Path(__file__).parent


def render(name: str, **values: str) -> str:
    text = (_DIR / f"{name}.md").read_text(encoding="utf-8")
    for key, value in values.items():
        text = text.replace(f"[[{key.upper()}]]", value)
    return text
