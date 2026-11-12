"""Every relative Markdown link in the docs, skills and guides must point at a real file."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LINK = re.compile(r"\[[^\]]*\]\(([^)#\s]+)(?:#[^)]*)?\)")
FILES = sorted(
    [*ROOT.glob("*.md"), *(ROOT / "docs").glob("*.md"), *(ROOT / ".claude").rglob("*.md")]
)


@pytest.mark.parametrize("md", FILES, ids=lambda p: str(p.relative_to(ROOT)))
def test_relative_links_resolve(md):
    broken = []
    for target in LINK.findall(md.read_text(encoding="utf-8")):
        if re.match(r"^(https?:|mailto:)", target):
            continue
        if not (md.parent / target).resolve().exists():
            broken.append(target)
    assert not broken, f"{md.relative_to(ROOT)} has broken links: {broken}"


def test_windows_and_learning_docs_exist_and_are_linked_from_readme():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for doc in ("docs/WINDOWS.md", "docs/HOW_IT_WORKS.md", "docs/GETTING_STARTED.md", "AGENTS.md"):
        assert (ROOT / doc).exists() and doc in readme
