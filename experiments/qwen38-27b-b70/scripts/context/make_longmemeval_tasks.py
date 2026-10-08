#!/usr/bin/env python3
"""Turn LongMemEval_S instances into streamed Harbor tasks for the context harness.

Why: the lane's earlier context results used assistant-authored synthetic streams (ledgers, narrative day
books). LongMemEval (Wu et al., ICLR 2025, arXiv 2410.10813, MIT licence) is an independently authored
benchmark of long-term chat memory: per question a timestamped user-assistant chat history of ~115K tokens
(LongMemEval_S, ~48 sessions) and a question asked after the last session, with a reference answer written
by the benchmark authors. This generator serves that history through the harness's `next` tool exactly like
make_sparse_prose_tasks.py serves a day book, so the existing arms (B32ira, C32, Ar, E32r, ...) can run it.

Source data (verified 2026-10-07, sha256 matches the HF LFS oids):
  /mnt/fast-ai/datasets/longmemeval/longmemeval_s_cleaned.json   (HF xiaowu0162/longmemeval-cleaned, the
      2025-09 cleaned release the upstream README now points to; 500 instances, 277 MB)

How a task is built (one task per question):
  * stream = the haystack sessions in chronological order (sorted by haystack_dates; despite the upstream
    README, 211 of the 500 cleaned S histories are NOT in date order, so sorting changes the order for them;
    --order given keeps the file's order), ONE session per `next` item, headed with its session number and date; a session longer than
    --max-batch-tokens is split at turn boundaries (a single over-long turn at line, then character,
    boundaries) into consecutive items marked "part i of k";
  * data quirk (measured 2026-10-07): in 76 of 500 instances (60 temporal-reasoning, 16 knowledge-update)
    some sessions are dated AFTER question_date, 75 of them evidence sessions; they are served like any
    other session (same content as the official full-history reader) and flagged in task.toml metadata
    (n_sessions_after_question, evidence_sessions_after_question) so results can be reported with and without;
  * turns are rendered "USER: ..." / "ASSISTANT: ..."; the `has_answer` evidence labels and the session ids
    are NOT served (evidence session ids start with "answer_" in the data, so serving ids would leak);
  * final item (kind QUERY) = the current date (question_date) and the question as `ASK answer: <question>`,
    so the improved agent's answers guard accepts exactly the key `answer`;
  * the agent writes /app/answers.json = {"answer": "<text>"}.

Grading (tests/grade.py, written by this script; an LLM judge is not available offline):
  * deterministic, NOT the headline: abstention questions (question_id ending "_abs") count as correct when
    the answer reads as a refusal ("I don't know", "you did not mention", "no information", ...), which is
    the official rule; other answers are "exact" (normalised equality) or "contains" (normalised reference
    contained in the answer; integer references also match their number word) -> correct; anything else is
    "unmatched" (not proven wrong: long or paraphrased references need the judge); blank -> "blank";
    single-session-preference references are rubrics and are always "judge_only";
  * the verifier also writes /logs/verifier/judge_pair.json: question_id, type, question, reference,
    hypothesis and the official GPT-4o judge prompt (src/evaluation/evaluate_qa.py, copied verbatim below),
    so a later judged pass can score it. THE HEADLINE MUST USE THE JUDGED SCORE.
    `make_longmemeval_tasks.py collect JOBS_DIR... --out hyp.jsonl` gathers the pairs into the official
    hypothesis format ({"question_id", "hypothesis"} per line) plus a pairs file with the prompts;
  * storage rule (memory mode): any file created after the image build that holds >= 5 distinct 8-word
    shingles of the served stream voids the run (the harness mirror, STATE.txt and verbatim archive files
    under /tmp/.live_ctx/archive/ are exempt, as in the ledger grader); notes mode reports, never voids;
  * the spec lives in tests/lme_spec.json (no tests/spec.json), so make_kvstream_tasks.py --refresh-graders
    never overwrites this grader.

HOST MEMORY: `build` json.load()s the whole 277 MB file (about 2-3 GB of Python objects). Do not run it beside
a resident two-card server (about 3 GB free, 2 GB guard); the prereg sample is already built under
/mnt/fast-ai/datasets/longmemeval/tasks-s8-seed0/. `selftest` is small and safe.

Usage:
  make_longmemeval_tasks.py build OUT_DIR [--data PATH] [--subset N] [--seed 0] [--mode memory|notes]
                            [--ids QID ...] [--max-batch-tokens 8000] [--exact-tokens|--chars-per-token 3.9]
      --subset N   stratified sample: N questions per stratum, strata = the six question_type values
                   (non-abstention) plus "abstention" (the 30 _abs questions), drawn with random.Random(seed)
                   from the sorted question ids; the chosen ids go to OUT_DIR/selection.json
  make_longmemeval_tasks.py collect JOBS_DIR [JOBS_DIR ...] --out hyp.jsonl
  make_longmemeval_tasks.py selftest          # 2-session fake instance: build, oracle/refusal/storage grading
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import random
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_kvstream_tasks import DEFAULT_TOKENIZER, STORAGE_MEMORY, STORAGE_NOTES, write_task  # noqa: E402

DEFAULT_DATA = "/mnt/fast-ai/datasets/longmemeval/longmemeval_s_cleaned.json"
TYPES = ["single-session-user", "single-session-assistant", "single-session-preference",
         "multi-session", "temporal-reasoning", "knowledge-update"]
STRATA = TYPES + ["abstention"]

# Official judge prompts, verbatim from github.com/xiaowu0162/LongMemEval src/evaluation/evaluate_qa.py
# (main, fetched 2026-10-07). Judge model there: gpt-4o-2024-08-06, temperature 0, max_tokens 10,
# label = 'yes' in reply.lower().
_JUDGE_BASIC = ("I will give you a question, a correct answer, and a response from a model. Please answer yes if the "
                "response contains the correct answer. Otherwise, answer no. If the response is equivalent to the "
                "correct answer or contains all the intermediate steps to get the correct answer, you should also "
                "answer yes. If the response only contains a subset of the information required by the answer, "
                "answer no. ")
JUDGE_PROMPTS = {
    "basic": _JUDGE_BASIC + "\n\nQuestion: {}\n\nCorrect Answer: {}\n\nModel Response: {}\n\nIs the model response "
                            "correct? Answer yes or no only.",
    "temporal-reasoning": _JUDGE_BASIC + "In addition, do not penalize off-by-one errors for the number of days. If "
        "the question asks for the number of days/weeks/months, etc., and the model makes off-by-one errors (e.g., "
        "predicting 19 days when the answer is 18), the model's response is still correct. \n\nQuestion: {}\n\n"
        "Correct Answer: {}\n\nModel Response: {}\n\nIs the model response correct? Answer yes or no only.",
    "knowledge-update": "I will give you a question, a correct answer, and a response from a model. Please answer yes "
        "if the response contains the correct answer. Otherwise, answer no. If the response contains some previous "
        "information along with an updated answer, the response should be considered as correct as long as the "
        "updated answer is the required answer.\n\nQuestion: {}\n\nCorrect Answer: {}\n\nModel Response: {}\n\nIs "
        "the model response correct? Answer yes or no only.",
    "single-session-preference": "I will give you a question, a rubric for desired personalized response, and a "
        "response from a model. Please answer yes if the response satisfies the desired response. Otherwise, answer "
        "no. The model does not need to reflect all the points in the rubric. The response is correct as long as it "
        "recalls and utilizes the user's personal information correctly.\n\nQuestion: {}\n\nRubric: {}\n\nModel "
        "Response: {}\n\nIs the model response correct? Answer yes or no only.",
    "abstention": "I will give you an unanswerable question, an explanation, and a response from a model. Please "
        "answer yes if the model correctly identifies the question as unanswerable. The model could say that the "
        "information is incomplete, or some other information is given but the asked information is not.\n\n"
        "Question: {}\n\nExplanation: {}\n\nModel Response: {}\n\nDoes the model correctly identify the question as "
        "unanswerable? Answer yes or no only.",
}


def judge_key(qtype: str, abstention: bool) -> str:
    if abstention:
        return "abstention"
    if qtype in ("single-session-user", "single-session-assistant", "multi-session"):
        return "basic"
    return qtype


INSTRUCTION = """\
You are a chat assistant with long-term memory. Run the command `next` to receive the next item of a
stream: your earlier conversations with one user, in the order they happened. There are {total} items:
{n_batches} item(s) of chat history ({n_sessions} sessions, each headed by its session number and date; a
long session is split over consecutive items marked "part i of k"), then one final item with the current
date and a question from the user. The history is about {stream_tokens:,} tokens; an item is about
{batch_tokens:,} tokens on average and at most about {max_tokens:,}.

You do not know the question in advance. It may concern anything the user or you said in any session.

Rules:
- Each item is printed once and then deleted; it cannot be fetched again.
- Do not read or copy anything under /opt/kvstream directly; only use `next`.
- When you have received the final item, write /app/answers.json: a JSON object with exactly one key,
  {{"answer": "<your answer to the user's question, as text>"}}.

{storage_rule}
Your answer is graded for correctness against a reference answer written by the benchmark's authors.
"""

# ----------------------------------------------------------------------------------------------------------
# Grader (runs in the sandbox at verification time; GRADE_ROOT prefixes every path for the offline selftest)
GRADE_LME = r'''import json, os, re, stat
R = os.environ.get("GRADE_ROOT", "")
spec = json.load(open(R + "/tests/lme_spec.json"))
ref = json.load(open(R + "/tests/reference.json"))
mode = spec["mode"]
MIRROR = R + "/tmp/.live_ctx/LIVE_CTX_MAIN.txt"
STATE = R + "/tmp/.live_ctx/STATE.txt"
ANS = R + "/app/answers.json"
ARCHIVE = R + "/tmp/.live_ctx/archive/"
os.makedirs(R + "/logs/verifier", exist_ok=True)
try:
    got = json.load(open(ANS))
    if not isinstance(got, dict):
        got = {"answer": json.dumps(got)}
except Exception:
    got = None
answers = got or {}
hyp = answers.get("answer")
hyp = "" if hyp is None else (hyp if isinstance(hyp, str) else json.dumps(hyp))
reference = str(ref["answer"])
qtype, abst = ref["question_type"], ref["abstention"]

NUMW = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
        "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty"]
def norm(s):
    t = re.sub(r"[^a-z0-9$%.:/ ]+", " ", str(s).lower().replace("’", "'").replace("'", ""))
    t = re.sub(r"(?<!\d)[.:/](?!\d)", " ", t)
    w = [x for x in t.split() if x not in ("the", "a", "an")]
    return " " + " ".join(w) + " "
REFUSAL = re.compile(r"(don'?t|do not|cannot|can'?t|unable to|not able to) (know|tell|find|recall|determine|"
                     r"answer|say|see|confirm|remember)|(did ?n'?o?t|have ?n'?o?t|has ?n'?o?t|never|not) "
                     r"(mention|mentioned|share|shared|say|said|tell|told|provide|provided|discuss|discussed|"
                     r"specif)|no (information|record|mention|details?|data|indication)|not (mentioned|"
                     r"provided|specified|available|recorded|in (the|our) (chat|conversation|history))|"
                     r"unanswerable|there is no|isn'?t (any|mentioned)|is not (mentioned|known)|"
                     r"(is|are|was) (not enough|insufficient|incomplete)\b|not enough "
                     r"(information|info|detail)|(information|info|details?) (is|are) (not enough|insufficient|"
                     r"incomplete|missing)|insufficient (information|info|details?)", re.I)
h = hyp.strip()
if not h:
    status = "blank"
elif abst:
    status = "correct_refusal" if REFUSAL.search(h) else "unmatched"
elif qtype == "single-session-preference":
    status = "judge_only"
else:
    nh, nr = norm(h), norm(reference)
    if nh.strip() == nr.strip():
        status = "exact"
    elif nr.strip() and nr in nh:
        status = "contains"
    elif re.fullmatch(r"\d+", reference.strip()) and int(reference) < len(NUMW) and \
            (" " + NUMW[int(reference)] + " ") in nh:
        status = "contains"
    else:
        status = "unmatched"
CORRECT = ("exact", "contains", "correct_refusal")
counts = {"correct": int(status in CORRECT), "blank": int(status == "blank"),
          "wrong": int(status == "unmatched"), "stale": 0, "judge_only": int(status == "judge_only")}
score = float(status in CORRECT)
rw = re.findall(r"[a-z0-9]+", reference.lower())
hs = set(re.findall(r"[a-z0-9]+", h.lower()))
token_recall = round(sum(1 for x in rw if x in hs) / len(rw), 4) if rw else None

# ---- storage audit: files created or changed after the image build that hold stream text
built = os.stat(R + "/opt/kvstream/.built").st_mtime
SKIP = {R + p for p in ("/proc", "/sys", "/dev", "/tests", "/logs", "/opt/kvstream", "/run")}
new_files = []
for root, dirs, files in os.walk(R + "/"):
    dirs[:] = [d for d in dirs if os.path.join(root, d) not in SKIP]
    for f in files:
        p = os.path.join(root, f)
        try:
            st = os.lstat(p)
        except OSError:
            continue
        if stat.S_ISREG(st.st_mode) and st.st_mtime > built and st.st_size < (64 << 20):
            new_files.append(p)
WORD = re.compile(r"[a-z0-9]+")
items = json.load(open(R + "/tests/items.json"))
shingles = set()
for t in items[:-1]:                                    # history items only (the question is not stream data)
    w = WORD.findall(t.lower())
    shingles.update(" ".join(w[i:i + 8]) for i in range(len(w) - 7))
item_texts = {" ".join(t.split()) for t in items}
holders, archive = [], {"files": 0, "verbatim": 0}
for p in new_files:
    if p in (MIRROR, STATE):
        continue
    try:
        txt = open(p, "rb").read().decode("utf-8", "replace")
    except Exception:
        continue
    if p.startswith(ARCHIVE) and not os.path.basename(p).startswith("."):
        archive["files"] += 1
        if " ".join(txt.split()) in item_texts:
            archive["verbatim"] += 1
            continue
    w = WORD.findall(txt.lower())
    hits = len({" ".join(w[i:i + 8]) for i in range(len(w) - 7)} & shingles)
    if hits >= 5:
        holders.append({"path": p[len(R):] if R else p, "hits": hits})
violations = []
extra = sorted(k for k in answers if k != "answer")
if extra:
    violations.append({"path": "/app/answers.json", "reason": f"keys beyond 'answer': {extra[:5]}"})
if mode == "memory":
    for x in holders:
        if x["path"] != "/app/answers.json":
            violations.append({"path": x["path"], "reason": f"holds stream text ({x['hits']} 8-word shingles)"})

deliv = []
try:
    deliv = [json.loads(l) for l in open(R + "/opt/kvstream/delivery.log")]
except Exception:
    pass
it = [d for d in deliv if "n" in d]
dl = {"items_total": spec["n_items"], "items_delivered": len(it),
      "items_broken_pipe": sum(1 for d in it if not d.get("complete", True)),
      "items_to_file": sum(1 for d in it if d.get("stdout") == "file"),
      "items_with_tee": sum(1 for d in it if "tee" in d.get("siblings", [])),
      "refused": sum(1 for d in deliv if d.get("refused")),
      "calls_after_end": sum(1 for d in deliv if d.get("end"))}
void = bool(violations)
reward = 0.0 if void else score
jk = "abstention" if abst else ("basic" if qtype in ("single-session-user", "single-session-assistant",
                                                      "multi-session") else qtype)
pair = {"question_id": ref["question_id"], "question_type": qtype, "abstention": abst,
        "question": ref["question"], "question_date": ref["question_date"], "reference": reference,
        "hypothesis": hyp, "deterministic_status": status, "void": void, "judge_template": jk,
        "judge_model_official": "gpt-4o-2024-08-06",
        "judge_prompt": spec["judge_prompts"][jk].format(ref["question"], reference, hyp)}
json.dump(pair, open(R + "/logs/verifier/judge_pair.json", "w"), indent=1)
open(R + "/logs/verifier/reward.txt", "w").write(f"{reward:.6f}\n")
json.dump({"score": reward, "score_raw": score, "void": void, "kind": "longmemeval", "mode": mode,
           "headline": "NOT this score: use the judged score of judge_pair.json",
           "n": 1, "correct": counts["correct"], "counts": counts, "status": status,
           "token_recall": token_recall, "answers_file_ok": got is not None, "per_key": {"answer": status},
           "question_id": ref["question_id"], "question_type": qtype, "abstention": abst,
           "violations": violations, "files_holding_data": holders[:50], "n_new_files": len(new_files),
           "new_files": sorted(new_files)[:200], "stored_frac": (1.0 if holders else 0.0) if mode == "notes" else None,
           "delivery": dl, "archive": archive, "surprise": None},
          open(R + "/logs/verifier/details.json", "w"), indent=1)
print(f"longmemeval score {reward:.4f} raw {score:.4f} ({counts}) status={status} void={void} "
      f"{violations[:3]} delivery={dl}")
'''


# ----------------------------------------------------------------------------------------------------------
def parse_date(s: str) -> dt.datetime:
    return dt.datetime.strptime(re.sub(r"\s*\(\w+\)\s*", " ", s).strip(), "%Y/%m/%d %H:%M")


def render_turn(t: dict) -> str:
    return f"{str(t.get('role', '')).upper()}: {t.get('content', '')}"


def split_text(text: str, cap: int, count) -> list[str]:
    """Split one over-long turn at line boundaries, then (for a single huge line) at character boundaries."""
    out, cur = [], ""
    for line in text.split("\n"):
        cand = line if not cur else cur + "\n" + line
        if count(cand) <= cap:
            cur = cand
            continue
        if cur:
            out.append(cur)
        if count(line) <= cap:
            cur = line
        else:
            n = max(1, -(-count(line) // cap))
            step = -(-len(line) // n)
            out += [line[i:i + step] for i in range(0, len(line), step)]
            cur = ""
    if cur:
        out.append(cur)
    return out


def session_chunks(turns: list[str], cap: int, count) -> list[str]:
    """Greedy packing of rendered turns (blank line between turns) into chunks of at most ~cap tokens."""
    pieces: list[str] = []
    for t in turns:
        pieces += [t] if count(t) <= cap else split_text(t, cap, count)
    chunks, cur = [], []
    for p in pieces:
        if cur and count("\n\n".join(cur + [p])) > cap:
            chunks.append("\n\n".join(cur))
            cur = []
        cur.append(p)
    if cur:
        chunks.append("\n\n".join(cur))
    return chunks


def build(out: Path, inst: dict, mode: str, cap: int, count, counter_name: str, seed: int,
          order_by: str = "chronological") -> dict:
    qid = inst["question_id"]
    abst = qid.endswith("_abs")
    dates = inst["haystack_dates"]
    chrono = sorted(range(len(dates)), key=lambda i: (parse_date(dates[i]), i))
    was_sorted = chrono == list(range(len(dates)))
    order = chrono if order_by == "chronological" else list(range(len(dates)))
    qdate = parse_date(inst["question_date"])
    ev_ids = set(inst.get("answer_session_ids", []))
    sids = inst.get("haystack_session_ids", [None] * len(dates))
    late = [i for i in range(len(dates)) if parse_date(dates[i]) > qdate]
    late_ev = sum(1 for i in late if sids[i] in ev_ids)
    n_sess = len(order)
    items, evidence_items, n_split, tokens, max_tok = [], [], 0, 0, 0
    item_tokens = []
    for si, i in enumerate(order, 1):
        sess = inst["haystack_sessions"][i]
        chunks = session_chunks([render_turn(t) for t in sess], cap, count)
        has_ans = any(t.get("has_answer") for t in sess)
        n_split += len(chunks) > 1
        for ci, c in enumerate(chunks, 1):
            part = f", part {ci} of {len(chunks)}" if len(chunks) > 1 else ""
            text = f"Session {si} of {n_sess}{part}. Session date: {dates[i]}\n\n{c}"
            items.append({"kind": "UPDATE", "text": text})
            k = count(text)
            item_tokens.append(k)
            tokens += k
            max_tok = max(max_tok, k)
            if has_ans:
                evidence_items.append(len(items))
    q = " ".join(str(inst["question"]).split())
    items.append({"kind": "QUERY",
                  "text": f"Current date: {inst['question_date']}\nThe user now asks you a question. Answer it in "
                          f"/app/answers.json under the key given:\nASK answer: {q}",
                  "last": "This was the last item. Write /app/answers.json now."})
    total = len(items)
    for it in items:
        it["total"] = total
    reference = str(inst["answer"])
    spec = {"kind": "longmemeval", "mode": mode, "expected": {"answer": reference}, "n_items": total,
            "judge_prompts": JUDGE_PROMPTS}
    instr = INSTRUCTION.format(
        total=total, n_batches=total - 1, n_sessions=n_sess, stream_tokens=tokens,
        batch_tokens=tokens // max(1, total - 1), max_tokens=max_tok,
        storage_rule=STORAGE_MEMORY.replace("values, keys, SET lines", "session text, facts, dates")
        if mode == "memory" else STORAGE_NOTES)
    name = f"lme-{mode}-{qid}"
    d = out / name
    write_task(d, items=items, spec=spec, answers_oracle={"answer": reference}, instruction=instr, mode=mode,
               end_text="STREAM END: no more items. Answer the question in /app/answers.json, then submit.",
               metadata={"seed": seed, "source": "LongMemEval_S cleaned (xiaowu0162/longmemeval-cleaned)",
                         "question_id": qid, "question_type": inst["question_type"], "abstention": abst,
                         "stream_tokens": tokens, "token_counter": counter_name,
                         "batch_tokens": tokens // max(1, total - 1), "max_item_tokens": max_tok,
                         "max_batch_tokens_cap": cap, "n_sessions": n_sess, "n_split_sessions": n_split,
                         "haystack_was_sorted": was_sorted, "order": order_by,
                         "n_sessions_after_question": len(late), "evidence_sessions_after_question": late_ev},
               description=f"LongMemEval_S {qid} ({inst['question_type']}), {mode}, ~{tokens} tokens",
               kind="longmemeval")
    (d / "tests" / "spec.json").unlink()          # keep --refresh-graders away from this grader
    (d / "tests" / "lme_spec.json").write_text(json.dumps(spec))
    (d / "tests" / "grade.py").write_text(GRADE_LME)
    (d / "tests" / "reference.json").write_text(json.dumps({
        "question_id": qid, "question_type": inst["question_type"], "abstention": abst,
        "question": inst["question"], "answer": reference, "question_date": inst["question_date"],
        "answer_session_ids": inst.get("answer_session_ids", []), "evidence_items": evidence_items,
        "item_tokens": item_tokens}, indent=1))
    return {"name": name, "question_id": qid, "type": inst["question_type"], "abstention": abst,
            "items": total, "sessions": n_sess, "split_sessions": n_split, "stream_tokens": tokens,
            "max_item_tokens": max_tok, "evidence_items": evidence_items, "was_sorted": was_sorted,
            "sessions_after_question": len(late), "evidence_after_question": late_ev}


def stratum(inst: dict) -> str:
    return "abstention" if inst["question_id"].endswith("_abs") else inst["question_type"]


def select(data: list[dict], per: int | None, seed: int, ids: list[str] | None) -> list[dict]:
    if ids:
        want = set(ids)
        return [x for x in data if x["question_id"] in want]
    if not per:
        return list(data)
    rng = random.Random(seed)
    chosen = []
    for s in STRATA:
        pool = sorted((x for x in data if stratum(x) == s), key=lambda x: x["question_id"])
        chosen += rng.sample(pool, min(per, len(pool)))
    return chosen


def make_counter(exact: bool, cpt: float):
    if exact:
        from tokenizers import Tokenizer
        tok = Tokenizer.from_file(DEFAULT_TOKENIZER)
        return (lambda t: len(tok.encode(t, add_special_tokens=False).ids)), f"tokenizer:{DEFAULT_TOKENIZER}"
    return (lambda t: int(len(t) / cpt)), f"chars/{cpt}"


def cmd_build(a) -> None:
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    data = json.load(open(a.data))
    chosen = select(data, a.subset, a.seed, a.ids)
    del data
    count, cname = make_counter(a.exact_tokens, a.chars_per_token)
    rows = []
    for inst in chosen:
        r = build(out, inst, a.mode, a.max_batch_tokens, count, cname, a.seed, a.order)
        rows.append(r)
        print(json.dumps(r), flush=True)
    (out / "selection.json").write_text(json.dumps({
        "data": a.data, "seed": a.seed, "per_stratum": a.subset, "strata": STRATA, "mode": a.mode,
        "max_batch_tokens": a.max_batch_tokens, "token_counter": cname, "order": a.order,
        "question_ids": [r["question_id"] for r in rows], "tasks": rows}, indent=1))


def cmd_collect(a) -> None:
    pairs = []
    for j in a.jobs:
        for p in sorted(Path(j).glob("**/verifier/judge_pair.json")):
            x = json.load(open(p))
            x["trial_dir"] = str(p.parent.parent)
            pairs.append(x)
    with open(a.out, "w") as f:
        for x in pairs:
            f.write(json.dumps({"question_id": x["question_id"], "hypothesis": x["hypothesis"]}) + "\n")
    Path(a.out + ".pairs.json").write_text(json.dumps(pairs, indent=1))
    print(json.dumps({"pairs": len(pairs), "hypotheses": a.out, "with_prompts": a.out + ".pairs.json"}))


# ----------------------------------------------------------------------------------------------------------
FAKE = {"question_id": "fake01", "question_type": "knowledge-update",
        "question": "Which city do I live in now?", "answer": "Lisbon", "question_date": "2023/06/10 (Sat) 09:00",
        "haystack_session_ids": ["s_b", "answer_x"], "answer_session_ids": ["answer_x"],
        "haystack_dates": ["2023/06/02 (Fri) 10:00", "2023/05/01 (Mon) 08:30"],
        "haystack_sessions": [
            [{"role": "user", "content": "I just moved to Lisbon last week and the trams are lovely, honestly the "
                                         "best part of my new routine every single morning.", "has_answer": True},
             {"role": "assistant", "content": "Congratulations on the move to Lisbon! Tram 28 is famous."}],
            [{"role": "user", "content": "I live in Porto and I want a recipe for bacalhau with potatoes and olive "
                                         "oil that my grandmother used to make on Sundays."},
             {"role": "assistant", "content": "Here is a classic recipe.\n" + "\n".join(
                 f"Step {i}: stir the pot slowly and taste the sauce again before adding salt." for i in range(60))}]]}


def _grade(task: Path, root: Path, answers: dict | None, extra_file: tuple[str, str] | None = None) -> dict:
    import shutil
    import time
    if root.exists():
        shutil.rmtree(root)
    (root / "tests").mkdir(parents=True)
    for f in ("lme_spec.json", "reference.json", "items.json"):
        shutil.copy(task / "tests" / f, root / "tests" / f)
    (root / "opt" / "kvstream").mkdir(parents=True)
    (root / "opt" / "kvstream" / ".built").write_text("")
    past = time.time() - 10
    os.utime(root / "opt" / "kvstream" / ".built", (past, past))
    (root / "app").mkdir()
    if answers is not None:
        (root / "app" / "answers.json").write_text(json.dumps(answers))
    if extra_file:
        p = root / extra_file[0].lstrip("/")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(extra_file[1])
    subprocess.run([sys.executable, "-I", str(task / "tests" / "grade.py")], check=True, capture_output=True,
                   env={**os.environ, "GRADE_ROOT": str(root)})
    return json.load(open(root / "logs" / "verifier" / "details.json"))


def cmd_selftest(_a) -> None:
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        count, cname = make_counter(os.path.exists(DEFAULT_TOKENIZER), 3.9)
        r = build(td / "tasks", FAKE, "memory", 300, count, cname, 0)
        task = td / "tasks" / r["name"]
        for f in ("task.toml", "instruction.md", "environment/Dockerfile", "environment/next",
                  "environment/stream.jsonl", "tests/test.sh", "tests/grade.py", "tests/lme_spec.json",
                  "tests/reference.json", "tests/items.json", "solution/solve.sh"):
            assert (task / f).exists(), f
        assert not (task / "tests" / "spec.json").exists()
        items = [json.loads(x) for x in (task / "environment" / "stream.jsonl").read_text().splitlines()]
        # chronological: the May session (index 1 in the data) comes first and is long -> split at the cap
        assert items[0]["text"].startswith("Session 1 of 2, part 1 of "), items[0]["text"][:60]
        assert "2023/05/01" in items[0]["text"] and "Porto" in items[0]["text"]
        assert any("Lisbon" in i["text"] and i["text"].startswith("Session 2 of 2") for i in items)
        assert items[-1]["kind"] == "QUERY" and "ASK answer: Which city" in items[-1]["text"]
        assert all(i["total"] == len(items) for i in items)
        assert not any("has_answer" in i["text"] or "answer_x" in i["text"] for i in items), "leak"
        assert all(count(i["text"]) <= 300 + 40 for i in items[:-1]), [count(i["text"]) for i in items]
        ref = json.load(open(task / "tests" / "reference.json"))
        assert ref["evidence_items"] == [len(items) - 1], ref["evidence_items"]
        # the clm_improved answers guard parses exactly this key from the final item
        assert re.findall(r"(?m)^ASK (\S+?):", items[-1]["text"]) == ["answer"]
        g = td / "root"
        checks = [
            ("oracle", {"answer": "Lisbon"}, None, "exact", 1.0, False),
            ("contains", {"answer": "You live in Lisbon now (you moved from Porto)."}, None, "contains", 1.0, False),
            ("stale", {"answer": "Porto"}, None, "unmatched", 0.0, False),
            ("blank", {"answer": ""}, None, "blank", 0.0, False),
            ("no file", None, None, "blank", 0.0, False),
            ("extra key", {"answer": "Lisbon", "notes": "x"}, None, "exact", 0.0, True),
            ("stored", {"answer": "Lisbon"}, ("/app/notes/h.txt", items[0]["text"][:3000]), "exact", 0.0, True),
            ("mirror ok", {"answer": "Lisbon"}, ("/tmp/.live_ctx/LIVE_CTX_MAIN.txt", items[0]["text"]), "exact",
             1.0, False),
            ("archive ok", {"answer": "Lisbon"}, ("/tmp/.live_ctx/archive/item-001.txt", items[0]["text"]), "exact",
             1.0, False),
        ]
        for label, ans, extra, st, reward, void in checks:
            d = _grade(task, g, ans, extra)
            assert (d["status"], d["score"], d["void"]) == (st, reward, void), (label, d["status"], d["score"],
                                                                                 d["void"], d["violations"])
        pair = json.load(open(g / "logs" / "verifier" / "judge_pair.json"))
        assert pair["judge_template"] == "knowledge-update" and "Correct Answer: Lisbon" in pair["judge_prompt"]
        # abstention: a refusal is correct (official rule), a guess is not
        fa = dict(FAKE, question_id="fake02_abs", question="Which city does my sister live in?",
                  answer="You did not mention your sister.")
        r2 = build(td / "tasks", fa, "notes", 300, count, cname, 0)
        t2 = td / "tasks" / r2["name"]
        for ans, st in (("I don't know; you never mentioned your sister.", "correct_refusal"),
                        ("The information provided is not enough to say.", "correct_refusal"),
                        ("Your sister lives in Lisbon.", "unmatched")):
            d = _grade(t2, g, {"answer": ans})
            assert d["status"] == st, (ans, d["status"])
        d = _grade(t2, g, {"answer": "no idea"}, ("/app/notes/h.txt", items[0]["text"][:3000]))
        assert not d["void"] and d["stored_frac"] == 1.0          # notes mode reports, never voids
        # collect
        jobs = td / "jobs" / "B32ira__x" / "trial" / "verifier"
        jobs.mkdir(parents=True)
        (jobs / "judge_pair.json").write_text(json.dumps(pair))
        hyp = td / "hyp.jsonl"
        cmd_collect(argparse.Namespace(jobs=[str(td / "jobs")], out=str(hyp)))
        assert json.loads(hyp.read_text())["question_id"] == "fake01"
        print(json.dumps({"selftest": "ok", "token_counter": cname, "items": len(items), "checks": len(checks) + 3}))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("out")
    b.add_argument("--data", default=DEFAULT_DATA)
    b.add_argument("--subset", type=int, default=None, help="N questions per stratum (7 strata)")
    b.add_argument("--seed", type=int, default=0)
    b.add_argument("--ids", nargs="+", default=None, help="explicit question ids (overrides --subset)")
    b.add_argument("--mode", choices=["memory", "notes"], default="memory")
    b.add_argument("--max-batch-tokens", type=int, default=8000)
    b.add_argument("--exact-tokens", action="store_true", help="count with the Qwen3.8 tokenizer.json")
    b.add_argument("--chars-per-token", type=float, default=3.9)
    b.add_argument("--order", choices=["chronological", "given"], default="chronological",
                   help="session order: sorted by haystack_dates (default) or the file's order")
    c = sub.add_parser("collect")
    c.add_argument("jobs", nargs="+")
    c.add_argument("--out", required=True)
    sub.add_parser("selftest")
    a = ap.parse_args()
    {"build": cmd_build, "collect": cmd_collect, "selftest": cmd_selftest}[a.cmd](a)


if __name__ == "__main__":
    main()
