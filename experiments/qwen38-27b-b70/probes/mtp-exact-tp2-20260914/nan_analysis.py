#!/usr/bin/env python3
"""CPU-only NaN-semantics fixture and mode selection. No torch import.

The fixture is every ordered (rank-0 value, rank-1 value) pair from VALUES,
tiled across the gate's registered element counts. A mode is selected only if
it equals XCCL on every element, on both ranks, at every shape. Otherwise the
verdict says no single formulation matches and gives the smallest set of pairs
that refutes every mode. Mismatches are data; this module never raises on them.
"""
import argparse
from array import array
from collections import Counter
import hashlib
from itertools import combinations
import json
from pathlib import Path
import sys

SCHEMA = "neural.download.exact-tp2-nan-semantics.v1"
CLASS_SCHEMA = "neural.download.exact-tp2-nan-class.v1"
RULES = ("bit-exact", "nan-class")  # nan-class: user decision 2026-09-15, any two NaNs count as equal.
ELEMENTS_PER_ROW = 5120
SHAPES = (1, 2, 512, 4096)
MODES = ("m0", "m1", "m2", "m3")  # Selection preference order when several match.
MODE_CODES = {m: i for i, m in enumerate(MODES)}
MODE_DESCRIPTIONS = {"m0": "fp32 add, rank-0 operand first (Native04 arithmetic)",
                     "m1": "fp32 add, rank-1 operand first",
                     "m2": "sycl::half add, rank-0 operand first",
                     "m3": "sycl::half add, rank-1 operand first"}
ARMS = ("xccl",) + MODES
VALUES = (
    ("+qnan", 0x7e00), ("+qnan.1", 0x7e01), ("+qnan.3", 0x7e03), ("+qnan.max", 0x7fff),
    ("-qnan", 0xfe00), ("-qnan.2", 0xfe02), ("-qnan.max", 0xffff),
    ("+snan.1", 0x7c01), ("+snan.100", 0x7d00), ("-snan.1", 0xfc01), ("-snan.155", 0xfd55),
    ("+inf", 0x7c00), ("-inf", 0xfc00), ("+0", 0x0000), ("-0", 0x8000),
    ("+1", 0x3c00), ("-1", 0xbc00), ("+max", 0x7bff), ("-max", 0xfbff),
    ("+subnormal", 0x0001), ("-subnormal", 0x8001),
)
BITS = tuple(bits for _, bits in VALUES)
PAIRS = tuple((a, b) for a in BITS for b in BITS)
PERIOD = len(PAIRS)
if sys.byteorder != "little":
    raise RuntimeError("raw FP16 receipts are little-endian")


def is_nan(bits):
    return bits & 0x7c00 == 0x7c00 and bits & 0x03ff != 0


def is_quiet(bits):
    return is_nan(bits) and bool(bits & 0x0200)


def column(rank, n):
    """This rank's operand bits for n elements: pair i % PERIOD, operand rank."""
    if rank not in (0, 1) or n <= 0:
        raise ValueError("invalid column")
    period = array("H", (pair[rank] for pair in PAIRS))
    return (period * (n // PERIOD + 1))[:n]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def _chunks(data, step):
    return (data[i:i + step] for i in range(0, len(data), step))


def mismatch_count(a, b):
    """Element mismatches between two raw FP16 byte strings, collapsed by period."""
    if len(a) != len(b) or len(a) % 2:
        raise ValueError("raw FP16 length mismatch")
    if a == b:
        return 0
    total = 0
    for (x, y), k in Counter(zip(_chunks(a, 2 * PERIOD), _chunks(b, 2 * PERIOD))).items():
        if x != y:
            total += k * sum(u != v for u, v in zip(array("H", x), array("H", y)))
    return total


def class_mismatch_count(a, b):
    """Element mismatches when any two NaNs count as equal; every other bit must match."""
    if len(a) != len(b) or len(a) % 2:
        raise ValueError("raw FP16 length mismatch")
    if a == b:
        return 0
    total = 0
    for (x, y), k in Counter(zip(_chunks(a, 2 * PERIOD), _chunks(b, 2 * PERIOD))).items():
        if x != y:
            total += k * sum(u != v and not (is_nan(u) and is_nan(v)) for u, v in zip(array("H", x), array("H", y)))
    return total


def pair_outputs(raw):
    """Per-pair output bits from the first period, and whether all positions agree."""
    if len(raw) < 2 * PERIOD:
        raise ValueError("raw output shorter than one pair period")
    first = raw[:2 * PERIOD]
    consistent = all(chunk == first[:len(chunk)] for chunk in _chunks(raw, 2 * PERIOD))
    return list(array("H", first)), consistent


def first_mismatch(a, b):
    for index, (u, v) in enumerate(zip(array("H", a), array("H", b))):
        if u != v:
            return index
    return None


def evaluate(outputs, shapes=SHAPES):
    """outputs[rank][rows][arm] = raw bytes. Returns a machine-readable verdict."""
    if 1 not in shapes:
        raise ValueError("pair tables require the one-row shape")
    verdict = {"schema": SCHEMA, "status": "incomplete", "selected_mode": None,
               "matching_modes": [], "modes": MODE_DESCRIPTIONS, "errors": [],
               "values": [{"name": name, "bits": f"{bits:04x}"} for name, bits in VALUES]}
    for rank in (0, 1):
        for rows in shapes:
            for arm in ARMS:
                raw = outputs.get(rank, {}).get(rows, {}).get(arm)
                if not isinstance(raw, (bytes, bytearray)) or len(raw) != rows * ELEMENTS_PER_ROW * 2:
                    verdict["errors"].append(f"rank{rank} rows{rows} {arm}: missing or wrong length")
    if verdict["errors"]:
        return verdict
    agree = {rows: outputs[0][rows]["xccl"] == outputs[1][rows]["xccl"] for rows in shapes}
    verdict["xccl_ranks_agree"] = {str(k): v for k, v in agree.items()}
    counts = {m: {f"rank{r}": {str(rows): mismatch_count(outputs[r][rows][m], outputs[r][rows]["xccl"])
                               for rows in shapes} for r in (0, 1)} for m in MODES}
    verdict["mismatch_counts"] = counts
    verdict["elements_per_shape"] = {str(rows): rows * ELEMENTS_PER_ROW for rows in shapes}
    tables, dependent = {}, []
    for rank in (0, 1):
        for arm in ARMS:
            tables[(rank, arm)], _ = pair_outputs(outputs[rank][1][arm])
            for rows in shapes:
                if not pair_outputs(outputs[rank][rows][arm])[1]:
                    dependent.append({"rank": rank, "rows": rows, "arm": arm})
    verdict["position_dependent_outputs"] = dependent
    verdict["pair_table"] = [
        {"pair": j, "rank0": f"{a:04x}", "rank1": f"{b:04x}",
         **{f"{arm}_rank{r}": f"{tables[(r, arm)][j]:04x}" for arm in ARMS for r in (0, 1)}}
        for j, (a, b) in enumerate(PAIRS)]
    verdict["matching_modes"] = [m for m in MODES if all(v == 0 for r in counts[m].values() for v in r.values())]
    if not all(agree.values()):
        verdict["status"] = "xccl-ranks-disagree"
        return verdict
    if verdict["matching_modes"]:
        verdict["status"] = "selected"
        verdict["selected_mode"] = verdict["matching_modes"][0]
        return verdict
    verdict["status"] = "no-single-formulation-matches"
    verdict["distinguishing_table"] = distinguishing_table(outputs, tables, shapes)
    return verdict


def evaluate_class(outputs, shapes=SHAPES):
    """As evaluate, except any two NaN outputs count as equal (user decision 2026-09-15).

    Every non-NaN output bit must still equal XCCL and XCCL must agree bitwise
    across ranks. The strict verdict fields are kept alongside for transparency.
    """
    verdict = evaluate(outputs, shapes)
    verdict.update(schema=CLASS_SCHEMA, rule="nan-class", bit_exact_status=verdict["status"],
                   bit_exact_matching_modes=verdict["matching_modes"])
    verdict.pop("distinguishing_table", None)
    if verdict["errors"] or verdict["status"] == "xccl-ranks-disagree":
        verdict.update(selected_mode=None, matching_modes=[])
        return verdict
    counts = {m: {f"rank{r}": {str(rows): class_mismatch_count(outputs[r][rows][m], outputs[r][rows]["xccl"])
                               for rows in shapes} for r in (0, 1)} for m in MODES}
    verdict["class_mismatch_counts"] = counts
    verdict["matching_modes"] = [m for m in MODES if all(v == 0 for r in counts[m].values() for v in r.values())]
    verdict["selected_mode"] = verdict["matching_modes"][0] if verdict["matching_modes"] else None
    verdict["status"] = "selected" if verdict["selected_mode"] else "no-single-formulation-matches"
    return verdict


def distinguishing_table(outputs, tables, shapes=SHAPES):
    """Smallest set of fixture pairs whose rows together refute every mode."""
    refutes = {}
    for j in range(PERIOD):
        wrong = frozenset(m for m in MODES if any(tables[(r, m)][j] != tables[(r, "xccl")][j] for r in (0, 1)))
        if wrong:
            refutes.setdefault(wrong, j)
    coverable = set().union(*refutes) if refutes else set()
    rows = []
    for size in range(1, len(refutes) + 1):
        best = next((c for c in combinations(refutes, size) if set().union(*c) == coverable), None)
        if best:
            rows = [refutes[s] for s in best]
            break
    table = [{"pair": j, "refutes": sorted(m for m in MODES if tables[(0, m)][j] != tables[(0, "xccl")][j]
                                           or tables[(1, m)][j] != tables[(1, "xccl")][j]),
              "rank0": f"{PAIRS[j][0]:04x}", "rank1": f"{PAIRS[j][1]:04x}",
              **{f"{arm}_rank{r}": f"{tables[(r, arm)][j]:04x}" for arm in ARMS for r in (0, 1)}}
             for j in sorted(rows)]
    # A mode whose first-period table agrees fails only at later elements.
    uncovered = set(MODES) - coverable
    notes = []
    for m in sorted(uncovered):
        for rank in (0, 1):
            for rows_ in shapes:
                index = first_mismatch(outputs[rank][rows_][m], outputs[rank][rows_]["xccl"])
                if index is not None:
                    notes.append({"mode": m, "rank": rank, "rows": rows_, "element": index, "pair": index % PERIOD})
                    break
            else:
                continue
            break
    return {"rows": table, "position_dependent_refutations": notes}


def analyze(directory, shapes=SHAPES, rule="bit-exact"):
    """Load both rank receipts and raw bins, verify hashes and inputs, evaluate."""
    if rule not in RULES:
        raise ValueError("unknown NaN comparison rule")
    directory = Path(directory)
    outputs, errors, receipts = {0: {}, 1: {}}, [], {}
    for rank in (0, 1):
        try:
            receipt = json.loads((directory / f"rank{rank}-nan-semantics.json").read_text())
            receipts[rank] = receipt
            if receipt.get("status") != "completed" or receipt.get("group_destroyed") is not True:
                raise ValueError("worker receipt incomplete")
            for rows in shapes:
                record = receipt["shapes"][str(rows)]
                n = rows * ELEMENTS_PER_ROW
                if record["input_sha256"] != sha(column(rank, n).tobytes()) or record["peer_input_sha256"] != sha(column(1 - rank, n).tobytes()):
                    raise ValueError(f"rows{rows}: fixture input hash differs")
                if not all(record["input_unchanged"][m] for m in MODES):
                    raise ValueError(f"rows{rows}: local input changed by add kernel")
                for arm in ARMS:
                    raw = (directory / f"rank{rank}-rows{rows}-{arm}.bin").read_bytes()
                    if sha(raw) != record["sha256"][arm]:
                        raise ValueError(f"rows{rows} {arm}: raw hash differs from receipt")
                    outputs[rank].setdefault(rows, {})[arm] = raw
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors.append(f"rank{rank}: {type(exc).__name__}: {exc}")
    verdict = (evaluate_class if rule == "nan-class" else evaluate)(outputs, shapes) if not errors else {
        "schema": CLASS_SCHEMA if rule == "nan-class" else SCHEMA, "status": "incomplete",
                                                    "selected_mode": None, "matching_modes": [], "errors": []}
    verdict["errors"] = errors + verdict["errors"]
    if verdict["errors"]:
        verdict.update(status="incomplete", selected_mode=None, matching_modes=[])
    verdict["worker"] = {f"rank{r}": {k: receipts[r].get(k) for k in ("torch", "library_sha256", "add_mode_codes")}
                         for r in receipts}
    verdict["runtime_qualified"] = False
    return verdict


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("directory", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--rule", choices=RULES, default="bit-exact")
    args = ap.parse_args()
    args.out.write_text(json.dumps(analyze(args.directory, rule=args.rule), indent=2) + "\n")
