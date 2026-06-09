"""WeasyPrint-Wrapper fuer HTML -> PDF."""

from __future__ import annotations

from pathlib import Path

from weasyprint import HTML


def render_pdf(html_string: str, output_path: Path, base_url: str | None = None):
    html = HTML(string=html_string, base_url=base_url)
    html.write_pdf(str(output_path))
