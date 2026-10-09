#!/usr/bin/env python3
"""Synthetic check of probe_analysis.py: one arm, 6 items of ~50K tokens, two probes, one void trial."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import probe_analysis as pa  # noqa: E402
import summarize_results as sr  # noqa: E402


def w(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(obj if isinstance(obj, str) else json.dumps(obj))


def make(root: Path, void: bool, rand: str) -> None:
    td = root / "tasks" / "probe" / "t1"
    w(td / "task.toml", "[metadata]\nstream_tokens = 300000\n")
    w(td / "environment" / "stream.jsonl", "\n".join(json.dumps({"kind": "UPDATE", "text": "x" * 1000}) for _ in range(6)))
    w(td / "tests" / "reference.json", {"after_batch": [], "surprise": {}, "probes": {
        "p3_1": {"q": "?", "a": 1, "type": "current", "item": 3, "ref_item": 1, "distance": 2, "tokens_back": 100000},
        "p5_1": {"q": "?", "a": 2, "type": "old_value", "item": 5, "ref_item": 4, "distance": 30, "tokens_back": 50000}}})
    t = root / "runs" / "jobs" / "A1__t1" / f"t1__{rand}"
    w(t / "config.json", {"task": {"path": str(td)}})
    w(t / "verifier" / "details.json", {"void": void, "score": 0.5, "per_key": {
        "p3_1": "correct", "p5_1": "stale", "k1": "correct", "k2": "wrong"}})
    # steps 1..12: odd steps deliver items 1..6, each step takes 30 s
    w(t / "agent" / "timing.json", [{"step": k, "llm_s": 20.0, "bash_s": 10.0, "cmd": "next" if k % 2 else "x"}
                                    for k in range(1, 13)])
    steps = [{"step_id": k, "source": "agent", "observation": {"results": [
        {"content": f"ITEM {(k + 1) // 2}/6 (UPDATE)\nxx" if k % 2 else "ok"}]}} for k in range(1, 13)]
    w(t / "agent" / "trajectory.ctx.json", {"segments": [{"steps": steps}]})
    w(t / "agent" / "trajectory.json", [{"role": "tool", "content": sr.SUBMIT}])
    w(t / "agent" / "usage.json", {"n_lm_calls": 12, "completion_tokens": 500})
    w(t / "agent" / "truncate_calls.json", [{}, {}])


def main() -> None:
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        make(root, False, "aaa")
        make(root, True, "bbb")
        text, data = pa.analyse(root, [4, 24, 99, 399])
        print(text)
        a = data["arms"]["A1"]
        assert a["n_trials"] == 1 and len(data["skipped"]) == 1, data["skipped"]
        assert a["by_bin"]["1-4"] == "1/1=1.00" and a["by_bin"]["25-99"] == "0/1=0.00", a["by_bin"]
        assert a["by_type"] == {"current": "1/1=1.00", "old_value": "0/1=0.00"}
        assert a["final"] == "1/2" and a["total"] == "2/4"
        # 50K tokens per item: 100K reached at item 2 (step 3, 90 s), 200K at item 4 (step 7, 210 s)
        assert a["cum_min"] == {"100000": 1.5, "200000": 3.5, "300000": 5.5}, a["cum_min"]
        assert a["seg_min_per_100k"]["200000"] == 2.0
        assert a["totals"]["truncations"] == 2 and a["totals"]["lm_calls"] == 12
    print("OK")


if __name__ == "__main__":
    main()
