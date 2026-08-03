#!/usr/bin/env python3
"""Rebuild and validate the complete EvoLex patent review package."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parent


def run(*args: object) -> None:
    subprocess.run([str(arg) for arg in args], cwd=PROJECT_ROOT, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skill-dir",
        type=Path,
        default=Path.home() / ".codex" / "skills" / "nature-paper-to-patent",
        help="Installed nature-paper-to-patent skill directory",
    )
    args = parser.parse_args()
    scripts = args.skill_dir / "scripts"
    draft = ROOT / "draft.json"
    outputs = ROOT / "outputs"
    figures = outputs / "EvoLex-figures"

    run(sys.executable, ROOT / "build_draft.py")
    run(
        sys.executable,
        scripts / "validate_patent_draft.py",
        draft,
        "--report",
        ROOT / "work" / "06-validation.txt",
    )
    run(
        sys.executable,
        scripts / "build_patent_package.py",
        draft,
        "--output-dir",
        outputs,
        "--prefix",
        "EvoLex",
    )

    # Replace generic fallback-font figures before producing the final DOCX set.
    run(
        sys.executable,
        ROOT / "render_figures.py",
        draft,
        "--output-dir",
        figures,
    )
    renderer = scripts / "render_patent_docx.py"
    for part, filename in (
        ("specification", "EvoLex-说明书.docx"),
        ("abstract", "EvoLex-说明书摘要.docx"),
        ("abstract-figure", "EvoLex-摘要附图.docx"),
        ("all", "EvoLex-完整审阅稿.docx"),
    ):
        run(
            sys.executable,
            renderer,
            draft,
            "--output",
            outputs / filename,
            "--part",
            part,
            "--figure-dir",
            figures,
        )
    print(outputs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
