"""Summarize the audited per-segment XPU event profile by segment kind.

The breakable-graph replay is 291 intervals timed with XPU events on the
current stream: 146 graph segments, 48 attention boundaries and 97 collective
boundaries. Unlike the host-call profile, these are *device* durations, which
is what distinguishes real work from host submission.

That distinction has repeatedly mattered on this stack. The host-call profile
attributed 8.118 ms to the 48 attention boundaries; retiring all 48 of them
saved 0.67 ms, because the attributed time was the attention kernel rather than
the boundary. Device intervals do not have that failure mode.

Usage: analyze_laguna_segment_event_profile.py <root-with-rankN.json>
"""

import json
import pathlib
import statistics
import sys


def summarize(payload):
    by_kind = {}
    for seg in payload["segments"]:
        by_kind.setdefault(seg["kind"], []).append(seg["duration_ns"])
    total = payload["total_duration_ns"]
    rows = []
    for kind, values in sorted(by_kind.items()):
        rows.append(
            (
                kind,
                len(values),
                sum(values) / 1e6,
                statistics.median(values) / 1e3,
                max(values) / 1e3,
                sum(values) / total * 100 if total else 0.0,
            )
        )
    return rows, total


def main():
    root = pathlib.Path(sys.argv[1])
    files = sorted(root.glob("rank*.json"))
    if not files:
        raise SystemExit(f"no rank*.json under {root}")
    for path in files:
        payload = json.loads(path.read_text())
        if "segments" not in payload:
            key = next(
                (k for k, v in payload.items()
                 if isinstance(v, list) and v and isinstance(v[0], dict)
                 and "duration_ns" in v[0]),
                None,
            )
            if key is None:
                raise SystemExit(f"{path.name}: no per-segment durations found; "
                                 f"keys are {sorted(payload)}")
            payload["segments"] = payload[key]
        rows, total = summarize(payload)
        print(f"\n{path.name}  batch={payload.get('batch_descriptor')}  "
              f"total={total / 1e6:.3f} ms")
        print(f"  {'kind':<12}{'count':>7}{'sum ms':>10}{'median us':>12}"
              f"{'max us':>10}{'share':>8}")
        for kind, count, total_ms, med_us, max_us, share in rows:
            print(f"  {kind:<12}{count:>7}{total_ms:>10.3f}{med_us:>12.1f}"
                  f"{max_us:>10.1f}{share:>7.1f}%")


if __name__ == "__main__":
    main()
