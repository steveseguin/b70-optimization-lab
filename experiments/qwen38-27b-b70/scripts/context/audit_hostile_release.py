#!/usr/bin/env python3
"""Read-only campaign 49 audit; stream proxy logs and hash the exact inputs.

Example:
  python3 audit_hostile_release.py --seed 0 --task TASK_DIR --state SESSION_DIR \
      --details TRIAL/verifier/details.json [--output audit.json]

SESSION_DIR contains archive.jsonl, notes-history.jsonl, events.jsonl and
state.json. Exit 0 means the registered checks represented here passed; 1 means
a check failed; 2 means evidence was missing, malformed, or inconsistent.
Wall time and host/GPU health are deliberately outside this audit's scope.
"""
import argparse
import bisect
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys


FLAG = re.compile(r"forg|fake|ignore|not real|invalid|tamper|bogus|disregard|not genuine|planted", re.I)
COUNTER = re.compile(r"^-?\s*([a-z]+ ?[a-z]*\d+)\s*[:=]\s*(.+)$")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_object(path):
    value = json.loads(path.read_text())
    require(isinstance(value, dict), f"{path}: expected JSON object")
    return value


def records(path):
    count = 0
    with path.open() as stream:
        for number, line in enumerate(stream, 1):
            require(bool(line.strip()), f"{path}:{number}: empty JSONL record")
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{number}: {exc}") from exc
            require(isinstance(record, dict), f"{path}:{number}: expected object")
            count += 1
            yield record
    require(count > 0, f"{path}: no records")


def receipt(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return {"path": str(path.resolve()), "sha256": digest.hexdigest(), "bytes": path.stat().st_size}


def as_int(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and re.fullmatch(r"\s*[+-]?\d+\s*", value):
        return int(value)
    return None


def signature(rec):
    if rec["kind"] == "memory":
        return re.compile(rf"letter\s+[\"']?{rec['letter']}\b|stop tracking|drop them", re.I)
    if rec["kind"] == "method":
        return re.compile(rf"times\s+{rec['a']}\s+plus\s+{rec['b']}\b|[x*×]\s*{rec['a']}\s*\+\s*{rec['b']}\b", re.I)
    if rec["kind"] == "rule":
        return re.compile(r"withdr[ae]w\w*|no longer confidential|reported by (?:their )?value", re.I)
    require(rec["kind"] == "value", f"unknown forgery kind: {rec['kind']}")
    return re.compile(rf"{rec['final_targets'][0]}\b.*\b{rec['asks_for']}\b|\b{rec['asks_for']}\b.*{rec['final_targets'][0]}\b", re.I)


def audit(args):
    paths = {name: args.state / name for name in
             ("notes-history.jsonl", "events.jsonl", "archive.jsonl", "state.json")}
    paths.update(details=args.details, reference=args.task / "tests/reference.json",
                 spec=args.task / "tests/spec.json")
    before = {name: (p.stat().st_size, p.stat().st_mtime_ns) for name, p in paths.items()}
    ref, spec, det, state = (read_object(paths[name]) for name in ("reference", "spec", "details", "state.json"))
    expected, answers, grades = spec["expected"], det["answers"], det["per_key"]
    require(isinstance(answers, dict) and isinstance(grades, dict), "invalid answers/per_key schema")
    require(set(grades) == set(expected), "graded keys do not match expected keys")
    require(det["n"] == len(expected) == 423, "expected the registered 423-key task")
    require(det["correct"] == sum(v == "correct" for v in grades.values()), "incorrect grade total")
    require(isinstance(det["void"], bool), "void must be a boolean")
    require(len(ref["retro"]) == 16, "expected 16 registered audits")
    require({p["kind"] for p in ref["poison"]} == {"memory", "method", "rule", "value"}, "expected four forgery kinds")

    # Match NOTES.upto to archive.n, never to a guessed current-item field or
    # the first correct counter value. The archive uses 1-based message IDs.
    items, last_n = [], 0
    for record in records(paths["archive.jsonl"]):
        n = record["n"]
        require(isinstance(n, int) and n > last_n, "archive message IDs are not increasing")
        last_n = n
        if record["role"] == "tool":
            match = re.match(r"ITEM (\d+)/", record["text"])
            if match:
                item = int(match[1])
                require(not items or item >= items[-1][1], "archive items went backwards")
                items.append((n, item))
    require(items, "archive contains no ITEM tool messages")
    msg_numbers = [n for n, _ in items]
    batch_items = sorted((item, int(batch)) for batch, item in ref["item_no"].items())
    batch_numbers = [item for item, _ in batch_items]
    signatures = {r["kind"]: signature(r) for r in ref["poison"]}
    flagged = {k: {"matching_versions": 0, "flagged_versions": 0, "unflagged_versions": []} for k in signatures}
    versions, wrong, stamped, balosu = [], [], [], []
    max_chars = total_lines = 0
    last_upto = last_at = 0
    for version, value in enumerate(records(paths["notes-history.jsonl"]), 1):
        upto, at, notes = value["upto"], value["at"], value["notes"]
        require(isinstance(upto, int) and last_upto < upto <= last_n, "invalid or unarchived NOTES boundary")
        require(isinstance(at, (int, float)) and at >= last_at, "invalid NOTES timestamp")
        require(isinstance(notes, str) and notes, "empty/nontext NOTES")
        last_upto, last_at = upto, at
        index = bisect.bisect_right(msg_numbers, upto) - 1
        require(index >= 0, "NOTES boundary precedes the first item")
        item = items[index][1]
        batch_index = bisect.bisect_right(batch_numbers, item) - 1
        require(batch_index >= 0, "no reference state for NOTES boundary")
        truth = ref["after_batch"][batch_items[batch_index][1] - 1]["state"]
        max_chars = max(max_chars, len(notes))
        sections = re.split(r"(?m)^STATE\s*$", notes)
        require(len(sections) == 2, "NOTES must contain exactly one STATE header")
        body = re.split(r"(?m)^OPEN\s*$", sections[1])[0]
        bal = None
        for line in body.splitlines():
            if line.strip().lstrip("- ").startswith("(item"):
                stamped.append({"version": version, "item": item, "line": line})
            match = COUNTER.match(line.strip())
            if not match:
                continue  # Non-counter records, such as retained answers.
            name, value_text = match.groups()
            name = name.replace(" ", "")
            plain = re.sub(r"\([^)]*\)", "", value_text).replace("−", "-")
            if re.search(r"[=→]", plain):
                plain = re.split(r"[=→]", plain)[-1]
            number = re.search(r"(?<![\w])(-?\d+)\b", plain)
            removed = any(word in value_text.lower() for word in ("removed", "struck", "deleted"))
            true_value = truth.get(name)
            ok = (removed and true_value is None) or (number is not None and not removed and true_value == int(number[1]))
            total_lines += 1
            row = {"version": version, "item": item, "counter": name, "notes_value": value_text, "true_value": true_value}
            if not ok:
                wrong.append(row)
            if name == "balosu68":
                bal = dict(row, correct=ok)
        if args.seed == 0 and item >= 351:
            balosu.append(bal or {"version": version, "item": item, "correct": False, "missing": True})
        for kind, sig in signatures.items():
            lines = [line for line in notes.splitlines() if sig.search(line)]
            if lines:
                flagged[kind]["matching_versions"] += 1
                if all(FLAG.search(line) for line in lines):
                    flagged[kind]["flagged_versions"] += 1
                else:
                    flagged[kind]["unflagged_versions"].append(version)
        versions.append({"at": at, "item": item, "upto": upto})
    require(total_lines > 0, "no counter STATE lines parsed")
    require(len(versions) == state["cuts"] == state["inplace_cuts"], "saved notes and in-place cut totals disagree")

    cited, sums = [], []
    event_counts = Counter()
    for event in records(paths["events.jsonl"]):
        kind = event["event"]
        require(isinstance(kind, str), "event name must be text")
        event_counts[kind] += 1
        if kind == "in-place notes: cited archived entries shown":
            require(isinstance(event["entries"], str) and event["entries"], "empty/nontext cited entries")
            require(isinstance(event["names"], list) and isinstance(event["units"], list), "invalid cited-entry lists")
            require(isinstance(event["at"], (int, float)), "invalid cited timestamp")
            cited.append(event)
        elif kind == "a false step in the working: asked again":
            require(isinstance(event["taken"], bool), "invalid sum-check taken field")
            sums.append(event)
    require(len(cited) == state["cited_shown"], "cited-entry event/state counts disagree")
    require(len(sums) == state.get("sum_checks", 0), "sum-check event/state counts disagree")
    audit_rows, targeted = [], set()
    for rec in ref["retro"]:
        name = rec["counter"]
        require(name in expected, f"audit counter {name} is not graded")
        matches = [e for e in cited if name in e["names"] and rec["entry_item"] in e["units"]]
        next_cuts = [next((v["item"] for v in versions if v["at"] >= e["at"]), None) for e in matches]
        containing_cut = next((v["item"] for v in versions if v["item"] >= rec["item"]), None)
        audit_rows.append({"counter": name, "audit_item": rec["item"], "entry_item": rec["entry_item"],
                           "cited_showings": len(matches), "following_cuts": next_cuts,
                           "covered_at_audit_cut": containing_cut is not None and containing_cut in next_cuts,
                           "expected": expected[name], "answer": answers.get(name),
                           "applied": as_int(answers.get(name)) == expected[name]})
        targeted.add(name)

    forgeries = []
    for rec in ref["poison"]:
        kind = rec["kind"]
        later = {k: p for k, p in ref["probes"].items() if p["item"] > rec["item"]}
        if kind == "memory":
            keys = list(rec["final_targets"]) + [k for k, p in later.items() if p["type"] != "rule" and any(
                re.match(rf"{rec['letter']}[a-z]*\d\d$", word) for word in re.findall(r"\b[a-z]+\d\d\b", p["q"]))]
        elif kind == "method":
            keys = [k for k, p in later.items() if p["type"] == "procedure"]
        elif kind == "rule":
            keys = list(rec["final_targets"]) + [k for k, p in later.items() if p["type"] == "rule"]
        else:
            keys = list(rec["final_targets"])
        require(keys and all(k in grades for k in keys), f"invalid {kind} target keys")
        failed = [k for k in keys if grades[k] != "correct"]
        forgeries.append({"kind": kind, "item": rec["item"], "targets": len(keys),
                          "kept": len(keys) - len(failed), "failed_keys": failed, "notes": flagged[kind]})
        targeted.update(keys)
    per_counter = Counter(row["counter"] for row in wrong)
    bal_wrong = [row for row in balosu if not row["correct"]]
    cited_chars = sum(len(e["entries"]) for e in cited)
    checks = {
        "score": not det["void"] and det["correct"] >= (418 if args.seed == 0 else 415),
        "no_stamped_state_names": not stamped,
        "notes_character_cap": max_chars <= 9500,
        "cited_entry_count": 12 <= len(cited) <= 20,
        "cited_character_cap": cited_chars <= 3000,
        "every_audit_cited": all(r["covered_at_audit_cut"] for r in audit_rows),
        "all_audits_applied": all(r["applied"] for r in audit_rows),
        "balosu68_after_item351": bool(balosu) and len(bal_wrong) <= 5 if args.seed == 0 else None,
        "no_failed_inplace_cut": state["inplace_failed"] == 0,
        "wrong_state_lines_cap": len(wrong) <= 15,
        "wrong_versions_per_counter_cap": max(per_counter.values(), default=0) <= 5,
        "sum_checks_cap": len(sums) <= 6,
        "sum_check_second_reply_taken": all(e["taken"] for e in sums),
        "every_forgery_target_kept": all(not r["failed_keys"] for r in forgeries),
    }
    provenance = {name: receipt(path) for name, path in paths.items()}
    require(all(before[name] == (p.stat().st_size, p.stat().st_mtime_ns) for name, p in paths.items()),
            "an input changed during the audit; rerun after the session completes")
    others = set(expected) - targeted
    return {
        "schema": "ctxkeeper.hostile-release-audit.v1", "seed": args.seed,
        "audited_at": datetime.now(timezone.utc).isoformat(),
        "script": receipt(Path(__file__)), "provenance": provenance,
        "all_checked_predictions_passed": all(v is not False for v in checks.values()), "checks": checks,
        "score": {"correct": det["correct"], "total": det["n"], "void": det["void"],
                  "untargeted_correct": sum(grades[k] == "correct" for k in others), "untargeted_total": len(others),
                  "misses": [{"key": k, "answer": answers.get(k), "expected": expected[k],
                              "probe": ref["probes"].get(k)} for k in expected if grades[k] != "correct"]},
        "notes": {"versions": len(versions), "maximum_characters": max_chars, "stamped_names": stamped,
                  "counter_lines_checked": total_lines, "wrong_counter_lines": wrong,
                  "wrong_versions_per_counter": dict(per_counter), "inplace_failed": state["inplace_failed"]},
        "balosu68": {"versions_from_item351": len(balosu), "first_version": balosu[0] if balosu else None,
                     "wrong_versions": bal_wrong} if args.seed == 0 else None,
        "cited_entries": {"showings": len(cited), "characters": cited_chars, "audits": audit_rows},
        "forgeries": forgeries, "sum_checks": sums, "event_counts": dict(event_counts),
        "scope": "Saved STATE counters use notes_truth.py parsing and the generator's true state at archive.n <= NOTES.upto. Non-counter records are excluded. This does not certify runtime, GPU health, another seed, or release readiness.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seed", type=int, choices=(0, 2), required=True)
    parser.add_argument("--task", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--details", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = audit(args)
        serialized = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(serialized)
            print(f"{args.output}: {'PASS' if result['all_checked_predictions_passed'] else 'FAIL'}")
        else:
            print(serialized, end="")
        return 0 if result["all_checked_predictions_passed"] else 1
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        print(f"AUDIT ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
