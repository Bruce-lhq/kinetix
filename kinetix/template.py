"""Jinja2-based template rendering for .ktx files.

Usage in .ktx:
    [t1]: text("Hello {{ user.name }}", font: heiti, size: 56)
    [v1]: {{ bg_video }}
    [v1] @ 00:00 | duration: {{ duration }}s

CLI:
    kinetix template.ktx --data vars.json
    kinetix template.ktx --var name=Alice --var score=95

Python:
    from kinetix.template import render_template
    result = render_template(source, {"user": {"name": "Alice"}})
"""

from __future__ import annotations

import json
from pathlib import Path


def _render(source: str, variables: dict) -> str:
    """Render Jinja2 template with given variables."""
    from jinja2 import Environment, BaseLoader, StrictUndefined
    env = Environment(loader=BaseLoader(), undefined=StrictUndefined)
    tpl = env.from_string(source)
    return tpl.render(**variables)


def render_template(
    source: str,
    variables: dict | None = None,
    strict: bool = False,
) -> str:
    """If variables provided, render source as Jinja2 template.

    Args:
        source: .ktx source text (may contain {{ jinja2 }} expressions).
        variables: dict of template variables.
        strict: if True, raise on undefined variables; else ignore.

    Returns:
        Rendered ktx source string.
    """
    if not variables:
        return source
    if "{{" not in source and "{%" not in source:
        return source  # no template syntax, skip
    try:
        return _render(source, variables)
    except Exception as e:
        if strict:
            raise
        return source


def load_variables_file(path: str) -> dict:
    """Load template variables from a JSON file."""
    return json.loads(Path(path).read_text(encoding="utf-8"))
