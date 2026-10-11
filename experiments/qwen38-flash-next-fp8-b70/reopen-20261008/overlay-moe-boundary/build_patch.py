#!/usr/bin/env python3
"""Seal/check a frozen diagnostic variant; stage only with explicit enablement.

Never changes the sealed lane overlay or an installed runtime. Preimages come
from Git, not mutable working files. --stage creates a fresh standalone package.
"""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
LANE = HERE.parent
REPO = LANE.parents[2]
PREFIX = str(LANE.relative_to(REPO))
BASE_REVISION = "3a6435133de4f2fc5b937e5b48033832d622df3d"
COPIES = HERE / "copies"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def before(rel):
    result = subprocess.run(["git", "show", f"{BASE_REVISION}:{PREFIX}/{rel}"],
                            cwd=REPO, capture_output=True)
    if result.returncode == 0:
        return result.stdout
    if result.returncode == 128 and (b"does not exist in" in result.stderr or b"exists on disk, but not in" in result.stderr):
        return None
    raise RuntimeError(result.stderr.decode())


def baseline():
    names = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", BASE_REVISION, PREFIX], cwd=REPO).decode().splitlines()
    payload = {}
    for name in names:
        rel = name[len(PREFIX)+1:]
        # No saved runs, checkpoints, caches or evidence copied into staging.
        if (rel.startswith("overlay/") or ("/" not in rel and Path(rel).suffix in (".py", ".sh", ".json"))
                or rel in ("probe/single_rank_slab_probe.py", "probe/watch_kernel.py")):
            payload[rel] = before(rel)
    return payload


def artifacts():
    payload = {str(p.relative_to(COPIES)): p.read_bytes() for p in sorted(COPIES.rglob("*"))
               if p.is_file() and p.suffix in (".py", ".sh")}
    manifest = json.loads(before("overlay-manifest.json"))
    for rel, raw in payload.items():
        if rel.startswith("overlay/"):
            runtime = rel[len("overlay/"):]
            manifest["files"][runtime] = sha(raw)
            if runtime in manifest["replacements"]:
                manifest["replacements"][runtime]["sha256"] = sha(raw)
            else:
                native = HERE / "base-runtime" / runtime
                manifest["replacements"][runtime] = dict(base_sha256=sha(native.read_bytes()) if native.exists() else None,
                                                          sha256=sha(raw))
        else:
            manifest["support_files"][rel] = sha(raw)
    # Seal previously implicit controller dependencies as well.
    base = baseline()
    for rel, raw in base.items():
        if not rel.startswith("overlay/") and rel != "overlay-manifest.json":
            manifest["support_files"][rel] = sha(payload.get(rel, raw))
    manifest["semantics"]["moe_boundary"] = (
        "UNQUALIFIED default-off SCREEN1B_MOE_BOUNDARY=1 diagnostic; TP4/EP4 profile only; "
        "watcher-gated queue drains, raw/remapped routing, owned rows/workspaces and eleven pointer receipts; "
        "nonlocal zero-return precedes table access only when enabled; native USM/context unknown")
    payload["overlay-manifest.json"] = (json.dumps(manifest, indent=2, ensure_ascii=False)+"\n").encode()
    pins, lines = {}, []
    for rel, raw in sorted(payload.items()):
        old = before(rel)
        if old == raw:
            continue
        pins[rel] = dict(before_sha256=sha(old) if old is not None else None, after_sha256=sha(raw))
        lines.extend(difflib.unified_diff((old or b"").decode().splitlines(keepends=True), raw.decode().splitlines(keepends=True),
                     fromfile="a/"+rel if old is not None else "/dev/null", tofile="b/"+rel))
    metadata = dict(schema="screen1b.unapplied-moe-boundary-patch.v1", applied=False,
                    base_revision=BASE_REVISION, base_manifest_sha256=sha(before("overlay-manifest.json")),
                    image=json.loads(before("image-plan.json"))["image"], enable_variable="SCREEN1B_MOE_BOUNDARY=1",
                    files=pins, baseline_files={rel:sha(raw) for rel,raw in sorted(base.items())},
                    native_base_sources={str(p.relative_to(HERE / "base-runtime")): sha(p.read_bytes())
                                         for p in sorted((HERE / "base-runtime").rglob("*.py"))})
    return {"copies/overlay-manifest.json": payload["overlay-manifest.json"],
            "boundary.patch": "".join("\n" if line == " \n" else line for line in lines).encode(),
            "patch-manifest.json": (json.dumps(metadata, indent=2, ensure_ascii=False)+"\n").encode()}


def check():
    for rel, raw in artifacts().items():
        if not (HERE / rel).is_file() or (HERE / rel).read_bytes() != raw:
            raise RuntimeError("stale diagnostic artifact: "+rel)


def stage(destination):
    if os.environ.get("SCREEN1B_MOE_BOUNDARY") != "1":
        raise RuntimeError("staging requires SCREEN1B_MOE_BOUNDARY=1")
    check()
    destination = Path(destination).resolve()
    if destination == REPO or REPO in destination.parents or destination.exists():
        raise RuntimeError("stage must be a fresh directory outside the repository")
    payload = baseline()
    for p in COPIES.rglob("*"):
        if p.is_file() and p.suffix in (".py", ".sh", ".json"):
            payload[str(p.relative_to(COPIES))] = p.read_bytes()
    destination.mkdir(parents=True)
    try:
        for rel, raw in payload.items():
            path = destination / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        # Hash validation only; no runtime import, patch application or launch.
        import importlib.util
        spec = importlib.util.spec_from_file_location("boundary_apply", destination / "apply_overlay.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.verify_package(destination)
        (destination / "diagnostic-stage.json").write_text(json.dumps(dict(
            source_repo=str(REPO), base_revision=BASE_REVISION,
            patch_manifest_sha256=sha((HERE / "patch-manifest.json").read_bytes()),
            overlay_manifest_sha256=sha((destination / "overlay-manifest.json").read_bytes())), indent=2)+"\n")
    except BaseException:
        shutil.rmtree(destination)  # only this newly-created staging directory
        raise
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true")
    group.add_argument("--stage", type=Path)
    args = parser.parse_args()
    if args.stage:
        print(stage(args.stage))
    elif args.check:
        check()
        print("Frozen diagnostic variant verified")
    else:
        for rel, raw in artifacts().items():
            (HERE / rel).write_bytes(raw)
        print("Frozen diagnostic variant sealed; production overlay unchanged")
