"""Packet85 interval accounting, copied unchanged; no import-time resource cap."""
from collections import defaultdict
import statistics as st
def duration(t):
    return 1000 * (t["rank_completed"] - t["rank_received"])


def balanced(pairs):
    groups = defaultdict(list)
    for label, value in pairs:
        groups[label].append(value)
    return st.median(st.median(v) for v in groups.values())


def intervals(r, limit=99):
    """Join by position, never by trace serialization order (ranks overlap).

    Each row starts at a verified emission and ends at the next emission.
    Hit/miss refers to the guess just verified at the starting emission.
    Rank 0's NEXT speculation races the next rank 1 half; its exposed tail
    is retained. Copies inside commands stay inside those command durations.
    """
    trace = r["rank_trace"]
    index = {(t["rank"], t["op"], t["position"], t["speculative"]): t
             for t in trace if t["op"] in (1, 3, 9)}
    stamps = r["generated_token_completion_timestamps"]
    draft_rank = next(t["rank"] for t in trace if t["op"] == 9)
    guesses = {d["position"]: d["hit"] for d in r["guess_rows"]}
    out = []
    for i, (start, end) in enumerate(zip(stamps, stamps[1:])):
        if i >= limit:
            break
        pos = r["prompt_tokens"] + i
        hit = guesses[pos]
        b = index[(1, 1, pos, False)]
        d = index[(draft_rank, 9, pos, True)]
        spec_next = index.get((0, 1, pos + 1, True))
        spec_previous = index[(0, 1, pos, True)]
        rollback = index.get((0, 3, pos, True)) if not hit else None
        corrected = index.get((0, 1, pos, False)) if not hit else None
        D, B = duration(d), duration(b)
        R = duration(rollback) if rollback else 0.0
        C = duration(corrected) if corrected else 0.0
        A = duration(spec_next) if spec_next else 0.0
        offset = 1000 * (spec_next["rank_received"] - b["rank_received"]) if spec_next else 0.0
        race = max(B, A + offset)
        if draft_rank == 1:
            ready = max(D, R + C)
        else:
            ready = D + R + C
        elapsed = 1000 * (end - start)
        branch_end = max(d["rank_completed"],
                         corrected["rank_completed"] if corrected else spec_previous["rank_completed"])
        out.append({"i": i, "position": pos, "hit": hit, "draft_rank": draft_rank,
                    "elapsed_ms": elapsed, "D": D, "B": B, "A": A, "R": R, "C": C,
                    "spec_start_offset_ms": offset,
                    "rank0_slack_ms": B - A - offset,
                    "handoff_ready_to_rank1_ms": 1000 * (b["rank_received"] - branch_end),
                    "draft_issue_after_emission_ms": 1000 * (d["rank_received"] - start),
                    "rollback_issue_after_emission_ms": 1000 * (rollback["rank_received"] - start) if rollback else None,
                    "restore_to_corrected_start_ms": 1000 * (corrected["rank_received"] - rollback["rank_completed"]) if corrected else None,
                    "emission_after_race_ms": 1000 * (end - max(b["rank_completed"], spec_next["rank_completed"] if spec_next else b["rank_completed"])),
                    "prediction_without_gaps_ms": ready + race,
                    "unresolved_control_gaps_ms": elapsed - ready - race})
    assert len(out) == min(limit, len(stamps) - 1)
    return out


