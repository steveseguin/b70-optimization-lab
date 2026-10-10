#!/usr/bin/env python3
"""Read saved LTX client evidence only; emit the continuation ledger as JSON.

Run with nice -n 19 env OMP_NUM_THREADS=2 <venv>/bin/python -B. No runtime imports,
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


def period_evidence(segments, pacing_segments):
    """Never call a sink-paced interval model production time.

    The primary window is the uninterrupted prefix before the first hold in
    each client invocation. Later hold-free periods are a separate diagnostic:
    skipping individual holds cannot undo their scheduling/temperature effects.
    All maintenance, cuts and slow intervals in each prefix remain included.
    """
    raw, prefix, hold_free, gaps = [], [], [], []
    previous = None
    for segment, holds in zip(segments, pacing_segments):
        if previous and segment:
            gaps.append({"from_seq": previous[0], "to_seq": segment[0][0],
                         "seconds": round(segment[0][1] - previous[1], 3)})
        first_hold_after = holds[0]["after_seq"] if holds else None
        blocked = {hold["after_seq"] for hold in holds}
        for (pq, pt), (q, t) in zip(segment, segment[1:]):
            if q != pq + 1 or q < 10:
                continue
            row = [q, round(t - pt, 3)]
            raw.append(row)
            if not holds or (first_hold_after is not None and q <= first_hold_after):
                prefix.append(row)
            if pq not in blocked:
                hold_free.append(row)
        if segment:
            previous = segment[-1]
    return raw, prefix, hold_free, gaps


def analyze(root, run_root):
    runs = []
    files = {}
    pattern = re.compile(r"s(117|118b|119|120|121|123b|124|125|126|127|128|129|130|131|132|133b?|134|135|137|138)-")
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
                                  "verdict_id": None, "client_segments": [], "pacing_segments": [], "incidents": [],
                                  "manifest_rows": []}
                current = local[key]
                current["client_segments"].append([])
                current["pacing_segments"].append([])
            if current is None:
                continue
            if "] throttle:" in line:
                segment = current["client_segments"][-1]
                start_ns = re.search(r"start_mono_ns=(\d+)", line)
                current["pacing_segments"][-1].append({
                    "after_seq": segment[-1][0] if segment else None,
                    "start_log": line, "end_log": None,
                    "start_mono_ns": int(start_ns[1]) if start_ns else None,
                    "duration_ns": None})
            if "] throttle released after " in line or "] throttle interrupted after " in line:
                holds = current["pacing_segments"][-1]
                if not holds or holds[-1]["end_log"] is not None:
                    raise ValueError(f"Pacing release without matching start: {folder}")
                hold = holds[-1]
                hold["end_log"] = line
                duration = re.search(r"start_mono_ns=(\d+) end_mono_ns=(\d+) duration_ns=(\d+)", line)
                if duration:
                    start, end, ns = map(int, duration.groups())
                    if start != hold["start_mono_ns"] or end - start != ns or ns < 0:
                        raise ValueError(f"Inconsistent monotonic pacing duration: {folder}")
                    hold.update(end_mono_ns=end, duration_ns=ns)
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
            rows, prefix, hold_free, gaps = period_evidence(run["client_segments"], run["pacing_segments"])
            run["periods_destination_seq_seconds"] = rows
            run["raw_statistics"] = summary(rows)
            run["unthrottled_prefix_periods_destination_seq_seconds"] = prefix
            run["statistics"] = summary(prefix)
            run["hold_free_diagnostic_statistics"] = summary(hold_free)
            run["pacing_hold_count"] = sum(map(len, run["pacing_segments"]))
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
    return {"schema": "ltx-continuation-ledger-v2", "method": {
        "period": "consecutive submitted timestamps in client.log; destination stream_seq >= 10",
        "primary": "all consecutive periods ending before the first pacing-hold start in each client invocation; full prefix, no outlier trimming",
        "raw": "all within-invocation periods, including client pacing holds; delivery cadence, not production speed",
        "hold_free_diagnostic": "omit only intervals containing a logged hold; diagnostic only because earlier holds can affect subsequent scheduling",
        "pacing": "legacy start/release logs identify excluded intervals; never subtract rounded legacy durations; precise logs bind monotonic nanosecond durations",
        "restart_policy": "never bridge client headers; gaps retained separately; no within-segment outlier trimming",
        "p90": "nearest rank ceil(0.9*n), no interpolation", "parity": "destination stream_seq",
        "video": "(frames-1)/24 new seconds, repeated anchor excluded", "timestamps": "log milliseconds",
    }, "source_files": files, "runs": runs}


def render_pacing_markdown(data):
    lines = [
        '# Continuation periods with client pacing separated', '',
        'Generated from the [v2 saved-evidence snapshot](../data/ltx25-continuation-stream-2026-10-10-pacing-v2.json). '
        'Its source hashes bind all input bytes. No new native work was run.', '',
        'Primary statistics use every consecutive submit-to-submit interval with destination sequence >=10 '
        'that ends before the first pacing hold in each client invocation. A restart starts a new segment; '
        'no restart gap is bridged. The full prefix is retained, including cuts, maintenance and slow intervals. '
        'This is an early unthrottled window, not an estimate of sustained unthrottled performance.', '',
        'Raw statistics retain every within-invocation interval, including client holds. The hold-free diagnostic '
        'drops only intervals containing a hold; later periods can still reflect prior pacing or drift. '
        'No historic duration is subtracted: legacy hold durations were rounded to 0.1 seconds. '
        'New precise logs contain monotonic nanosecond start, end and duration, including interrupted holds. '
        'These are client observations, not server-side chain timers.', '',
        '| Client / identity | Holds | Raw n / median s | Early unthrottled n / median / mean / p90 s | Hold-free diagnostic n / median s |',
        '| --- | ---: | --- | --- | --- |',
    ]
    for run in data['runs']:
        raw, primary, diagnostic = (run[k] for k in ('raw_statistics', 'statistics', 'hold_free_diagnostic_statistics'))
        if not raw:
            continue
        brief = lambda s: f"{s['n']} / {s['median_s']:.4f}" if s else 'not measured'
        main = (f"{primary['n']} / {primary['median_s']:.4f} / {primary['mean_s']:.4f} / {primary['p90_s']:.4f}"
                if primary else 'not measured')
        lines.append(f"| `{Path(run['work_dir']).name}` / `{run['identity_prefix']}` | {run['pacing_hold_count']} | {brief(raw)} | {main} | {brief(diagnostic)} |")
    return '\n'.join(lines) + '\n'


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("/home/steve/ltx-stream"))
    parser.add_argument("--run-root", type=Path, default=Path("/mnt/fast-ai/bench-results/ltx25-baseline-20260913"))
    parser.add_argument("--snapshot", type=Path, help="render an existing v2 JSON snapshot without rereading source logs")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args()
    data = json.loads(args.snapshot.read_text()) if args.snapshot else analyze(args.root, args.run_root)
    print(render_pacing_markdown(data) if args.format == 'markdown' else json.dumps(data, indent=2, ensure_ascii=False), end='\n' if args.format == 'json' else '')
