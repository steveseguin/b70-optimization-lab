#!/usr/bin/env python3
"""Check staged repository hygiene without modifying files or running experiments.

New/changed blobs of at least 1 MiB produce review warnings. Tracked generated
caches fail. New Markdown campaign closeouts must preserve a minimum useful
record and link repository evidence. Historical blobs are not reformatted.
The Git index is the candidate tree; use --base HEAD before committing.
CI chooses the push before-SHA or PR merge base from --event-json.
"""
from __future__ import annotations

import argparse
from collections import Counter
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import urllib.parse

EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
CACHE_DIRS = {"__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache"}
CLOSEOUT_NAME = re.compile(r"(?:^|[-_])(closeout|closure)(?:[-_.]|$)", re.I)
SECTIONS = (
    "Question and identity", "Outcome", "What worked",
    "What failed or remains uncertain", "Evidence and patches", "When to revisit",
)
LINK = re.compile(r"\[[^\]]*\]\((?:<([^>\n]+)>|([^\s)]+))\)")
REFERENCE_DEFINITION = re.compile(
    r"(?m)^ {0,3}\[([^\]\n]+)\]:[ \t]*(?:<([^>\n]+)>|([^\s]+))[^\n]*$")
REFERENCE_LINK = re.compile(r"(?<!\\)\[([^\]\n]+)\](?:[ \t]*\[([^\]\n]*)\])?")
HEADING = re.compile(r"(?m)^ {0,3}(#{1,6})[ \t]+([^\n]*?)[ \t]*$")
_LINK_SPEC = importlib.util.spec_from_file_location("doc_links", Path(__file__).with_name("check-doc-links.py"))
_LINK_CHECKER = importlib.util.module_from_spec(_LINK_SPEC)
_LINK_SPEC.loader.exec_module(_LINK_CHECKER)


def git(root, *args, input=None):
    return subprocess.run(["git", "-C", str(root), *args], input=input,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout


def base_for_event(root, path):
    event = json.loads(Path(path).read_text(encoding="utf-8"))
    if "pull_request" in event:
        sha = event["pull_request"]["base"]["sha"]
        if not re.fullmatch(r"[0-9a-f]{40,64}", sha):
            raise ValueError("invalid pull request base SHA")
        return git(root, "merge-base", "HEAD", sha).decode().strip()
    sha = event.get("before")
    if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40,64}", sha):
        raise ValueError("event must supply a push before-SHA or pull request base")
    return EMPTY_TREE if set(sha) == {"0"} else sha


def trees(root, base):
    previous = {}
    base_tree = b"" if base == EMPTY_TREE else git(root, "ls-tree", "-r", "-z", "--full-tree", base)
    for item in base_tree.split(b"\0"):
        if item:
            meta, name = item.split(b"\t", 1)
            mode, kind, oid = meta.decode().split()
            previous[os.fsdecode(name)] = {"mode": mode, "kind": kind, "oid": oid}
    candidate = {}
    for item in git(root, "ls-files", "--stage", "-z").split(b"\0"):
        if item:
            meta, name = item.split(b"\t", 1)
            mode, oid, stage = meta.decode().split()
            if stage != "0":
                raise ValueError("resolve the unmerged index before checking hygiene")
            candidate[os.fsdecode(name)] = {"mode": mode, "oid": oid}
    return previous, candidate


def repository_links(document, text, candidate):
    """Return actual linked candidate files; prose in code blocks is not evidence."""
    text = _LINK_CHECKER.markdown_prose(text)
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    normalize = lambda label: " ".join(label.split()).casefold()
    definitions = {}
    for match in REFERENCE_DEFINITION.finditer(text):
        definitions.setdefault(normalize(match[1]), match[2] or match[3])
    # An unused reference definition is not a link in the rendered document.
    text = REFERENCE_DEFINITION.sub("", text)
    targets = [match[1] or match[2] for match in LINK.finditer(text)]
    for match in REFERENCE_LINK.finditer(text):
        if text[match.end():].startswith("("):
            continue  # Inline link, already handled above.
        label = match[2] if match[2] else match[1]
        if normalize(label) in definitions:
            targets.append(definitions[normalize(label)])
    found = set()
    for raw in targets:
        target = urllib.parse.urlsplit(raw)
        if target.scheme or target.netloc or not target.path or target.path.startswith("/"):
            continue
        relative = os.path.normpath(str(PurePosixPath(document).parent / urllib.parse.unquote(target.path)))
        if (relative in candidate and relative != document
                and candidate[relative]["mode"] in ("100644", "100755")
                and relative != "experiments/CLOSEOUT-TEMPLATE.md"):
            found.add(relative)
    return sorted(found)


def markdown_sections(prose):
    """Parse ATX headings once for both section names and their visible bodies."""
    prose = re.sub(r"<!--.*?-->", "", prose, flags=re.S)
    headings = list(HEADING.finditer(prose))
    sections = []
    for index, heading in enumerate(headings):
        level = len(heading[1])
        name = re.sub(r"[ \t]+#+[ \t]*$", "", heading[2]).strip()
        end = next((other.start() for other in headings[index + 1:]
                    if len(other[1]) <= level), len(prose))
        body = prose[heading.end():end]
        body = HEADING.sub("", body)
        body = re.sub(r"<!--.*?-->", "", body, flags=re.S)
        sections.append((level, name, body))
    return sections


def check(root, base, large_bytes=1024**2):
    previous, candidate = trees(root, base)
    # Each removed old path can exempt one byte-identical move, not new copies.
    moved_blobs = Counter(v["oid"] for p, v in previous.items() if p not in candidate)
    changed = {p: v for p, v in candidate.items()
               if p not in previous or previous[p]["oid"] != v["oid"]
               or previous[p]["mode"] != v["mode"]}
    errors, warnings, closeouts = [], [], []
    for path in candidate:
        parts = PurePosixPath(path).parts
        if CACHE_DIRS.intersection(parts) or path.endswith((".pyc", ".pyo")):
            errors.append({"path": path, "reason": "generated cache must not be tracked; retain its source"})
    blobs = {v["oid"] for v in changed.values() if v["mode"] != "160000"}
    sizes = {}
    if blobs:
        output = git(root, "cat-file", "--batch-check=%(objectname) %(objecttype) %(objectsize)",
                     input=("\n".join(sorted(blobs)) + "\n").encode())
        for row in output.decode().splitlines():
            oid, kind, size = row.split()
            if kind == "blob":
                sizes[oid] = int(size)
    for path, item in sorted(changed.items()):
        size = sizes.get(item["oid"], 0)
        if size >= large_bytes:
            warnings.append({"path": path, "bytes": size,
                             "reason": "large artifact: document value, consumers, retention and restoration; a duplicate is not automatically disposable"})
        if not path.lower().endswith(".md") or item["mode"] not in ("100644", "100755"):
            continue
        # Existing source blobs can move without imposing a new format on frozen evidence.
        if path not in previous and moved_blobs[item["oid"]] > 0:
            moved_blobs[item["oid"]] -= 1
            continue
        text = git(root, "cat-file", "blob", item["oid"]).decode("utf-8", errors="replace")
        marked = "<!-- campaign-closeout -->" in text
        if path in previous and previous[path]["mode"] in ("100644", "100755"):
            old_text = git(root, "cat-file", "blob", previous[path]["oid"]).decode("utf-8", errors="replace")
            marked = marked or "<!-- campaign-closeout -->" in old_text
        if path in previous and not marked:
            continue
        if not (CLOSEOUT_NAME.search(PurePosixPath(path).name)
                or marked):
            continue
        if path == "experiments/CLOSEOUT-TEMPLATE.md":
            continue
        prose = _LINK_CHECKER.markdown_prose(text)
        sections = markdown_sections(prose)
        headings = {name for level, name, _ in sections if level >= 2}
        missing = [s for s in SECTIONS if s not in headings]
        if missing:
            errors.append({"path": path, "reason": "closeout is missing sections: " + ", ".join(missing)})
        evidence = repository_links(path, text, candidate)
        if not evidence:
            errors.append({"path": path, "reason": "closeout needs at least one link to tracked repository evidence"})
        # Empty headings or untouched template placeholders cannot satisfy the contract.
        for level, name, body in sections:
            if level >= 2 and name in SECTIONS and (not body.strip() or "<fill in" in body.lower()):
                errors.append({"path": path, "reason": f"closeout section needs content: {name}"})
        closeouts.append({"path": path, "evidence": evidence})
    return {"schema": "lab.repository-hygiene.v1", "base": base,
            "candidate": "git-index", "tracked_files": len(candidate),
            "changed_files": len(changed), "large_threshold_bytes": large_bytes,
            "large_artifacts": warnings, "closeouts_checked": closeouts, "errors": errors}


def annotation(value):
    return str(value).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A").replace(",", "%2C").replace(":", "%3A")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    bases = ap.add_mutually_exclusive_group()
    bases.add_argument("--base", default=None, help="compare the index against this Git tree (default HEAD)")
    bases.add_argument("--event-json", help="CI push/PR event JSON; choose its actual comparison base")
    ap.add_argument("--large-bytes", type=int, default=1024**2)
    ap.add_argument("--json", type=Path, help="write a report outside source evidence")
    args = ap.parse_args(argv)
    if args.large_bytes < 1:
        ap.error("--large-bytes must be positive")
    root = Path(__file__).resolve().parents[1]
    try:
        base = base_for_event(root, args.event_json) if args.event_json else args.base or "HEAD"
        report = check(root, base, args.large_bytes)
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as exc:
        ap.exit(2, f"cannot check repository hygiene: {exc}\n")
    for severity, items in (("warning", report["large_artifacts"]), ("error", report["errors"])):
        for item in items:
            suffix = f" ({item['bytes']:,} bytes)" if "bytes" in item else ""
            print(f"{severity}: {item['path']}{suffix}: {item['reason']}")
            if os.environ.get("GITHUB_ACTIONS") == "true":
                print(f"::{severity} file={annotation(item['path'])}::{annotation(item['reason'] + suffix)}")
    print(f"checked {report['tracked_files']} tracked paths, {report['changed_files']} changed; "
          f"{len(report['large_artifacts'])} large-artifact warnings, {len(report['errors'])} errors")
    if args.json:
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return int(bool(report["errors"]))


if __name__ == "__main__":
    sys.exit(main())
