#!/usr/bin/env python3
"""Read every rg-visible repository DO-NOT-REPEAT; exclude this new packet."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import resource
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def main():
    resource.setrlimit(resource.RLIMIT_AS, (2_000_000_000, 2_000_000_000))
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    out = HERE / "dnr-audit.json"
    if args.check:
        manifest = json.loads(out.read_text())
        paths = [x["path"] for x in manifest["files"]]
        retained = manifest["retained_untracked_inputs"]
    else:
        paths = subprocess.check_output(
            ["rg", "--files", "--hidden", "-g", "*DO-NOT-REPEAT*", "-g", "!.git"],
            cwd=ROOT, stdin=subprocess.DEVNULL, text=True).splitlines()
        paths = sorted(p for p in paths if "packet170-onecard-mtp-cycle/" not in p)
        tracked = set(subprocess.check_output(["git", "ls-files", "--", *paths],
                     cwd=ROOT, stdin=subprocess.DEVNULL, text=True).splitlines())
        retained = {p: (ROOT / p).read_bytes().decode() for p in paths if p not in tracked}
    pattern = re.compile(r"mtp|draft|speculat|verify|depth", re.I)
    files, matches = [], []
    for p in paths:
        b = (ROOT / p).read_bytes() if (ROOT / p).exists() else retained[p].encode()
        lines = [(i, s) for i, s in enumerate(b.decode().splitlines(), 1) if pattern.search(s)]
        files.append(dict(path=p, sha256=hashlib.sha256(b).hexdigest(), matches=len(lines)))
        matches.extend(f"{p}:{i}:{s}" for i,s in lines)
    plan = "experiments/own-xpu-runtime/stage2/packet147-lever-synthesis/PLAN.md"
    result = dict(schema="packet170.negative-history-audit.v1", pattern=pattern.pattern,
                  scope="All rg-visible repository DO-NOT-REPEAT files, including hidden paths; new packet excluded",
                  files=files, file_count=len(files), matching_lines=len(matches),
                  retained_untracked_inputs=retained,
                  packet147_negative_index_exists=any("packet147" in p for p in paths),
                  packet147_decision_record=plan+":290",
                  packet147_sha256=hashlib.sha256((ROOT / plan).read_bytes()).hexdigest())
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    text = "\n".join(matches) + "\n"
    if args.check:
        assert out.read_text() == encoded, "An audited negative index changed"
        assert (HERE / "dnr-scan.txt").read_text() == text
    else:
        out.write_text(encoded)
        (HERE / "dnr-scan.txt").write_text(text)
    print(json.dumps(dict(check=args.check, files=len(files), matching_lines=len(matches))))


if __name__ == "__main__":
    main()
