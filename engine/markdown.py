"""A tiny, dependency-free Markdown to HTML renderer.

Deliberately small: it handles exactly the constructs the engine's own
docs use (headings, paragraphs, unordered lists, fenced code blocks,
pipe tables, blockquotes, horizontal rules, bold, inline code, links).
It is not a general Markdown engine. Keeping it in-repo means the site
has no third-party dependency and WORKFLOW.md stays the single source.
"""
from __future__ import annotations

import html
import re

_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_CODE = re.compile(r"`([^`]+)`")


def _inline(text: str) -> str:
    """Escape a line, then apply inline links, bold and code."""
    text = html.escape(text)
    # html.escape turned & < > into entities; our own tags below are added
    # after, so they are never double-escaped.
    text = _CODE.sub(r"<code>\1</code>", text)
    text = _BOLD.sub(r"<strong>\1</strong>", text)
    text = _LINK.sub(r'<a href="\2">\1</a>', text)
    return text


def _is_table_sep(line: str) -> bool:
    return bool(re.fullmatch(r"\s*\|?[\s:|-]+\|?\s*", line)) and "-" in line


def _cells(row: str) -> list[str]:
    row = row.strip().strip("|")
    return [c.strip() for c in row.split("|")]


def render(md: str) -> str:
    lines = md.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    i, n = 0, len(lines)
    para: list[str] = []
    in_list = False

    def flush_para():
        nonlocal para
        if para:
            out.append("<p>" + " ".join(_inline(p) for p in para) + "</p>")
            para = []

    def close_list():
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    while i < n:
        line = lines[i]
        stripped = line.strip()

        # Fenced code block.
        if stripped.startswith("```"):
            flush_para(); close_list()
            i += 1
            code: list[str] = []
            while i < n and not lines[i].strip().startswith("```"):
                code.append(html.escape(lines[i]))
                i += 1
            i += 1  # skip closing fence
            out.append("<pre><code>" + "\n".join(code) + "</code></pre>")
            continue

        # Blank line ends paragraphs and lists.
        if not stripped:
            flush_para(); close_list()
            i += 1
            continue

        # Pipe table: a | line followed by a |---| separator.
        if stripped.startswith("|") and i + 1 < n and _is_table_sep(lines[i + 1]):
            flush_para(); close_list()
            header = _cells(stripped)
            out.append("<table><thead><tr>"
                       + "".join(f"<th>{_inline(c)}</th>" for c in header)
                       + "</tr></thead><tbody>")
            i += 2
            while i < n and lines[i].strip().startswith("|"):
                row = _cells(lines[i].strip())
                out.append("<tr>" + "".join(f"<td>{_inline(c)}</td>"
                                            for c in row) + "</tr>")
                i += 1
            out.append("</tbody></table>")
            continue

        # Headings.
        if stripped.startswith("#"):
            flush_para(); close_list()
            level = len(stripped) - len(stripped.lstrip("#"))
            text = stripped[level:].strip()
            out.append(f"<h{level}>{_inline(text)}</h{level}>")
            i += 1
            continue

        # Horizontal rule.
        if re.fullmatch(r"-{3,}", stripped):
            flush_para(); close_list()
            out.append("<hr>")
            i += 1
            continue

        # Blockquote.
        if stripped.startswith(">"):
            flush_para(); close_list()
            out.append(f"<blockquote>{_inline(stripped[1:].strip())}"
                       "</blockquote>")
            i += 1
            continue

        # Unordered list item.
        if stripped.startswith("- "):
            flush_para()
            if not in_list:
                out.append("<ul>"); in_list = True
            out.append(f"<li>{_inline(stripped[2:])}</li>")
            i += 1
            continue

        # Plain paragraph line.
        close_list()
        para.append(stripped)
        i += 1

    flush_para(); close_list()
    return "\n".join(out)
