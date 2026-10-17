#!/usr/bin/env python3
"""Validate the diagnostic-only JSONL wire contract, including command resolution."""
import argparse
import json
from pathlib import Path

SCHEMA = "ownrt.packet46.diagnostics.v1"
PHASES = set("prepare enqueue wait dense routing expert_gate_up expert_down shared_expert attention gdn hc sampler_head snapshot_capture snapshot_restore draft handoff_copy handoff_mailbox lookup_copy command accept diagnostic_route_copy".split())
BASE = {"schema", "kind", "record", "rank", "physical_card"}
COMMAND = {"request_id", "command_sequence", "position", "token_id", "occupied_context", "stage", "attempt"}
EXTRA = {
    "header": {"run_id", "model_identity", "runtime_identity", "prompt_sha256", "dataset_role", "diagnostic_only", "speed_claim_eligible", "routes", "phases", "target_experts_per_layer", "target_top_k"},
    "routes": COMMAND | {"layer", "expert_ids"},
    "phase": COMMAND | {"layer", "phase", "clock", "event_id", "start_ns", "end_ns", "duration_ns"},
    "resolution": COMMAND | {"outcome"},
    "footer": {"complete"},
}


def check(condition, message):
    if not condition:
        raise ValueError(message)


def uint(value):
    return type(value) is int and value >= 0


def validate(rows):
    check(len(rows) >= 2, "missing header/footer")
    check(rows[0].get("kind") == "header" and rows[-1].get("kind") == "footer", "incomplete diagnostic trace")
    header = rows[0]
    command_ids, resolved, routes, events = {}, {}, set(), set()
    for i, row in enumerate(rows):
        kind = row.get("kind")
        check(kind in EXTRA, "unknown record kind")
        check(set(row) == BASE | EXTRA[kind], f"unexpected or absent fields: {kind}")
        check(row["schema"] == SCHEMA and type(row["record"]) is int and row["record"] == i, "schema/record sequence")
        check(type(row["rank"]) is int and row["rank"] in (0, 1) and uint(row["physical_card"]), "rank/card")
        check((row["rank"], row["physical_card"]) == (header["rank"], header["physical_card"]), "rank/card changed")
        check((kind != "header" or i == 0) and (kind != "footer" or i == len(rows)-1), "header/footer position")
        if kind == "header":
            check(row["diagnostic_only"] is True and row["speed_claim_eligible"] is False, "diagnostics cannot enter speed claims")
            check(type(row["routes"]) is bool and type(row["phases"]) is bool and (row["routes"] or row["phases"]), "collector configuration")
            check(row["target_experts_per_layer"] == 512 and row["target_top_k"] == 10, "wrong target geometry")
            check(all(isinstance(row[x], str) and row[x] for x in ("run_id", "model_identity", "runtime_identity")), "missing identity")
            digest = row["prompt_sha256"]
            check(isinstance(digest, str) and len(digest) == 64 and all(c in "0123456789abcdef" for c in digest), "invalid prompt SHA256")
            check(row["dataset_role"] in ("calibration", "evaluation", "mock"), "dataset role")
        elif kind == "footer":
            check(row["complete"] is True, "incomplete footer")
        else:
            check(all(uint(row[x]) for x in COMMAND - {"stage", "attempt"}), "invalid command integer")
            check(row["stage"] in ("prefill", "decode"), "invalid stage")
            check(row["attempt"] in ("ordinary", "speculative", "corrected", "draft"), "invalid attempt")
            key = row["request_id"], row["command_sequence"]
            identity = tuple(row[x] for x in sorted(COMMAND))
            check(key not in command_ids or command_ids[key] == identity, "command identity changed")
            check(key not in resolved, "record after command resolution")
            command_ids[key] = identity
            if kind == "routes":
                check(header["routes"] and row["attempt"] != "draft", "route collector scope")
                check(type(row["layer"]) is int and 0 <= row["layer"] < 48, "target layer")
                ids = row["expert_ids"]
                check(isinstance(ids, list) and len(ids) == 10 and all(uint(x) and x < 512 for x in ids), "route IDs")
                check(len(set(ids)) == 10, "duplicate expert IDs")
                route_key = key + (row["layer"],)
                check(route_key not in routes, "duplicate route layer")
                routes.add(route_key)
            elif kind == "phase":
                check(header["phases"], "phase collector disabled")
                check(type(row["layer"]) is int and -1 <= row["layer"] <= 48, "phase layer")
                check(row["phase"] in PHASES, "phase name")
                check(all(uint(row[x]) for x in ("start_ns", "end_ns", "duration_ns")), "phase timestamp")
                check(row["end_ns"] >= row["start_ns"] and row["duration_ns"] == row["end_ns"]-row["start_ns"], "phase interval")
                check(row["clock"] in ("host_steady", "gpu_event"), "unknown clock")
                if row["clock"] == "host_steady":
                    check(row["event_id"] is None, "host event ID")
                else:
                    check(uint(row["event_id"]) and row["event_id"] > 0 and row["start_ns"] > 0, "GPU event ID/timing")
                    event_key = key + (row["event_id"],)
                    check(event_key not in events, "GPU event counted twice")
                    events.add(event_key)
            else:
                check(row["outcome"] in ("accepted", "rejected", "cancelled", "error", "draft_proposal"), "outcome")
                check((row["attempt"] == "draft") == (row["outcome"] == "draft_proposal") or row["outcome"] in ("error", "cancelled"), "draft outcome mismatch")
                resolved[key] = row["outcome"]
    check(set(command_ids) == set(resolved), "unresolved command: no complete trace")
    return {"schema": SCHEMA, "passed": True, "diagnostic_only": True,
            "speed_claim_eligible": False, "records": len(rows),
            "commands": len(command_ids), "route_layers": len(routes), "gpu_events": len(events)}


def read_rows(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            check(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    return [json.loads(line, object_pairs_hook=unique) for line in Path(path).read_text().splitlines()]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path)
    args = parser.parse_args()
    print(json.dumps(validate(read_rows(args.trace)), sort_keys=True))
