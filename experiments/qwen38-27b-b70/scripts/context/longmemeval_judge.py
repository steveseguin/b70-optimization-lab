#!/usr/bin/env python3
"""Judge LongMemEval trials with the official prompts (prepared 2026-10-07; the owner picks the judge).

Reads every <jobs>/**/verifier/judge_pair.json (written by the task's grader; it already holds the official
GPT-4o judge prompt for the question's type, copied verbatim from LongMemEval src/evaluation/evaluate_qa.py)
and asks a judge model for yes/no, exactly like the official script: one user message, temperature 0,
max_tokens 10, label = 'yes' in reply.lower(). Writes one verdict per trial (jsonl, appended; trials already
judged by the same judge model are skipped, so it can be resumed).

Judges:
  official   any OpenAI-compatible endpoint: OPENAI_BASE_URL (default https://api.openai.com/v1),
             OPENAI_API_KEY, JUDGE_MODEL (default gpt-4o-2024-08-06, the official judge). This is the
             HEADLINE judge, comparable to published LongMemEval numbers.
  local      our own 27B server: --local (API_BASE / MODEL_NAME env, as the run scripts use), thinking off
             (chat_template_kwargs.enable_thinking=false) so the yes/no fits the official 10 tokens.
             SECONDARY ONLY: the model judges its own answers. Report its agreement with the official
             judge on a shared subset before quoting it.
Trials whose deterministic grade is void (storage rule) are judged but flagged; they score 0 in the tables.

  longmemeval_judge.py JOBS_DIR [...] --out verdicts.jsonl [--local] [--dry-run] [--limit N]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path


def pairs(dirs: list[str]):
    for d in dirs:
        for p in sorted(Path(d).glob("**/verifier/judge_pair.json")):
            trial = p.parent.parent
            job = trial.parent.name
            yield job, trial, json.loads(p.read_text())


def ask(base: str, key: str, model: str, prompt: str, local: bool) -> str:
    body = {"model": model, "messages": [{"role": "user", "content": prompt}], "n": 1, "temperature": 0,
            "max_tokens": 10}
    if local:
        body["chat_template_kwargs"] = {"enable_thinking": False}
    req = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return (json.load(r)["choices"][0]["message"].get("content") or "").strip()
        except Exception as e:                    # backoff like the official script (rate limits, API errors)
            if attempt == 5:
                raise
            print(f"retry {attempt + 1}: {e}", file=sys.stderr)
            time.sleep(2 ** attempt)
    return ""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("jobs", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--local", action="store_true", help="judge with our own server (secondary score)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    if a.local:
        base = os.environ.get("API_BASE", "http://127.0.0.1:8000/v1")
        key = os.environ.get("OPENAI_API_KEY", "EMPTY")
        model = os.environ.get("MODEL_NAME", "qwen38-27b-fp8")
    else:
        base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        key = os.environ.get("OPENAI_API_KEY", "")
        model = os.environ.get("JUDGE_MODEL", "gpt-4o-2024-08-06")
    done = set()
    if os.path.exists(a.out):
        for ln in open(a.out):
            try:
                v = json.loads(ln)
                done.add((v["job"], v["judge_model"]))
            except Exception:
                pass
    todo = [(j, t, p) for j, t, p in pairs(a.jobs) if (j, model) not in done]
    if a.limit:
        todo = todo[:a.limit]
    print(json.dumps({"judge": "local (secondary)" if a.local else "official", "base": base, "model": model,
                      "to_judge": len(todo), "already": len(done)}))
    if a.dry_run:
        if todo:
            print(todo[0][2]["judge_prompt"])
        return
    if not a.local and not key:
        sys.exit("OPENAI_API_KEY is not set (official judge); use --local for the secondary 27B judge")
    with open(a.out, "a") as f:
        for job, trial, p in todo:
            reply = ask(base, key, model, p["judge_prompt"], a.local)
            v = {"job": job, "arm": job.split("__", 1)[0], "trial": str(trial), "question_id": p["question_id"],
                 "question_type": p["question_type"], "abstention": p["abstention"], "void": p.get("void", False),
                 "deterministic_status": p.get("deterministic_status"), "label": "yes" in reply.lower(),
                 "reply": reply, "judge_model": model, "judge_base": base, "secondary": a.local,
                 "t": round(time.time(), 1)}
            f.write(json.dumps(v) + "\n")
            f.flush()
            print(f"{job}: {v['label']} ({reply!r})")


if __name__ == "__main__":
    main()
