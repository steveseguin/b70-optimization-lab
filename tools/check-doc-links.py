#!/usr/bin/env python3
"""Check that repository-relative links inside the guides and site pages point at files that exist.

Covers Markdown links and HTML hrefs whose target is a path in this repository (not http, mailto or a bare anchor).
Link rot here is silent: a renamed evidence file leaves a guide pointing at nothing, and nobody notices until a reader
tries to follow it. Offline and fast, so it can run on every change.

usage: check-doc-links.py [--all-tracked | PATH ...] [--json OUT]
The default scope remains the public guides and site entry points. --all-tracked
also covers experiment notes and other tracked Markdown/HTML, including staged
new files. It reads working-tree contents, not the staged blob contents.
Run --all-tracked from the repository root.

Exit 1 for new broken repository links, unreadable documents, or invalid pinned
baseline exceptions. Optional baseline document/source SHA256 fields are checked,
and a supplied resolved_source must exist. Legacy unpinned entries still work.
Absolute host
paths and template destinations are reported separately as unverified; their
targets and remote URLs are not opened. This is a path check, not a full Markdown,
fragment-anchor, publication, or evidence-integrity validator.
"""
from __future__ import annotations
import argparse, glob, hashlib, json, os, re, subprocess, sys, urllib.parse
from html.parser import HTMLParser
from pathlib import Path

MD = re.compile(r"(?<!\\)\[[^\]]*\]\((?:<([^>\n]+)>|([^)\s]+))(?:\s+\"[^\"]*\")?\)")
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
INLINE_CODE = re.compile(r"(?<!`)(`+)(?!`)(.*?)(?<!`)\1(?!`)", re.DOTALL)
HOST_PATH = re.compile(r"^/(?:home|mnt|media|tmp|var|usr|opt|root|run|dev|proc|sys|etc|srv)(?:/|$)")
SKIP = ("http://", "https://", "//", "mailto:", "data:", "#", "javascript:", "tel:")


def markdown_prose(text: str) -> str:
    """Remove fenced blocks and inline code without hiding surrounding links."""
    lines = []
    fence = None
    for line in text.splitlines(keepends=True):
        match = FENCE.match(line)
        if fence:
            if match and match[1][0] == fence[0] and len(match[1]) >= fence[1] and not match[2].strip():
                fence = None
            lines.append("\n")
        elif match:
            fence = (match[1][0], len(match[1]))
            lines.append("\n")
        else:
            lines.append(line)
    return INLINE_CODE.sub(lambda m: re.sub(r"[^\n]", " ", m[0]), "".join(lines))


class HTMLTargets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        self.links.extend(value for key, value in attrs if key in ("href", "src") and value)


def targets(path: str):
    with open(path, encoding="utf-8", errors="replace") as stream:
        text = stream.read()
    if path.lower().endswith(".md"):
        for m in MD.finditer(markdown_prose(text)):
            yield m[1] or m[2]
    else:
        parser = HTMLTargets()
        parser.feed(text)
        yield from parser.links


def check_file(path: str, root: str, unverified=None):
    bad = []
    for raw in targets(path):
        if raw.startswith(SKIP) or not raw.strip():
            continue
        # These are visible limitations, not successful existence checks.
        kind = None
        if "${" in raw or "{{" in raw or raw in ("…", "..."):
            kind = "template"
        link = urllib.parse.unquote(raw.split("#", 1)[0].split("?", 1)[0])
        if HOST_PATH.match(link) or link.startswith("file:"):
            kind = "absolute-host-path"
        if kind:
            if unverified is not None:
                unverified.append({"link": raw, "reason": kind})
            continue
        if not link:
            continue
        base = root if link.startswith("/") else os.path.dirname(path)
        resolved = os.path.normpath(os.path.join(base, link.lstrip("/")))
        if not os.path.exists(resolved):
            bad.append({"link": raw, "resolved": os.path.relpath(resolved, root)})
    return bad


def tracked_documents(root: str):
    prefix = subprocess.run(["git", "-C", root, "rev-parse", "--show-prefix"],
                            check=True, stdout=subprocess.PIPE)
    if prefix.stdout.strip():
        raise ValueError("run --all-tracked from the repository root")
    result = subprocess.run(["git", "-C", root, "ls-files", "--cached", "-z"],
                            check=True, stdout=subprocess.PIPE)
    # NUL separation preserves spaces and newlines; --cached includes new
    # staged files and excludes untracked scratch files and staged deletions.
    return sorted({os.fsdecode(p) for p in result.stdout.split(b"\0")
                   if p and p.lower().endswith((b".md", b".html"))})


def load_baseline(filename: str, root: str):
    """Honor old link-only exceptions; verify any supplied evidence bindings."""
    try:
        with open(filename, encoding="utf-8") as stream:
            entries = json.load(stream)["known_broken"]
        if not isinstance(entries, list):
            raise ValueError("known_broken must be a list")
    except FileNotFoundError:
        return set(), []  # The historical default baseline is optional.
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return set(), [f"{filename}: cannot read baseline: {exc}"]
    known, errors = set(), []
    repo = Path(root).resolve()
    for number, entry in enumerate(entries, 1):
        label = f"{filename} entry {number}"
        if not isinstance(entry, dict) or not all(isinstance(entry.get(k), str) and entry[k]
                                                  for k in ("document", "link")):
            errors.append(f"{label}: document and link must be nonempty strings")
            continue
        known.add((entry["document"], entry["link"]))
        for field, hash_field in (("document", "document_sha256"),
                                  ("resolved_source", "resolved_source_sha256")):
            if hash_field not in entry and (field == "document" or field not in entry):
                continue
            try:
                relative = entry.get(field)
                if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
                    raise ValueError(f"{field} must be a repository-relative file path")
                target = (repo / relative).resolve()
                if not target.is_relative_to(repo):
                    raise ValueError(f"{field} escapes the repository: {relative}")
                if not target.is_file():
                    raise ValueError(f"{field} does not exist as a file: {relative}")
                if hash_field in entry:
                    expected = entry[hash_field]
                    if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
                        raise ValueError(f"{hash_field} must be a lowercase SHA256 digest")
                    digest = hashlib.sha256()
                    with target.open("rb") as stream:
                        for block in iter(lambda: stream.read(1024 * 1024), b""):
                            digest.update(block)
                    if digest.hexdigest() != expected:
                        raise ValueError(f"{hash_field} mismatch for {relative}; pinned exception changed")
            except (OSError, ValueError) as exc:
                errors.append(f"{label}: {exc}")
    return known, errors


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--all-tracked", action="store_true",
                    help="check every Git-tracked .md/.html using its working-tree contents")
    ap.add_argument("--json", dest="out")
    ap.add_argument("--baseline", default="data/doc-link-baseline.json",
                    help="known-broken links to report but not fail on; new breakage still fails")
    a = ap.parse_args()
    if a.all_tracked and a.paths:
        ap.error("--all-tracked cannot be combined with explicit paths")
    root = os.getcwd()
    known, baseline_errors = load_baseline(a.baseline, root)
    try:
        paths = tracked_documents(root) if a.all_tracked else a.paths
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        ap.exit(2, f"cannot list tracked documents: {exc}\n")
    paths = paths if a.all_tracked or paths else sorted(
        glob.glob("*.md") + glob.glob("*.html")
        + glob.glob("repro/**/*.md", recursive=True)
        + glob.glob("packages/**/*.md", recursive=True)
        + glob.glob("learn/*.html") + glob.glob("docs/**/*.md", recursive=True)
        + glob.glob("results/**/*.md", recursive=True)
    )
    findings = {}
    unverified = {}
    read_errors = {}
    for p in paths:
        unchecked = []
        try:
            bad = check_file(p, root, unchecked)
        except OSError as exc:
            read_errors[p] = str(exc)
            continue
        if bad:
            findings[p] = bad
        if unchecked:
            unverified[p] = unchecked
    baselined = {p: [b for b in bad if (p, b["link"]) in known] for p, bad in findings.items()}
    findings = {p: [b for b in bad if (p, b["link"]) not in known] for p, bad in findings.items()}
    findings = {p: v for p, v in findings.items() if v}
    total = sum(len(v) for v in findings.values())
    known_total = sum(len(v) for v in baselined.values())
    unchecked_total = sum(len(v) for v in unverified.values())
    for p, bad in sorted(baselined.items()):
        for b in bad:
            print(f"known-broken   {p}: {b['link']}")
    for p, bad in sorted(findings.items()):
        print(f"{p}: {len(bad)} broken")
        for b in bad[:8]:
            print(f"    - {b['link']}  ->  {b['resolved']}")
        if len(bad) > 8:
            print(f"    ... {len(bad) - 8} more")
    for p, unchecked in sorted(unverified.items()):
        print(f"{p}: {len(unchecked)} unverified host/template reference(s)")
        for item in unchecked[:3]:
            print(f"    - {item['reason']}: {item['link']}")
        if len(unchecked) > 3:
            print(f"    ... {len(unchecked) - 3} more (use --json for all)")
    for p, error in sorted(read_errors.items()):
        print(f"unreadable document {p}: {error}")
    for error in baseline_errors:
        print(f"baseline error: {error}")
    print(f"\nchecked {len(paths)} documents, {total} new broken repository-relative link(s) in {len(findings)} file(s), {known_total} known-broken")
    if unchecked_total or read_errors:
        print(f"{unchecked_total} unverified host/template reference(s); {len(read_errors)} unreadable document(s)")
    if baseline_errors:
        print(f"{len(baseline_errors)} invalid baseline evidence binding(s)")
    if a.out:
        with open(a.out, "w") as stream:
            json.dump({"documents_checked": len(paths), "broken_total": total,
                       "findings": findings, "known_broken_total": known_total,
                       "known_broken": {p: v for p, v in baselined.items() if v},
                       "unverified_total": unchecked_total, "unverified": unverified,
                       "read_errors": read_errors, "baseline_errors": baseline_errors},
                      stream, ensure_ascii=False, indent=1)
    return 0 if total == 0 and not read_errors and not baseline_errors else 1


if __name__ == "__main__":
    sys.exit(main())
