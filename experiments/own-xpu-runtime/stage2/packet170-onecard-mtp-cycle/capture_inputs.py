#!/usr/bin/env python3
"""Preserve ignored receipt inputs as exact compressed bytes, never model data."""
import gzip
import hashlib
import json
from pathlib import Path
import resource
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def main():
    resource.setrlimit(resource.RLIMIT_AS, (2_000_000_000, 2_000_000_000))
    pins = json.loads((HERE / "cycle.json").read_text())["sources_sha256"]
    tracked = set(subprocess.check_output(["git", "ls-files", "--", *pins],
                                         cwd=ROOT, stdin=subprocess.DEVNULL, text=True).splitlines())
    records = {}
    dest = HERE / "inputs"
    dest.mkdir(exist_ok=True)
    for path, expected in pins.items():
        if path in tracked or path.startswith(str(HERE.relative_to(ROOT))):
            continue
        source = ROOT / path
        assert source.suffix in {".json", ".jsonl"} and source.stat().st_size < 10_000_000
        data = source.read_bytes()
        assert hashlib.sha256(data).hexdigest() == expected
        archive = dest / (expected + ".gz")
        packed = gzip.compress(data, mtime=0)
        assert gzip.decompress(packed) == data
        archive.write_bytes(packed)
        records[path] = dict(archive=str(archive.relative_to(HERE)), original_bytes=len(data),
                             original_sha256=expected, archive_sha256=hashlib.sha256(packed).hexdigest())
    (HERE / "inputs.json").write_text(json.dumps(dict(schema="packet170.exact-receipt-snapshots.v1",
        purpose="Ignored native receipts required for CPU reproduction; exact bytes, no model payloads",
        files=records), indent=2, sort_keys=True)+"\n")
    print(json.dumps(dict(snapshots=len(records), compressed_bytes=sum(x.stat().st_size for x in dest.iterdir()))))


if __name__ == "__main__":
    main()
