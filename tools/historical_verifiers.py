"""CPU-only identity checks for frozen verifier recovery; never import verifiers."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess


ROOTS = ("repro", "experiments", "scripts", "tools")
PIN = re.compile(
    r"sha256sum\s+(?:--\s+)?[\"']?(?:\$\{?repo(?:_root)?\}?/|\$\{?ROOT\}?/)?"
    r"((?:repro|experiments|scripts|tools|configs|data|patches)/[^\"'$\s|]+)[\"']?"
    r"[^=\n]{0,80}==\s*[\"']?([0-9a-f]{64})"
)
HASH_TOKEN = re.compile(r"[0-9a-f]{64}|[0-9a-f]{40}")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def relative_file(root: Path, value: str) -> Path:
    """Reject absolute paths, traversal and symlinks, including parent symlinks."""
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError(f"invalid repository path: {value!r}")
    rel = PurePosixPath(value)
    if rel.is_absolute() or ".." in rel.parts or rel.as_posix() != value:
        raise ValueError(f"invalid repository path: {value!r}")
    target = root
    for part in rel.parts:
        target = target / part
        if target.is_symlink():
            raise ValueError(f"symlink is not an immutable input: {value}")
    return target


def verified_bytes(root: Path, path: str, sha: str) -> bytes:
    if not isinstance(sha, str) or re.fullmatch(r"[0-9a-f]{64}", sha) is None:
        raise ValueError(f"invalid SHA256 for {path}")
    data = relative_file(root, path).read_bytes()
    if digest(data) != sha:
        raise ValueError(f"SHA256 differs: {path}")
    return data


def tracked_shells(root: Path) -> list[str]:
    result = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--", *ROOTS],
                            capture_output=True, check=False)
    if result.returncode:
        raise ValueError("git ls-files failed: " + result.stderr.decode(errors="replace"))
    return sorted({p for p in result.stdout.decode().split("\0") if p.endswith(".sh")})


def scan_pins(root: Path) -> list[dict]:
    rows = []
    cache = {}
    for holder in tracked_shells(root):
        data = relative_file(root, holder).read_bytes()
        for match in PIN.finditer(data.decode(errors="replace")):
            target, expected = match.groups()
            if target not in cache:
                path = relative_file(root, target)
                cache[target] = digest(path.read_bytes()) if path.is_file() else None
            actual = cache[target]
            rows.append({"holder": holder, "holder_sha256": digest(data),
                         "target": target, "expected_sha256": expected,
                         "actual_sha256": actual,
                         "status": "absent" if actual is None else
                                   "match" if actual == expected else "drift"})
    return rows


def row_key(row: dict) -> tuple[str, str, str]:
    return row["holder"], row["target"], row["expected_sha256"]


def load_manifest(path: Path) -> dict:
    try:
        manifest = json.loads(path.read_text())
        if manifest["schema"] != "lab.historical-verifier-recovery.v1":
            raise ValueError("unsupported historical manifest schema")
        for name in ("versions", "pins", "maintained_replays"):
            if not isinstance(manifest[name], list):
                raise ValueError(f"manifest {name} must be a list")
        return manifest
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid historical manifest: {exc}") from exc


def validate_manifest(root: Path, path: Path, rows: list[dict]) -> dict:
    """An exact inventory, never a wildcard waiver for a path or old digest.

    Git blob IDs are verified from snapshot bytes, so shallow clones work.
    Original commit/path provenance was checked during extraction. No history
    fetch is attempted in validation; see pin-audit.md for its read-only proof.
    """
    manifest = load_manifest(path)
    try:
        versions = {}
        for version in manifest["versions"]:
            sha = version["sha256"]
            key = version["original_path"], sha
            if key in versions:
                raise ValueError(f"duplicate historical version: {key}")
            data = verified_bytes(root, version["snapshot"], sha)
            blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
            if blob != version["git_blob"]:
                raise ValueError(f"Git blob differs: {version['snapshot']}")
            if re.fullmatch(r"[0-9a-f]{40}", version["origin_commit"]) is None:
                raise ValueError("invalid origin commit")
            relative_file(root, version["original_path"])
            versions[key] = version
        current = {row_key(row): row for row in rows if row["status"] != "match"}
        recorded = set()
        used_versions = set()
        recoverable = blocked = 0
        for entry in manifest["pins"]:
            key = row_key(entry)
            if key in recorded:
                raise ValueError(f"duplicate historical pin: {entry['holder']}")
            recorded.add(key)
            if key not in current:
                raise ValueError(f"stale historical pin: {entry['holder']}")
            row = current[key]
            if row["holder_sha256"] != entry["holder_sha256"]:
                raise ValueError(f"historical holder SHA256 differs: {entry['holder']}")
            # An absent shared file is a new defect, even if history is recoverable.
            if row["status"] != "drift":
                raise ValueError(f"historical target absent: {entry['target']}")
            version_key = entry["target"], entry["expected_sha256"]
            if entry["disposition"] == "recoverable":
                if version_key not in versions:
                    raise ValueError(f"no exact historical version: {entry['holder']}")
                used_versions.add(version_key)
                recoverable += 1
            elif entry["disposition"] == "blocked":
                if version_key in versions or not entry["reason"].strip() or not entry["evidence"]:
                    raise ValueError(f"invalid blocked pin: {entry['holder']}")
                for evidence in entry["evidence"]:
                    verified_bytes(root, evidence["path"], evidence["sha256"])
                blocked += 1
            else:
                raise ValueError(f"unknown disposition: {entry['disposition']}")
        extra = current.keys() - recorded
        if extra:
            raise ValueError(f"unreviewed pin drift: {sorted(extra)[0]}")
        if used_versions != versions.keys():
            raise ValueError("unreferenced historical version in manifest")
        seen_replays = set()
        for replay in manifest["maintained_replays"]:
            if replay["pin_file"] in seen_replays:
                raise ValueError("duplicate maintained replay")
            seen_replays.add(replay["pin_file"])
            descriptor = verified_bytes(root, replay["pin_file"], replay["pin_file_sha256"])
            pins = dict(line.split("=", 1) for line in descriptor.decode().splitlines())
            verified_bytes(root, replay["verifier"], pins["sha256"])
            for field in ("maker", "identity"):
                verified_bytes(root, replay[field], replay[field + "_sha256"])
        return {"recoverable": recoverable, "blocked": blocked,
                "versions": len(versions), "maintained_replays": len(seen_replays)}
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError(f"invalid historical manifest entry: {exc}") from exc


def redirect_client(data: bytes, target: str, snapshot: str, expected: str) -> bytes:
    """Same two-reference redirection as the maintained frozen replay makers."""
    text = data.decode()
    if text.count(target) != 2 or PIN.findall(text).count((target, expected)) != 1:
        raise ValueError("expected exactly the verifier hash check and invocation")
    changed = text.replace(target, snapshot)
    if HASH_TOKEN.findall(changed) != HASH_TOKEN.findall(text):
        raise ValueError("verifier redirection changed historical hash tokens")
    return changed.encode()


def prepare_client(root: Path, manifest_path: Path, holder: str, output: Path) -> dict:
    """Prepare review material only: no shell, verifier imports, chmod +x or launch."""
    manifest = load_manifest(manifest_path)
    # Check the whole catalog, including new drift, before writing anything.
    validate_manifest(root, manifest_path, scan_pins(root))
    entries = [entry for entry in manifest["pins"] if entry["holder"] == holder]
    if len(entries) != 1:
        raise ValueError("choose exactly one catalogued historical client")
    entry = entries[0]
    if entry["disposition"] != "recoverable":
        raise ValueError("historical client is blocked: " + entry["reason"])
    version = next(v for v in manifest["versions"]
                   if (v["original_path"], v["sha256"]) ==
                   (entry["target"], entry["expected_sha256"]))
    original = verified_bytes(root, holder, entry["holder_sha256"])
    verifier = verified_bytes(root, version["snapshot"], entry["expected_sha256"])
    derived = redirect_client(original, entry["target"], version["snapshot"],
                              entry["expected_sha256"])
    # Keep generated copies out of pin scans and away from frozen packet paths.
    output = output.absolute()
    if output.exists() or output.is_symlink():
        raise ValueError(f"output must be a new directory: {output}")
    if not output.parent.is_dir() or output.parent.resolve() != output.parent:
        raise ValueError("output parent must exist and must not traverse symlinks")
    if output.is_relative_to(root.resolve()):
        raise ValueError("review output must be outside the repository")
    receipt = {
        "schema": "lab.historical-verifier-preparation.v1",
        "status": "prepared-for-review-only",
        "launch_ready": False,
        "manifest_sha256": digest(manifest_path.read_bytes()),
        "source": holder, "source_sha256": digest(original),
        "verifier": version,
        "derivative_sha256": digest(derived),
        "historical_hash_tokens_unchanged": True,
        "path_references_changed": 2,
        "current_md_sha256": digest((root / "CURRENT.md").read_bytes()),
        "constraints": [
            "This is a client/verifier review artifact, not a complete replay packet.",
            "Frozen supervisors, generators and manifests still pin the original client SHA256.",
            "Do not substitute this derivative into its frozen parent chain; use a reviewed successor generator.",
            "Ports, attempt IDs, hardcoded host paths, output locations and all other gates remain historical.",
            "Other variable-held and absolute-path pins and runtime dependencies were not qualified here.",
            "Consult CURRENT.md and subsequent owner/host acceptance receipts for live gates; preparation grants no launch permission.",
            "No historical client, shell generator or verifier was executed or imported."
        ],
        "files": {"client-original.sh.txt": digest(original),
                  "client-for-review.sh.txt": digest(derived),
                  "verifier.py.txt": digest(verifier)},
    }
    output.mkdir(mode=0o700)
    for name, data in (("client-original.sh.txt", original),
                       ("client-for-review.sh.txt", derived), ("verifier.py.txt", verifier),
                       ("receipt.json", (json.dumps(receipt, indent=2) + "\n").encode())):
        destination = output / name
        with destination.open("xb") as handle:
            handle.write(data)
        destination.chmod(0o444)
    return receipt
