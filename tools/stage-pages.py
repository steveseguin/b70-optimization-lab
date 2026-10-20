#!/usr/bin/env python3
"""Stage the public static site and its linked files, never the research tree.

Run --dry-run first to see the complete size before copying. HTML/CSS/JS assets,
public-manifest file references and catalog copy-button targets are required;
broken historical Markdown links and directories without an index are reported
as warnings. No Markdown is rendered or source file rewritten.
Only tracked regular files are eligible. Symlinks, including parent-directory
symlinks, are never followed. Output must be empty and outside the checkout.
"""
import argparse
from collections import deque
from html import unescape
from html.parser import HTMLParser
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import runpy
import shutil
import stat
import subprocess
import sys
from urllib.parse import unquote, urlsplit


ROOT_FILES = ("CNAME", "robots.txt", "sitemap.xml", "llms.txt", "favicon.ico",
              "favicon.svg", "apple-touch-icon.png", "og-image.png", "site.webmanifest")
SITE_HOSTS = {"neural.download", "www.neural.download"}
FETCH = re.compile(r"\bfetch\(\s*(['\"])(.*?)\1", re.S)
CSS_URL = re.compile(r"url\(\s*(?:'([^']*)'|\"([^\"]*)\"|([^\s)]+))\s*\)", re.I)
CSS_IMPORT = re.compile(r"@import\s+(['\"])(.*?)\1", re.I)
MARKDOWN_LINK = re.compile(r"!?\[[^\]\n]*\]\(\s*(<[^>]+>|[^\s)]+)")
MARKDOWN_DEF = re.compile(r"(?m)^\s{0,3}\[[^\]\n]+\]:\s*(<[^>]+>|\S+)")
# Share the public-manifest path rule, including nested evidence/command fields.
MANIFEST_RULES = runpy.run_path(str(Path(__file__).with_name("check-manifest-paths.py")))
PATH_RE = MANIFEST_RULES["PATH_RE"]


def is_manifest(rel):
    parts = PurePosixPath(rel).parts
    return (rel == "packages/catalog.json" or
            (len(parts) == 3 and parts[0] == "packages" and parts[2] == "package.json") or
            (len(parts) == 2 and parts[0] == "families" and parts[1].endswith(".json")))


class HTMLLinks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.urls = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "base" and attrs.get("href"):
            raise ValueError("HTML base href is unsupported; make relative paths explicit")
        for key in ("href", "src", "poster", "data-copy-markdown", "data-copy"):
            if attrs.get(key):
                self.urls.append(attrs[key])
        if attrs.get("srcset") and not attrs["srcset"].startswith("data:"):
            self.urls.extend(entry.strip().split()[0] for entry in attrs["srcset"].split(",") if entry.strip())
        if tag == "meta" and attrs.get("property") in {"og:image", "og:url"}:
            self.urls.append(attrs.get("content", ""))


def text_links(text):
    return [m[2] for m in FETCH.finditer(text)] + [next(v for v in m.groups() if v is not None)
            for m in CSS_URL.finditer(text)] + [m[2] for m in CSS_IMPORT.finditer(text)]


def markdown_without_code(text):
    result, fence = [], None
    for line in text.splitlines():
        match = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if match:
            marker = match[1]
            if fence is None:
                fence = marker[0]
            elif marker[0] == fence:
                fence = None
            continue
        if fence is None:
            result.append(line)
    return "\n".join(result)


def tracked_paths(root):
    """Read the index, not file contents or a recursive checkout copy."""
    process = subprocess.Popen(["git", "ls-files", "--stage", "-z"], cwd=root, stdout=subprocess.PIPE)
    paths, pending = {}, b""
    while True:
        block = process.stdout.read(65536)
        if not block:
            break
        chunks = (pending + block).split(b"\0")
        pending = chunks.pop()
        for row in chunks:
            metadata, path = row.split(b"\t", 1)
            mode, _, stage = metadata.split()
            if stage != b"0":
                raise ValueError("unmerged index entries; finish resolving them before staging Pages")
            paths[os.fsdecode(path)] = mode.decode()
    if process.wait() or pending:
        raise ValueError("git ls-files failed or returned an incomplete record")
    return paths


class Planner:
    def __init__(self, root, tracked):
        self.root = Path(root).absolute()
        self.tracked = tracked
        self.files = {}
        self.errors, self.warnings = [], []
        self.queue = deque()
        self.requested = set()

    def issue(self, required, source, url, reason):
        row = {"source": source, "url": url, "reason": reason}
        target = self.errors if required else self.warnings
        if row not in target:
            target.append(row)

    def path_kind(self, rel):
        path = self.root
        for part in PurePosixPath(rel).parts:
            path /= part
            try:
                mode = path.lstat().st_mode
            except FileNotFoundError:
                return None, "missing file"
            if stat.S_ISLNK(mode):
                return None, "symlink or symlink parent refused"
        return mode, ""

    def safe_regular(self, rel):
        mode, reason = self.path_kind(rel)
        if mode is None:
            return False, reason
        if not stat.S_ISREG(mode):
            return False, "not a regular file"
        if self.tracked.get(rel) not in {"100644", "100755"}:
            return False, "not a tracked regular file"
        return True, ""

    def add(self, url, source="index.html", required=True, rooted=False, directory_ok=False):
        url = unescape(url).strip().strip("<>")
        if not url or url.startswith("#"):
            return
        if "${" in url or "{{" in url:
            return  # Dynamic catalog paths are expanded explicitly below.
        parsed = urlsplit(url)
        if parsed.scheme and parsed.scheme not in {"http", "https"}:
            return
        if parsed.netloc and parsed.hostname not in SITE_HOSTS:
            return
        if not parsed.path:
            return
        raw = unquote(parsed.path)
        if "\\" in raw or "\x00" in raw:
            self.issue(required, source, url, "invalid path")
            return
        rel = posixpath.normpath(raw.lstrip("/") if rooted or raw.startswith("/") or parsed.netloc
                                 else posixpath.join(posixpath.dirname(source), raw))
        if rel == ".." or rel.startswith("../"):
            self.issue(required, source, url, "path escapes source root")
            return
        if rel == ".":
            rel = "index.html"
        # Resolve directory routes only to real index pages; never traverse
        # the directory or substitute a symlink target.
        kind, reason = self.path_kind(rel)
        if kind is None:
            self.issue(required, source, url, reason)
            return
        if stat.S_ISDIR(kind):
            if self.safe_regular(rel + "/index.html")[0]:
                rel += "/index.html"
            elif (not required or directory_ok) and self.safe_regular(rel + "/README.md")[0]:
                self.issue(False, source, url, "directory has no index.html; preserving README.md only")
                rel += "/README.md"
            else:
                self.issue(required and not directory_ok, source, url, "directory has no index.html; directory copying refused")
                return
        safe, reason = self.safe_regular(rel)
        if not safe:
            self.issue(required, source, url, reason)
            return
        if rel not in self.requested:
            self.requested.add(rel)
            self.queue.append(rel)

    def plan(self):
        for rel, mode in self.tracked.items():
            path = PurePosixPath(rel)
            if path.suffix == ".html" and (len(path.parts) == 1 or path.parts[0] in {"models", "learn", "worker"}):
                self.add(rel, rooted=True)
            if is_manifest(rel):
                self.add(rel, rooted=True)
        if "index.html" not in self.requested:
            self.issue(True, "<roots>", "index.html", "missing public index.html")
        for rel in ROOT_FILES:
            if rel in self.tracked:
                self.add(rel, rooted=True)
        while self.queue:
            rel = self.queue.popleft()
            path = self.root / rel
            self.files[rel] = path.stat().st_size
            suffix = path.suffix.lower()
            if suffix not in {".html", ".css", ".js", ".md", ".markdown", ".webmanifest", ".json", ".txt"}:
                continue
            if suffix == ".json" and not is_manifest(rel):
                continue  # Evidence JSON is copied as bytes, not interpreted.
            if suffix == ".txt" and rel != "llms.txt":
                continue  # Logs and plain-text evidence do not expand the site.
            text = path.read_text(encoding="utf-8")
            if suffix in {".html", ".md", ".markdown"}:
                content = markdown_without_code(text) if suffix != ".html" else text
                parser = HTMLLinks()
                parser.feed(content)
                for url in parser.urls:
                    self.add(url, rel, required=suffix == ".html")
                if suffix != ".html":
                    for match in list(MARKDOWN_LINK.finditer(content)) + list(MARKDOWN_DEF.finditer(content)):
                        self.add(match[1], rel, required=False)
            if suffix in {".html", ".css", ".js"}:
                for url in text_links(text):
                    self.add(url, rel)
            if suffix == ".webmanifest":
                for icon in json.loads(text).get("icons", []):
                    self.add(icon["src"], rel)
            if is_manifest(rel):
                claims = []
                MANIFEST_RULES["walk"](json.loads(text), rel, claims)
                for _, url in claims:
                    self.add(url, rel, rooted=True, directory_ok=True)
            if rel == "packages/catalog.json":
                catalog = json.loads(text)
                for item in catalog["packages"]:
                    guide = item.get("guide") or re.sub(r"package\.json$", "README.md", item["manifest"])
                    self.add(guide, rel, rooted=True)
                    self.add("models/" + item["id"] + ".html", rel, rooted=True)
            if suffix == ".txt":
                for url in re.findall(r"https?://(?:www\.)?neural\.download/[^\s<>]+", text):
                    self.add(url.rstrip(".,):;"), rel, required=False)
        return {"files": dict(sorted(self.files.items())), "file_count": len(self.files),
                "bytes": sum(self.files.values()), "errors": self.errors, "warnings": self.warnings}


def copy_plan(planner, destination):
    destination = Path(destination).absolute()
    if destination.resolve() != destination:
        raise ValueError("destination must not use symlink parents")
    if destination == planner.root or planner.root in destination.parents:
        raise ValueError("destination must be outside the source repository")
    if destination.is_symlink() or (destination.exists() and any(destination.iterdir())):
        raise ValueError("destination must be absent or an empty directory")
    if planner.errors:
        raise ValueError("required assets failed validation; no files copied")
    # Revalidate every source before creating anything; the planning pass never
    # follows links, and replacing a source with a link cannot silently pass.
    for rel, size in planner.files.items():
        safe, reason = planner.safe_regular(rel)
        if not safe or (planner.root / rel).stat().st_size != size:
            raise ValueError(f"source changed after planning: {rel}: {reason}")
    destination.mkdir(parents=True, exist_ok=True)
    for rel in planner.files:
        target = destination / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        safe, reason = planner.safe_regular(rel)
        if not safe:
            raise ValueError(f"source changed during copying: {rel}: {reason}")
        descriptor = os.open(planner.root / rel, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "rb") as source:
            if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                raise ValueError(f"source is no longer a regular file: {rel}")
            with target.open("xb") as output:
                shutil.copyfileobj(source, output, length=1024 * 1024)
    (destination / ".nojekyll").write_text("")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, help="empty destination outside the repository")
    parser.add_argument("--report", type=Path, help="write full JSON plan outside the repository")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-bytes", type=int, default=500_000_000)
    args = parser.parse_args()
    try:
        source = args.source.resolve()
        planner = Planner(source, tracked_paths(source))
        report = planner.plan()
        if report["bytes"] > args.max_bytes:
            report["errors"].append({"source": "<plan>", "url": "", "reason": "planned payload exceeds --max-bytes"})
        if args.report:
            report_path = args.report.resolve()
            if report_path == source or source in report_path.parents:
                raise ValueError("report must be outside the source repository")
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        print(f"Pages plan: {report['file_count']} files, {report['bytes']} bytes; "
              f"{len(report['errors'])} errors, {len(report['warnings'])} historical/directory-link warnings")
        for issue in report["errors"]:
            print(f"ERROR {issue['source']}: {issue['url']}: {issue['reason']}", file=sys.stderr)
        if report["warnings"]:
            print("Historical and directory link warnings remain visible in --report; source files are preserved unchanged.")
        if report["errors"]:
            return 1
        if not args.dry_run:
            if not args.output:
                raise ValueError("provide --output or use --dry-run")
            copy_plan(planner, args.output)
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Pages staging failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
