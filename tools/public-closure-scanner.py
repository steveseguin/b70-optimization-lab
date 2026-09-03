#!/usr/bin/env python3
"""Scan every published package for references a third party cannot resolve.

Starting from packages/catalog.json, follow each package's guide, package
README, declared dependencies, and command entrypoints, then crawl the text
files they reference (READMEs, shell/Python scripts, Dockerfiles, JSON
manifests). Report, per package:

- repo-relative paths that are missing or not git-tracked (required-path gap
  when found in a guide, script, or Dockerfile; evidence pointer when found in
  a result JSON);
- absolute host paths in scripts and Dockerfiles (hard-coded vs. overridable
  `${VAR:-default}` vs. documented host requirement `/opt/intel/oneapi`);
- lab Docker image tags referenced without a reachable builder that produces
  them;
- GitHub release download URLs whose asset does not exist.

Read-only. Exit status 1 when any required-path gap, hard-coded host path, or
missing release asset is found.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import urllib.parse
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".md", ".sh", ".py", ".json", ".txt", ".yml", ".yaml", ".toml", ".cfg", ".env"}
PATH_RE = re.compile(r"(?<![\w/.-])((?:repro|experiments|scripts|tools|packages|data|models|results|docs|families|audits)/[A-Za-z0-9_@+./-]+)")
MD_LINK_RE = re.compile(r"\]\((\.{1,2}/[A-Za-z0-9_@+./-]+)\)")
HOST_RE = re.compile(r"(?<![\w-])(/home/[A-Za-z0-9_-]+|/mnt/[A-Za-z0-9_-]+|/opt/[A-Za-z0-9_.-]+|~/\.[A-Za-z0-9_-]+|/root/[A-Za-z0-9_.-]+)(/[^\s\"'`)>;|,]*)?")
IMAGE_RE = re.compile(r"(neural-download/[A-Za-z0-9._-]+:[A-Za-z0-9._-]+)")
RELEASE_RE = re.compile(r"https://github\.com/steveseguin/b70-optimization-lab/releases/download/([A-Za-z0-9._-]+)/([A-Za-z0-9._+%-]+)")
HOST_REQUIREMENTS = ("/opt/intel/oneapi",)
CONTAINER_PATHS = ("/opt/venv", "/opt/intel/oneapi", "/root/.cache", "/root/.config", "/model", "/opt/uv", "/opt/localmaxx")
STRIP_TRAIL = ".,;:)]}>'\"`*"


def tracked_files() -> set[str]:
    out = subprocess.run(["git", "-C", str(ROOT), "ls-files"], check=True, capture_output=True, text=True).stdout
    return set(out.splitlines())


def is_text(path: Path) -> bool:
    return path.suffix in TEXT_SUFFIXES or path.name.startswith("Dockerfile") or path.name in ("Makefile",)


def clean(token: str) -> str:
    token = token.rstrip(STRIP_TRAIL)
    for junk in ("<br>", "&times;", "&middot;"):
        token = token.split(junk)[0]
    return token


def release_assets(tag: str, cache: dict[str, set[str]]) -> set[str]:
    if tag not in cache:
        try:
            out = subprocess.run(["gh", "release", "view", tag, "--json", "assets", "--jq", ".assets[].name"], check=True, capture_output=True, text=True).stdout
            cache[tag] = set(out.split())
        except Exception:
            cache[tag] = set()
    return cache[tag]


def scan_package(pkg: dict, tracked: set[str], rel_cache: dict) -> dict:
    seeds: list[str] = [pkg["guide"]]
    pkg_readme = Path(pkg["manifest"]).parent / "README.md"
    if (ROOT / pkg_readme).exists():
        seeds.append(str(pkg_readme))
    lane_dirs = {str(Path(pkg["guide"]).parent)}
    seeds += pkg.get("dependencies", [])
    for cmd in (pkg.get("commands") or {}).values():
        seeds += [m for m in PATH_RE.findall(cmd)]
    queue = [s for s in dict.fromkeys(seeds)]
    seen: set[str] = set()
    findings = defaultdict(list)
    images_used: dict[str, list[str]] = defaultdict(list)
    images_built: set[str] = set()
    while queue:
        rel = clean(queue.pop())
        if rel in seen or not rel:
            continue
        seen.add(rel)
        path = ROOT / rel
        if not path.exists():
            findings["missing_path"].append({"path": rel, "referenced_by": "seed"})
            continue
        if rel not in tracked and path.is_file():
            findings["untracked_path"].append({"path": rel, "referenced_by": "seed"})
        if path.is_dir() or not is_text(path) or path.stat().st_size > 8_000_000:
            continue
        is_note = rel.endswith(".md") and (rel.startswith(("experiments/", "results/", "docs/", "community/", "families/", "audits/")) or "/notes/" in rel)
        is_data = rel.endswith(".json") and ("/data/" in rel or rel.startswith(("experiments/", "results/", "data/")))
        kind = "evidence" if (is_note or is_data) else "recipe"
        if kind == "evidence":
            continue
        rel_in_lane = any(rel.startswith(d + "/") for d in lane_dirs) or rel in seeds
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for m in PATH_RE.findall(line):
                m = clean(m)
                if not m or m.endswith("/"):
                    continue
                if not (ROOT / m).exists():
                    for anc in (path.parent, path.parent.parent, path.parent.parent.parent):
                        if anc != ROOT.parent and (anc / m).exists():
                            m = str((anc / m).resolve().relative_to(ROOT))
                            break
                target = ROOT / m
                if not target.exists():
                    key = "missing_path" if kind == "recipe" else "evidence_missing_path"
                    findings[key].append({"path": m, "referenced_by": f"{rel}:{lineno}"})
                elif target.is_file() and m not in tracked:
                    key = "untracked_path" if kind == "recipe" else "evidence_untracked_path"
                    findings[key].append({"path": m, "referenced_by": f"{rel}:{lineno}"})
                elif target.is_file() and m not in seen and kind == "recipe" and (
                    m.endswith((".sh", ".py")) or "Dockerfile" in m or m.endswith((".json", ".patch", ".txt"))
                    or (m.endswith(".md") and m.startswith("repro/"))
                ) and (any(m.startswith(d + "/") for d in lane_dirs) or rel_in_lane):
                    queue.append(m)
            if rel.endswith(".md"):
                for m in MD_LINK_RE.findall(line):
                    target = (path.parent / m).resolve()
                    try:
                        r = str(target.relative_to(ROOT))
                    except ValueError:
                        continue
                    if not target.exists():
                        findings["missing_path"].append({"path": r, "referenced_by": f"{rel}:{lineno}"})
                    elif target.is_file() and r not in tracked:
                        findings["untracked_path"].append({"path": r, "referenced_by": f"{rel}:{lineno}"})
                    elif target.is_file() and r not in seen and kind == "recipe" and (
                        r.endswith((".sh", ".py")) or "Dockerfile" in r or r.endswith((".json", ".patch", ".txt"))
                        or (r.endswith(".md") and r.startswith("repro/"))
                    ):
                        queue.append(r)
            if kind == "recipe" and (rel.endswith((".sh", ".py")) or "Dockerfile" in rel):
                for base, tail in HOST_RE.findall(line):
                    full = base + (tail or "")
                    if "/path/to" in full or full.startswith(CONTAINER_PATHS) or full.startswith("/root/.cache/vllm"):
                        continue
                    if full.startswith(HOST_REQUIREMENTS):
                        findings["host_requirement"].append({"path": full, "referenced_by": f"{rel}:{lineno}"})
                        continue
                    before = line.split(base)[0]
                    overridable = (":-" in before[-60:]) or bool(re.search(r"[A-Z_]*DEFAULT[A-Z_]*\s*=", before)) or bool(re.search(r"(default|DEFAULT)\s*[=:(]", before))
                    key = "host_path_overridable_default" if overridable else "host_path_hardcoded"
                    findings[key].append({"path": full, "referenced_by": f"{rel}:{lineno}", "line": line.strip()[:160]})
            if kind == "recipe":
                for img in IMAGE_RE.findall(line):
                    if rel.endswith(".md") or rel.endswith(".sh") or "Dockerfile" in rel or rel.endswith(".json"):
                        images_used[img].append(f"{rel}:{lineno}")
                    if re.search(r"(--tag|IMAGE=\$\{IMAGE:-|^image=\$\{IMAGE:-|FINAL_IMAGE=|final_image=\$\{FINAL_IMAGE:-|docker tag)", line) and (rel.endswith(".sh") or "Dockerfile" in rel):
                        images_built.add(img)
                for tag, asset in RELEASE_RE.findall(line):
                    asset = urllib.parse.unquote(asset)
                    if asset not in release_assets(tag, rel_cache):
                        findings["missing_release_asset"].append({"tag": tag, "asset": asset, "referenced_by": f"{rel}:{lineno}"})
    # builders anywhere in the repo count: image tags are global, not per lane
    for bp in list(ROOT.glob("repro/**/build-*.sh")) + list(ROOT.glob("repro/**/Dockerfile*")) + list(ROOT.glob("scripts/build-*.sh")):
        try:
            for line in bp.read_text(errors="replace").splitlines():
                if re.search(r"(--tag|IMAGE=\$\{IMAGE:-|^image=\$\{IMAGE:-|FINAL_IMAGE=|final_image=\$\{FINAL_IMAGE:-|docker tag|^ARG BASE_IMAGE=)", line):
                    images_built.update(IMAGE_RE.findall(line))
        except Exception:
            pass
    for img, refs in images_used.items():
        if img not in images_built:
            findings["image_without_reachable_builder"].append({"image": img, "referenced_by": refs[:3]})
    # de-duplicate
    for k, v in findings.items():
        uniq = {json.dumps(x, sort_keys=True): x for x in v}
        findings[k] = list(uniq.values())
    return {"id": pkg["id"], "status": pkg.get("status"), "files_crawled": len(seen), "findings": dict(findings)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", action="append")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--markdown", type=Path)
    a = ap.parse_args()
    catalog = json.loads((ROOT / "packages/catalog.json").read_text())
    tracked = tracked_files()
    rel_cache: dict = {}
    reports = []
    for pkg in catalog["packages"]:
        if a.package and pkg["id"] not in a.package:
            continue
        reports.append(scan_package(pkg, tracked, rel_cache))
    # Guides that have no model package (lab-replay, research-status, capsules)
    # are scanned too, as informational lanes: their findings are reported but
    # never fail the scan, because they do not promise portability.
    packaged_guides = {pkg["guide"] for pkg in catalog["packages"]}
    guide_catalog = json.loads((ROOT / "repro/guide-catalog.json").read_text())
    for guide in guide_catalog["guides"]:
        if guide["guide"] in packaged_guides:
            continue
        if a.package and guide["id"] not in a.package:
            continue
        lane = {
            "id": guide["id"],
            "guide": guide["guide"],
            "manifest": guide["guide"],
            "dependencies": list(guide.get("dependency_links") or []),
            "status": f"informational:{guide.get('classification')}",
        }
        report = scan_package(lane, tracked, rel_cache)
        report["informational"] = True
        reports.append(report)
    blocking = ("missing_path", "untracked_path", "host_path_hardcoded", "missing_release_asset", "image_without_reachable_builder")
    lines = ["# Public closure scan", ""]
    fail = False
    for r in reports:
        f = r["findings"]
        counts = {k: len(v) for k, v in f.items()}
        bad = any(counts.get(k) for k in blocking)
        if not r.get("informational"):
            fail |= bad
        verdict = "GAPS" if bad else "clean"
        if r.get("informational") and bad:
            verdict = "gaps (informational; no portability promise)"
        lines.append(f"## {r['id']} ({r['status']}, {r['files_crawled']} files) — {verdict}")
        for k in blocking + ("host_path_overridable_default", "host_requirement", "evidence_missing_path", "evidence_untracked_path"):
            if counts.get(k):
                lines.append(f"- **{k}**: {counts[k]}")
                for x in f[k][:8]:
                    lines.append(f"  - `{x.get('path') or x.get('image') or x.get('asset')}` ← {x.get('referenced_by')}")
                if counts[k] > 8:
                    lines.append(f"  - … {counts[k]-8} more")
        lines.append("")
    if a.out:
        a.out.write_text(json.dumps(reports, indent=2) + "\n")
    md = "\n".join(lines) + "\n"
    if a.markdown:
        a.markdown.write_text(md)
    print(md)
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
