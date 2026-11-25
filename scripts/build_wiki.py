#!/usr/bin/env python3
"""Build a file:// compatible reader for a directory of Markdown source docs."""

import argparse
import base64
from dataclasses import dataclass
from html import escape
import mimetypes
from pathlib import Path
import posixpath
from string import Template
import sys
from tempfile import NamedTemporaryFile
import unicodedata
from urllib.parse import quote, unquote, urlencode, urlsplit, urlunsplit
from xml.etree import ElementTree

try:
    from markdown_it import MarkdownIt
except ImportError:
    sys.exit("Install the build dependency: python3 -m pip install 'markdown-it-py>=3,<5'")

ASSETS = Path(__file__).resolve().parents[1] / "assets" / "wiki"
UI = {
    "en": dict(contents="Documents", outline="On this page", source="View Markdown",
               search="Filter documents", close="Close navigation"),
    "zh": dict(contents="文档目录", outline="本页大纲", source="查看 Markdown 原文",
               search="筛选文档", close="关闭导航"),
}


def plain(tokens):
    parts = []
    for token in tokens:
        if token.type in ("text", "code_inline"):
            parts.append(token.content)
        elif token.type in ("hardbreak", "softbreak"):
            parts.append(" ")
        elif token.type == "image":
            parts.append(plain(token.children or []))
    return "".join(parts)


def slug(text):
    return "".join(c for c in text.lower().replace(" ", "-")
                   if c in "_-" or unicodedata.category(c)[0] in "LMN")


@dataclass
class Page:
    key: str
    title: str
    tokens: list
    anchors: set


def read_page(md, docs, path):
    key = path.relative_to(docs).as_posix()
    if not path.resolve().is_relative_to(docs):
        raise ValueError(f"Document outside the documentation directory: {key}")
    tokens = md.parse(path.read_text(encoding="utf-8-sig"))
    anchors = set()
    title = None
    for i, token in enumerate(tokens):
        if token.type != "heading_open":
            continue
        label = plain(tokens[i + 1].children or [])
        if token.tag == "h1" and title is None:
            title = label
        base = slug(label) or "section"
        fragment, suffix = base, 0
        while fragment in anchors:
            suffix += 1
            fragment = f"{base}-{suffix}"
        anchors.add(fragment)
        token.attrSet("id", "section-" + fragment)
        token.attrSet("data-fragment", fragment)
        token.attrSet("tabindex", "-1")
    return Page(key, title or path.stem, tokens, anchors)


def wiki_url(key, fragment=""):
    args = {"p": key}
    if fragment:
        args["h"] = fragment
    return "#" + urlencode(args)


def local_key(page, path):
    return posixpath.normpath(posixpath.join(posixpath.dirname(page.key), unquote(path))) if path else page.key


def navigation(entry, pages, default_group):
    """Use index outline order for topic groups; include remaining pages by directory."""
    tree = {}
    seen = {entry.key}

    def add(group_names, key):
        node = tree
        for name in group_names:
            node = node.setdefault(("group", name), {})
        node[("page", key)] = None
        seen.add(key)

    headings = []
    for i, token in enumerate(entry.tokens):
        if token.type == "heading_open":
            level = int(token.tag[1:])
            headings = [(n, s) for n, s in headings if n < level]
            if level > 1:
                headings.append((level, plain(entry.tokens[i + 1].children or [])))
        for child in token.children or []:
            if child.type != "link_open":
                continue
            url = urlsplit(child.attrGet("href"))
            if url.scheme or url.netloc or not url.path:
                continue
            key = local_key(entry, url.path)
            if key in pages and key not in seen:
                path = [name for _, name in headings] or [default_group]
                add(path, key)
    for key in pages:
        if key not in seen:
            add(key.split("/")[:-1] or [default_group], key)

    def link(key):
        return (f'<a class="page-link" data-page="{escape(key)}" href="{escape(wiki_url(key))}">'
                f'{escape(pages[key].title)}</a>')

    def branch(node):
        result = []
        for (kind, name), sub in node.items():
            if kind == "page":
                result.append(link(name))
            else:
                result.append(f'<details open><summary>{escape(name)}</summary>'
                              f'<div class="branch">{branch(sub)}</div></details>')
        return "".join(result)
    return link(entry.key) + branch(tree)


def image_data(path):
    mime = mimetypes.guess_type(path.name)[0]
    if not mime or not mime.startswith("image/"):
        raise ValueError(f"Unsupported image type: {path}")
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def prepare_content(page, pages, docs, diagrams):
    diagram_no = 0
    for token in page.tokens:
        if token.type == "fence" and token.info.split()[:1] == ["mermaid"]:
            diagram_no += 1
            name = Path(page.key) / f"{diagram_no}.svg"
            diagram = diagrams / name if diagrams else None
            if not diagram or not diagram.is_file():
                raise ValueError(f"{page.key}: render Mermaid diagram {diagram_no} as "
                                 f"<diagram-dir>/{name} and pass --diagram-dir <diagram-dir>")
            svg = ElementTree.parse(diagram).getroot()
            if svg.tag.rsplit("}", 1)[-1] != "svg":
                raise ValueError(f"Expected an SVG diagram: {diagram}")
            box = svg.get("viewBox", "").split()
            size = ""
            if len(box) == 4:
                width, height = float(box[2]), float(box[3])
                if width > 0 and height > 0:
                    size = f' width="{max(1, round(width))}" height="{max(1, round(height))}"'
            alt = svg.get("aria-label") or f"{page.title} ({diagram_no})"
            token.type = "html_block"
            token.content = (f'<figure><img src="{image_data(diagram)}" alt="{escape(alt)}"{size}></figure>\n')
        for child in token.children or []:
            if child.type not in ("link_open", "image"):
                continue
            attr = "src" if child.type == "image" else "href"
            url = urlsplit(child.attrGet(attr))
            if url.scheme or url.netloc:
                if child.type == "image" and url.scheme != "data":
                    raise ValueError(f"{page.key}: use a local copy of the image {url.geturl()} for offline reading")
                if child.type == "link_open" and url.scheme in ("http", "https"):
                    child.attrSet("target", "_blank")
                    child.attrSet("rel", "noopener noreferrer")
                continue
            key = local_key(page, url.path)
            if posixpath.isabs(key) or key == ".." or key.startswith("../"):
                raise ValueError(f"{page.key}: local target outside the documentation directory: {url.path}")
            if child.type == "image":
                path = docs / key
                if not path.resolve().is_relative_to(docs):
                    raise ValueError(f"{page.key}: image outside the documentation directory: {key}")
                child.attrSet(attr, image_data(path))
            elif key in pages:
                heading = unquote(url.fragment)
                if heading and heading not in pages[key].anchors:
                    raise ValueError(f"{page.key}: missing Markdown heading: {key}#{heading}")
                child.attrSet(attr, wiki_url(key, heading))
            else:
                if key.lower().endswith(".md") or not (docs / key).is_file():
                    raise ValueError(f"{page.key}: missing local target: {key}")
                child.attrSet(attr, urlunsplit(("", "", quote(key), url.query, url.fragment)))


def build(docs, entry_key, lang, diagrams):
    docs = docs.resolve()
    md = MarkdownIt("commonmark", {"html": False}).enable(["table", "strikethrough"])
    md.renderer.rules["table_open"] = lambda *args: '<div class="table-wrap"><table>\n'
    md.renderer.rules["table_close"] = lambda *args: "</table></div>\n"
    pages = {}
    for path in sorted(docs.rglob("*.md")):
        if path.is_file():
            page = read_page(md, docs, path)
            pages[page.key] = page
    if entry_key not in pages:
        raise ValueError(f"Missing Markdown entry: {entry_key}")
    entry = pages[entry_key]
    ui = UI["zh"] if lang.lower().startswith("zh") else UI["en"]
    tree = navigation(entry, pages, ui["contents"])
    articles = []
    for page in pages.values():
        prepare_content(page, pages, docs, diagrams)
        body = md.renderer.render(page.tokens, md.options, {})
        articles.append(f'<template data-page="{escape(page.key)}" data-title="{escape(page.title)}" '
                        f'data-raw="{escape(quote(page.key))}">{body}</template>')
    template = Template((ASSETS / "reader.html").read_text(encoding="utf-8"))
    html = template.substitute(**ui, title=escape(entry.title), entry=escape(entry.key), lang=escape(lang),
                               raw_home=escape(quote(entry.key)), home_url=escape(wiki_url(entry.key)),
                               tree=tree, articles="\n".join(articles),
                               css=(ASSETS / "reader.css").read_text(encoding="utf-8"),
                               js=(ASSETS / "reader.js").read_text(encoding="utf-8"))
    output = docs / "index.html"
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=docs, delete=False) as f:
        temporary = Path(f.name)
    try:
        temporary.write_text(html, encoding="utf-8")
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    return len(pages), output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("docs", type=Path)
    parser.add_argument("--entry", default="index.md", help="Markdown entry path relative to docs")
    parser.add_argument("--lang", default="zh-CN", help="HTML language, with Chinese or English navigation")
    parser.add_argument("--diagram-dir", type=Path, help="pre-rendered Mermaid SVGs: <page.md>/<1-based number>.svg")
    args = parser.parse_args()
    try:
        count, output = build(args.docs, Path(args.entry).as_posix(), args.lang, args.diagram_dir)
    except (OSError, ValueError, ElementTree.ParseError) as error:
        parser.exit(1, f"build_wiki: {error}\n")
    print(f"{count} Markdown pages -> {output}")


if __name__ == "__main__":
    main()
