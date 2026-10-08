#!/usr/bin/env python3
"""Arm F: one-call full-history control for a LongMemEval task built by make_longmemeval_tasks.py.

One chat request: the official LongMemEval long-context reader prompt (src/generation/run_generation.py,
"direct" variant: "I will give you several history chats between you and a user. ... History Chats: ...
Current Date: ... Question: ... Answer:"), with the history = the task's served items verbatim (same
session headers and turn text the stream arms see), then the question. No tools, no stream, no budget.
It sees the question together with the history, so it is the in-window ceiling, not a retention test.

Window need: prompt tokens (Qwen tokenizer, counted before sending) + MAX_TOKENS must fit the server's
max_model_len (read from /v1/models); if not, the trial is written as skipped ("window") and not sent.

Writes a Harbor-like trial dir:  <job_dir>/F-trial/{agent/request_meta.json, agent/response.json,
agent/usage.json, verifier/{reward.txt,details.json,judge_pair.json}, result.json, config.json}
The verifier is the task's own tests/grade.py, run on a scratch root (GRADE_ROOT) holding
/app/answers.json = {"answer": <final reply text>}.

  longmemeval_direct.py --task TASK_DIR --job-dir JOB_DIR [--api-base URL] [--model NAME]
                        [--max-tokens 16384] [--thinking true|false] [--temperature 0]
Env defaults: API_BASE, MODEL_NAME, MAX_TOKENS, ENABLE_THINKING, TEMPERATURE.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

TOKENIZER = "/mnt/fast-ai/llm-models/qwen3.8-27b-fp8/tokenizer.json"
TEMPLATE = ("I will give you several history chats between you and a user. Please answer the question based on the "
            "relevant chat history.\n\n\nHistory Chats:\n\n{}\n\nCurrent Date: {}\nQuestion: {}\nAnswer:")


def post(url: str, body: dict, timeout: float) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {os.environ.get('OPENAI_API_KEY', 'EMPTY')}"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", required=True)
    ap.add_argument("--job-dir", required=True)
    ap.add_argument("--api-base", default=os.environ.get("API_BASE", "http://127.0.0.1:8000/v1"))
    ap.add_argument("--model", default=os.environ.get("MODEL_NAME", "qwen38-27b-fp8"))
    ap.add_argument("--max-tokens", type=int, default=int(os.environ.get("MAX_TOKENS", "16384")))
    ap.add_argument("--thinking", default=os.environ.get("ENABLE_THINKING", "true"))
    ap.add_argument("--temperature", type=float, default=float(os.environ.get("TEMPERATURE", "0")))
    ap.add_argument("--timeout", type=float, default=3600)
    a = ap.parse_args()
    task, trial = Path(a.task), Path(a.job_dir) / "F-trial"
    if trial.exists():
        shutil.rmtree(trial)
    (trial / "agent").mkdir(parents=True)
    (trial / "verifier").mkdir()
    items = [json.loads(x) for x in (task / "environment" / "stream.jsonl").read_text().splitlines() if x.strip()]
    ref = json.loads((task / "tests" / "reference.json").read_text())
    history = "\n\n".join(f"### {it['text']}" for it in items if it["kind"] != "QUERY")
    prompt = TEMPLATE.format(history, ref["question_date"], ref["question"])
    from tokenizers import Tokenizer
    n_prompt = len(Tokenizer.from_file(TOKENIZER).encode(prompt).ids) if os.path.exists(TOKENIZER) else len(prompt) // 4
    win = None
    try:
        d = json.load(urllib.request.urlopen(a.api_base.rstrip("/") + "/models", timeout=10))
        win = {m.get("id"): m.get("max_model_len") for m in d.get("data", [])}.get(a.model)
    except Exception as e:
        print(f"models probe failed: {e}", file=sys.stderr)
    need = n_prompt + 64 + a.max_tokens
    meta = {"arm": "F", "task": str(task), "question_id": ref["question_id"], "prompt_tokens_local": n_prompt,
            "window": win, "window_need": need, "max_tokens": a.max_tokens, "thinking": a.thinking,
            "template": "LongMemEval run_generation.py direct (full-history-session, nl)"}
    (trial / "config.json").write_text(json.dumps({"agent": {"name": "direct", "kwargs": meta},
                                                    "task": {"path": str(task)}}, indent=1))
    t0 = time.time()
    answer, usage, status = "", {}, "ok"
    if win and need > int(win):
        status = "skipped:window"
    else:
        body = {"model": a.model, "messages": [{"role": "user", "content": prompt}], "max_tokens": a.max_tokens,
                "temperature": a.temperature,
                "chat_template_kwargs": {"enable_thinking": str(a.thinking).lower() == "true"}}
        try:
            resp = post(a.api_base.rstrip("/") + "/chat/completions", body, a.timeout)
            (trial / "agent" / "response.json").write_text(json.dumps(resp, indent=1))
            msg = resp["choices"][0]["message"]
            answer = (msg.get("content") or "").strip()
            usage = resp.get("usage") or {}
            if resp["choices"][0].get("finish_reason") == "length":
                status = "max_tokens"
        except Exception as e:
            status = f"error:{type(e).__name__}:{e}"
    wall = time.time() - t0
    meta.update(status=status, wall_s=round(wall, 2))
    (trial / "agent" / "request_meta.json").write_text(json.dumps(meta, indent=1))
    (trial / "agent" / "usage.json").write_text(json.dumps({
        "prompt_tokens": usage.get("prompt_tokens", 0), "completion_tokens": usage.get("completion_tokens", 0),
        "n_lm_calls": 1, "context_budget_tokens": 0, "wall_s": round(wall, 2)}, indent=1))
    # grade with the task's own verifier on a scratch root
    with tempfile.TemporaryDirectory() as td:
        r = Path(td)
        shutil.copytree(task / "tests", r / "tests")
        (r / "opt" / "kvstream").mkdir(parents=True)
        (r / "opt" / "kvstream" / ".built").write_text("")
        (r / "app").mkdir()
        (r / "app" / "answers.json").write_text(json.dumps({"answer": answer}))
        past = time.time() - 5
        os.utime(r / "app" / "answers.json", (past, past))     # not a "new file" for the storage audit
        os.utime(r / "opt" / "kvstream" / ".built", (past + 1, past + 1))
        g = subprocess.run([sys.executable, "-I", str(r / "tests" / "grade.py")], env={**os.environ, "GRADE_ROOT": td},
                           capture_output=True, text=True)
        (trial / "verifier" / "test-stdout.txt").write_text(g.stdout + g.stderr)
        for f in ("reward.txt", "details.json", "judge_pair.json"):
            if (r / "logs" / "verifier" / f).exists():
                shutil.copy(r / "logs" / "verifier" / f, trial / "verifier" / f)
    reward = float((trial / "verifier" / "reward.txt").read_text()) if (trial / "verifier" / "reward.txt").exists() else None
    (trial / "result.json").write_text(json.dumps({"arm": "F", "status": status, "wall_s": round(wall, 2),
                                                   "verifier_result": {"rewards": {"reward": reward}}}, indent=1))
    print(json.dumps({"job": str(a.job_dir), "status": status, "prompt_tokens": n_prompt, "window": win,
                      "reward_deterministic": reward, "wall_s": round(wall, 2)}))


if __name__ == "__main__":
    main()
