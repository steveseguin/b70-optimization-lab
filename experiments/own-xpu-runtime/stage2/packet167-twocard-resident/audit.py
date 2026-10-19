"""Read saved two-card receipts only; never import a runtime or open weights."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
STAGE = ROOT / "experiments/own-xpu-runtime/stage2"


def relative(path):
    return str(path.relative_to(ROOT))


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def scan(path):
    result = dict(path=relative(path), sha256=digest(path), rows=0,
                  major_faults=0, minor_faults=0, nonzero_rows=[])
    with path.open() as stream:
        for number, line in enumerate(stream, 1):
            row = json.loads(line)
            # Missing telemetry is not zero. These streams must all be native
            # token timing streams with per-operation getrusage differences.
            for key in ("process_major_faults", "process_minor_faults"):
                value = row[key]
                assert type(value) is int and value >= 0, (path, number, key)
            result["rows"] += 1
            result["major_faults"] += row["process_major_faults"]
            result["minor_faults"] += row["process_minor_faults"]
            if row["process_major_faults"]:
                result["nonzero_rows"].append(dict(line=number, receipt=row))
    assert result["rows"], f"empty required stream: {path}"
    return result


def group(paths, expected):
    paths = sorted(paths)
    assert len(paths) == expected, (len(paths), expected)
    rows = [scan(p) for p in paths]
    return dict(stream_count=len(rows), rows=sum(r["rows"] for r in rows),
                major_faults=sum(r["major_faults"] for r in rows),
                minor_faults=sum(r["minor_faults"] for r in rows),
                streams=rows)


def main():
    windows = []
    chain = STAGE / "packet136-record-bundle/build/device-cards01-a"
    for name in ("W2m", "WS", "WSs", "WS128x", "WS128"):
        run = chain / name / "run"
        scopes = {}
        for rank in ("rank0", "rank1"):
            if name == "W2m":
                paths = [run / rank / "timings.jsonl"]
                scopes[rank] = group(paths, 1)
            else:
                # Per-request archived streams only: live rank and after-suite
                # copies are excluded, as are the distinct warm-up streams.
                scopes[rank] = group(run.glob(f"repeat-1/*/{rank}/timings.jsonl"), 12)
                scopes[f"warmup_{rank}"] = group([run / "warmup" / rank / "timings.jsonl"], 1)
        windows.append(dict(window=f"packet136/{name}", path=relative(run), scopes=scopes))

    for packet, prefix, first in (("packet163-full-gate", "full512", "prefill512"),
                                  ("packet165-warm-prefill", "warm512", "incident-retrospective")):
        for attempt in ("a", "b"):
            win = STAGE / packet / "two-card/evidence" / f"device-{prefix}-B-{attempt}"
            scopes = {}
            for rank in ("rank0", "rank1"):
                scopes[rank] = group((win / "run/requests").glob(f"*/{rank}/timings.jsonl"), 13)
            cold = []
            for rank in ("rank0", "rank1"):
                path = win / "run/requests" / first / rank / "timings.jsonl"
                with path.open() as stream:
                    row = json.loads(next(stream))
                assert row["position"] == 0 and row["speculative"] is False
                cold.append(row["process_major_faults"])
            total = sum(s["major_faults"] for s in scopes.values())
            windows.append(dict(window=f"{packet}/{attempt}", path=relative(win), scopes=scopes,
                                first_request=first, first_operation_major_faults_by_rank=cold,
                                other_operations_major_faults=total-sum(cold)))

    evidence_pins = {}
    lookup_receipts = []
    for path in sorted(chain.glob("*/run/**/lookup-residency.json")) + sorted(STAGE.glob("packet16[35]-*/two-card/evidence/device-*/run/ranks/rank*/lookup-residency.json")):
        row = json.loads(path.read_text())
        lookup_receipts.append(dict(path=relative(path), receipt=row))
        evidence_pins[relative(path)] = digest(path)
    source_names = ["packet136-record-bundle/main.cpp", "packet136-record-bundle/rank.hpp",
                    "packet136-record-bundle/mtp.hpp", "packet2/loader/gguf.cpp",
                    "packet3/step/plan.hpp"]
    for name in source_names:
        path = STAGE / name
        evidence_pins[relative(path)] = digest(path)
    for rank in ("rank0", "rank1"):
        path = chain / "WS128/run/ranks" / rank / "plan.json"
        evidence_pins[relative(path)] = digest(path)
    for pattern in ("packet151-*", "packet153-*", "packet156-*", "packet157-*", "packet158-*",
                    "packet160-*", "packet161-*", "packet162-*", "packet164-*"):
        for path in sorted(STAGE.glob(f"{pattern}/DO-NOT-REPEAT.md")):
            evidence_pins[relative(path)] = digest(path)
    report = dict(schema="packet167.lookup-applicability.v1", device_executed=False,
                  decision="close under zero-fault record-window stop rule; no candidate built",
                  scope="Saved native per-operation process counters, not whole-process lifetime or fault-address attribution",
                  unmeasured_chain_windows=["K0", "K1a", "K1b", "K2", "KD", "W0p"],
                  unmeasured_reason="No equivalent native process-major-fault stream audited; not assigned zero",
                  windows=windows, lookup_receipts=lookup_receipts, pins=evidence_pins)
    out = HERE / "evidence/fault-audit.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    for window in windows:
        counts = {k: v["major_faults"] for k, v in window["scopes"].items()}
        print(window["window"], counts)


if __name__ == "__main__":
    main()
