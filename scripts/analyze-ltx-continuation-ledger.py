#!/usr/bin/env python3
"""Read saved LTX client evidence only; emit the continuation ledger as JSON.

Run with nice -n 19 env OMP_NUM_THREADS=2 python3 -B. No runtime imports,
devices, network, subprocesses, or evidence writes. stdout is the only output.
"""
import argparse
import hashlib
import json
import math
import re
import statistics
from pathlib import Path


def summary(rows):
    values = sorted(row[1] for row in rows)
    if not values:
        return None
    parity = [[v for q, v in rows if q % 2 == p] for p in (0, 1)]
    return {
        "n": len(values),
        "median_s": statistics.median(values),
        "mean_s": statistics.mean(values),
        "p90_s": values[math.ceil(0.9 * len(values)) - 1],
        "even_destination_median_s": statistics.median(parity[0]) if parity[0] else None,
        "odd_destination_median_s": statistics.median(parity[1]) if parity[1] else None,
        "max_s": max(values),
    }


def analyze(root, run_root):
    runs = []
    files = {}
    pattern = re.compile(r"s(117|118b|119|120|121|123b|124|125|126|127|128|129|131)-")
    for folder in sorted(root.iterdir()):
        if not pattern.match(folder.name) or not (folder / "client.log").is_file():
            continue
        sources = {}
        for name in ("client.log", "manifest.jsonl"):
            path = folder / name
            if path.is_file():
                raw = path.read_bytes()
                sources[name] = raw.decode()
                files[str(path)] = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        local = {}
        current = None
        epoch = 0
        last = None
        for line in sources["client.log"].splitlines():
            header = re.search(r"server (encoder-server-\S+) identity (\w+).*? frames (\d+).*? packet (\w+)", line)
            if header:
                name, identity, frames, packet = header.groups()
                key = (name, identity)
                if key not in local:
                    local[key] = {"packet": packet, "frames": int(frames), "run_name": name,
                                  "identity_prefix": identity, "work_dir": str(folder),
                                  "verdict_id": None, "client_segments": [], "incidents": [],
                                  "manifest_rows": []}
                current = local[key]
                current["client_segments"].append([])
            if current is None:
                continue
            verdict = re.search(r"qualification verified: verdict (\w+)", line)
            if verdict:
                current["verdict_id"] = verdict[1]
            if any(word in line for word in ("STOPPED", "signal 2:", "clean stop:")):
                current["incidents"].append(line)
            event = re.search(r"\[c112 (\d+):(\d+):([\d.]+)\] submitted stream\d+[a-z]*-s(\d+)", line)
            if event:
                h, m, sec, seq = event.groups()
                t = int(h) * 3600 + int(m) * 60 + float(sec)
                if last is not None and t < last:
                    epoch += 86400
                last = t
                current["client_segments"][-1].append([int(seq), round(t + epoch, 3)])
        for line in sources.get("manifest.jsonl", "").splitlines():
            row = json.loads(line)
            matches = [r for r in local.values() if row["server_identity_sha256"].startswith(r["identity_prefix"])]
            if len(matches) != 1:
                raise ValueError(f"Manifest identity not uniquely bound: {folder} {row['seq']}")
            keep = ("seq", "stream_seq", "frames", "seconds", "new_frames", "seed", "scene", "cone_equal",
                    "images_sha256", "last_frame_sha256", "anchor_sha256", "preview_sha256")
            matches[0]["manifest_rows"].append({k: row.get(k) for k in keep})
            if "server_options" in row:
                options = row["server_options"]
                if "server_options" in matches[0] and matches[0]["server_options"] != options:
                    raise ValueError(f"Options changed within identity: {folder}")
                matches[0]["server_options"] = options
        for run in local.values():
            rows = []
            gaps = []
            previous = None
            for segment in run["client_segments"]:
                if previous and segment:
                    gaps.append({"from_seq": previous[0], "to_seq": segment[0][0],
                                 "seconds": round(segment[0][1] - previous[1], 3)})
                for (pq, pt), (q, t) in zip(segment, segment[1:]):
                    if q == pq + 1 and q >= 10:
                        rows.append([q, round(t - pt, 3)])
                if segment:
                    previous = segment[-1]
            run["periods_destination_seq_seconds"] = rows
            run["statistics"] = summary(rows)
            run["client_resume_gaps"] = gaps
            run["chunks_streamed"] = len(run["manifest_rows"])
            run["new_video_seconds_per_continuation"] = (run["frames"] - 1) / 24
            if run["statistics"]:
                run["statistics"]["median_work_seconds_per_video_second"] = run["statistics"]["median_s"] / run["new_video_seconds_per_continuation"]
            if not run["verdict_id"] and not run["incidents"]:
                run["pending_client_log_snapshot"] = sources["client.log"]
                files[str(folder / "client.log")]["may_append"] = True
            runs.append(run)
    comparisons = {
        "s118b-live01": "s117-live01", "s118b-dg1-live01": "s118b-live01",
        "s118b-live02": "s118b-live01", "s119-live01": "s118b-live02",
        "s118b-live03": "s118b-live02", "s120-live01": "s118b-live03",
        "s121-live02": "s121-live01", "s123b-live01": "s121-live02",
        "s123b-live02": "s123b-live01", "s123b-legacy-live01": "s121-live02",
        "s124-live01": "s123b-legacy-live01", "s125-live01": "s123b-legacy-live01",
        "s126-live01": "s125-live01", "s127-live01": "s126-live01",
        "s128-live01": "s127-live01", "s128-gc60-live01": "s128-live01",
        "s129-live01": "s128-gc60-live01",
    }
    hashes = ("images_sha256", "last_frame_sha256", "anchor_sha256", "preview_sha256")
    by_folder = {Path(r["work_dir"]).name: r for r in runs}
    for run in runs:
        parent_name = comparisons.get(Path(run["work_dir"]).name)
        if parent_name:
            parent = by_folder[parent_name]
            keyed = {r["stream_seq"]: r for r in parent["manifest_rows"]}
            pairs = [(r, keyed[r["stream_seq"]]) for r in run["manifest_rows"] if r["stream_seq"] in keyed]
            for a, b in pairs:
                if any(a[k] != b[k] for k in ("frames", "seed", "scene")):
                    raise ValueError("Mismatched comparison identity")
            run["saved_manifest_comparison"] = {
                "reference_work_dir": parent["work_dir"], "shared_chunks": len(pairs),
                "matching_hashes": {k: sum(bool(a[k]) and a[k] == b[k] for a, b in pairs) for k in hashes},
                "scope": "saved digest comparison only; no new tensor or media reads",
            }
    for run in runs:
        run["cone_equal_counts"] = {str(v): sum(r["cone_equal"] is v for r in run["manifest_rows"]) for v in (True, False, None)}
        del run["manifest_rows"]
        if run["verdict_id"]:
            matches = []
            for path in sorted(run_root.glob(run["run_name"] + "*/stream-qualification-verdict.json")):
                raw = path.read_bytes()
                sha = hashlib.sha256(raw).hexdigest()
                if sha.startswith(run["verdict_id"]):
                    matches.append((path, raw, sha))
            if len(matches) != 1:
                raise ValueError(f"Verdict not uniquely bound: {run['work_dir']}")
            path, raw, sha = matches[0]
            verdict = json.loads(raw)
            files[str(path)] = {"bytes": len(raw), "sha256": sha}
            run["saved_run_dir"] = str(path.parent)
            run["qualification"] = {k: verdict.get(k) for k in
                                    ("passed", "exact_replay", "reference_check", "plan_sha256", "failures")}
        else:
            run["saved_run_dir"] = str(run_root / run["run_name"])
        for name, key in (("stream-launch-options.json", "launch_options"), ("stream-halt.json", "halt")):
            path = Path(run["saved_run_dir"]) / name
            if path.is_file():
                raw = path.read_bytes()
                files[str(path)] = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
                run[key] = json.loads(raw)
                if key == "launch_options" and "server_options" not in run:
                    run["server_options"] = run[key]["server_options"]
    return {"schema": "ltx-continuation-ledger-v1", "method": {
        "period": "consecutive submitted timestamps in client.log; destination stream_seq >= 10",
        "restart_policy": "never bridge client headers; gaps retained separately; no within-segment outlier trimming",
        "p90": "nearest rank ceil(0.9*n), no interpolation", "parity": "destination stream_seq",
        "video": "(frames-1)/24 new seconds, repeated anchor excluded", "timestamps": "log milliseconds",
    }, "source_files": files, "runs": runs}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("/home/steve/ltx-stream"))
    parser.add_argument("--run-root", type=Path, default=Path("/mnt/fast-ai/bench-results/ltx25-baseline-20260913"))
    args = parser.parse_args()
    print(json.dumps(analyze(args.root, args.run_root), indent=2, ensure_ascii=False))
