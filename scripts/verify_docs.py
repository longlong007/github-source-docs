#!/usr/bin/env python3
"""Check a portable Markdown doc set and its source citations, without network access.

Use single-line inline links [label](target) or [label](<target>). Encode spaces
and parentheses in bare targets. Fenced examples and single-line inline code are
ignored. Relative links should name files. Local heading anchors, HTML, reference
links, external URLs and the meaning of a citation are outside this check.
"""

import argparse
import re
import subprocess
import sys
from functools import lru_cache
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit


LINK = re.compile(r"(?<!\\)\[(?:\\.|[^\[\]\\])*\]\( *(?:<([^<>]+)>|([^()\s]+)) *\)")
INLINE_CODE = re.compile(r"(?<!`)(`+)(?!`).*?(?<!`)\1(?!`)")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
ANCHOR = re.compile(r"L([1-9]\d*)(?:-L([1-9]\d*))?")


def targets(page):
    fence = ""
    for lineno, line in enumerate(page.read_text(encoding="utf-8").splitlines(), 1):
        delimiter = FENCE.match(line)
        if fence:
            if delimiter and delimiter[1].startswith(fence) and not delimiter[2].strip():
                fence = ""
            continue
        if delimiter:
            fence = delimiter[1]
            continue
        for match in LINK.finditer(INLINE_CODE.sub("", line)):
            yield lineno, match[1] or match[2]


def git(repo, *args):
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True)
    if result.returncode:
        raise ValueError(result.stderr.decode(errors="replace").strip() or "git lookup failed")
    return result.stdout


@lru_cache(maxsize=None)
def source_length(repo, sha, path):
    data = git(repo, "cat-file", "blob", sha + ":" + path)
    return data.count(b"\n") + int(bool(data) and not data.endswith(b"\n"))


def verify_source(url, owner_repo, repo, sha):
    """Return whether this is an in-scope source link, raising on invalid citations."""
    if url.hostname not in ("github.com", "www.github.com"):
        return False
    parts = url.path.lstrip("/").split("/", 4)
    if len(parts) < 3 or "/".join(parts[:2]).casefold() != owner_repo.casefold() or parts[2] != "blob":
        return False
    if len(parts) != 5 or parts[3] != sha:
        raise ValueError("expected a source permalink at " + sha)
    path = unquote(parts[4])
    if not path or PurePosixPath(path).is_absolute() or ".." in PurePosixPath(path).parts:
        raise ValueError("invalid source path")
    length = source_length(repo, sha, path)
    lines = ANCHOR.fullmatch(url.fragment)
    if not lines:
        raise ValueError("expected a #Lstart or #Lstart-Lend anchor")
    start = int(lines[1])
    end = int(lines[2] or lines[1])
    if not 1 <= start <= end <= length:
        raise ValueError(f"requested lines {start}–{end}, file has {length} lines")
    return True


def verify(args):
    docs = args.docs.resolve()
    sha = git(args.checkout, "rev-parse", "--verify", "--end-of-options",
              args.commit + "^{commit}").decode("ascii").strip()
    pages = {page for page in docs.rglob("*.md") if page.is_file()}
    entry = docs / (args.entry or ("index.md" if docs.joinpath("index.md").is_file() else "README.md"))
    if entry.resolve() not in pages:
        raise ValueError(f"missing entry page in docs directory: {entry}")
    graph = {page: set() for page in pages}
    problems = []
    citations = 0
    for page in sorted(pages):
        if not page.resolve().is_relative_to(docs):
            problems.append(f"{page}: linked file escapes docs directory")
            continue
        for lineno, target in targets(page):
            try:
                url = urlsplit(target)
                if url.scheme or url.netloc:
                    citations += verify_source(url, args.repository, args.checkout, sha)
                    continue
                if not url.path:
                    continue
                linked = (page.parent / unquote(url.path)).resolve()
                if not linked.is_relative_to(docs):
                    raise ValueError("link escapes docs directory")
                if not linked.is_file():
                    raise ValueError("missing file (link directly to the filename)")
                if linked in pages:
                    graph[page].add(linked)
            except ValueError as exc:
                problems.append(f"{page.relative_to(docs)}:{lineno}: {target}: {exc}")

    seen = set()
    queue = [entry.resolve()]
    while queue:
        page = queue.pop()
        if page not in seen:
            seen.add(page)
            queue.extend(graph[page] - seen)
    for page in sorted(pages - seen):
        problems.append(f"{page.relative_to(docs)}: unreachable from {entry.relative_to(docs)}")
    if not citations:
        problems.append("no valid inline source citations for " + args.repository)
    for problem in problems:
        print(problem, file=sys.stderr)
    print(f"{len(pages)} Markdown pages, {citations} valid source citations, {len(problems)} problems")
    return int(bool(problems))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("docs", type=Path, help="generated Markdown directory")
    parser.add_argument("checkout", type=Path, help="local Git checkout of the source repository")
    parser.add_argument("--repository", required=True, help="GitHub OWNER/REPO")
    parser.add_argument("--commit", default="HEAD", help="commit ish used for the documentation")
    parser.add_argument("--entry", help="entry path relative to docs (default: index.md, then README.md)")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repository):
        parser.error("--repository must be OWNER/REPO")
    try:
        return verify(args)
    except (OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
