#!/usr/bin/env python3
"""Gemma 4 26B A4B Q8 (llama.cpp SYCL) metric sweep on one B70: draft length 0-5, prefill and decode at
300 / 2K / 8K / 16K context, repeat determinism, and 1-8 concurrent users on the 8x4K and 4x16K slot shapes.

Each server configuration runs in its own transient user unit on the selected card; measurements come from
llama.cpp's own `timings` block (prompt_ms / predicted_ms / draft_n / draft_n_accepted), not client clocks.

usage: tools/gemma4-26b-sweep.py run [--gpu 0] [--port 19350] [--only LABEL,...] [--out DIR]
       tools/gemma4-26b-sweep.py summarize DIR
Run under a shell that has sourced oneAPI setvars.sh (PATH / LD_LIBRARY_PATH are passed to the unit).
"""
import argparse, json, os, random, statistics, subprocess, threading, time, urllib.request, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL = "/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/gemma-4-26B-A4B-it-UD-Q8_K_XL.gguf"
DRAFT = "/mnt/fast-ai/llm-models/gemma4-26b-a4b-it-q8-gguf/MTP/gemma-4-26B-A4B-it-Q4_0-MTP.gguf"
SERVER = "/home/steve/src/llama.cpp-gemma-c926-oneapi2026.1-compat/build-sycl-b70-aot-bmg-g31-q8reorder-vdr2/bin/llama-server"
ALIAS = "gemma4-26b-a4b-q8"
LAUNCHER = "/home/steve/llm-optimizations/scripts/serve-gemma4-26b-q8-production.sh"  # sets the ~20 LLAMA_GEMMA4_* / LLAMA_SYCL_* kernel switches
OUT_TOKENS = 256


def draft_args(n_max, n_min=None):
    if not n_max:
        return []
    n_min = n_min if n_min is not None else min(2, n_max)
    return ["--spec-type", "draft-mtp", "--spec-draft-model", DRAFT, "--spec-draft-n-max", str(n_max),
            "--spec-draft-n-min", str(n_min), "--spec-draft-device", "SYCL0", "--spec-draft-ngl", "all",
            "--spec-draft-type-k", "f16", "--spec-draft-type-v", "f16", "--spec-draft-p-min", "0.0475",
            "--no-spec-draft-backend-sampling", "--spec-draft-threads", "32", "--spec-draft-threads-batch", "32"]


def configs():
    """Each entry becomes environment for the production launcher (the same path the LAN service uses)."""
    def cfg(label, shape, draft, slots, ctx, ub, points, users, users_8k=()):
        extra = ["--parallel", str(slots), "--cache-ram", "512", "--ctx-checkpoints", "8"] + draft_args(draft)
        return {"label": label, "shape": shape, "draft": draft, "slots": slots, "ctx": ctx, "ub": ub,
                "env": {"GEMMA4_26B_PROFILE": "service", "CTX_SIZE": str(ctx * slots), "PARALLEL": str(slots), "BATCH_SIZE": "2048",
                        "UBATCH_SIZE": str(ub), "LLAMA_PREFILL_UBATCH_SIZE": str(ub), "CACHE_RAM_MIB": "512",
                        "GGML_SYCL_DNNL_DETERMINISTIC": "1", "LLAMA_SERVER": SERVER, "EXTRA_LLAMA_ARGS": " ".join(extra)},
                "single_points": points, "users": list(users), "users_8k": list(users_8k)}
    out = []
    for d in (0, 1, 2, 3, 4, 5):
        out.append(cfg(f"single-16k-draft{d}", "1 slot x 16K", d, 1, 16384, 2048, [300, 512, 2048, 8192, 15800], []))
    for d in (0, 1, 3):
        out.append(cfg(f"p8x4k-draft{d}", "8 slots x 4K", d, 8, 4096, 1024, [300, 2048], [1, 2, 4, 8]))
    for d in (0, 1, 3):
        out.append(cfg(f"p4x16k-draft{d}", "4 slots x 16K", d, 4, 16384, 1024, [300, 2048, 8192], [1, 2, 4], [4]))
    return out


# ---------------------------------------------------------------- http helpers
def post(base, path, body, timeout=900):
    req = urllib.request.Request(base + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=timeout))


WORDS = ["network", "server", "cache", "token", "model", "layer", "query", "memory", "device", "kernel", "stream",
         "batch", "prompt", "answer", "number", "letter", "window", "signal", "buffer", "thread", "river", "stone",
         "garden", "engine", "silver", "harbor", "candle", "meadow", "summit", "violet"]


def make_prompt(base, n_tokens, seed):
    """Filler text sized with the server's tokenizer to about n_tokens prompt tokens (chat template adds ~20)."""
    rnd = random.Random(seed)
    tail = "\n\nQuestion: in two sentences, what is a local area network? Then list five prime numbers and explain each briefly."
    head = "Below is a long filler document. After it, answer the question.\n\n"
    if n_tokens <= 320:
        body = " ".join(rnd.choice(WORDS) for _ in range(max(1, n_tokens - 60)))
    else:
        body = " ".join(rnd.choice(WORDS) for _ in range(n_tokens))
    text = head + body + tail
    got = len(post(base, "/tokenize", {"content": text})["tokens"])
    target = n_tokens - 20
    if got > target:
        words = body.split()
        body = " ".join(words[: int(len(words) * target / got)])
        text = head + body + tail
    return text


def chat(base, prompt, max_tokens=OUT_TOKENS, cache=False):
    t0 = time.time()
    r = post(base, "/v1/chat/completions", {"model": ALIAS, "temperature": 0, "max_tokens": max_tokens, "cache_prompt": cache,
                                            "messages": [{"role": "user", "content": prompt}]})
    wall = time.time() - t0
    tm = r.get("timings", {})
    txt = r["choices"][0]["message"].get("content") or ""
    return {"wall_s": round(wall, 3), "prompt_n": tm.get("prompt_n"), "prompt_ms": tm.get("prompt_ms"),
            "prompt_tps": tm.get("prompt_per_second"), "predicted_n": tm.get("predicted_n"), "predicted_ms": tm.get("predicted_ms"),
            "decode_tps": tm.get("predicted_per_second"), "draft_n": tm.get("draft_n"), "draft_n_accepted": tm.get("draft_n_accepted"),
            "cache_n": tm.get("cache_n"), "text": txt}


def med(xs):
    xs = [x for x in xs if x]
    return round(statistics.median(xs), 1) if xs else None


# ---------------------------------------------------------------- measurements
def single_points(base, points, log):
    res = {}
    for n in points:
        runs = []
        for i in range(3 if n <= 2048 else 2):
            p = make_prompt(base, n, seed=1000 + n + i)
            r = chat(base, p)
            runs.append(r)
            log(f"  ctx {n}: prompt_n={r['prompt_n']} prefill {r['prompt_tps']:.0f} tok/s, decode {r['decode_tps']:.1f} tok/s"
                + (f", draft acc {r['draft_n_accepted']}/{r['draft_n']}" if r.get("draft_n") else ""))
        acc = sum(r["draft_n_accepted"] or 0 for r in runs); dn = sum(r["draft_n"] or 0 for r in runs)
        res[str(n)] = {"prompt_n": runs[0]["prompt_n"], "prefill_tps": med([r["prompt_tps"] for r in runs]),
                       "decode_tps": med([r["decode_tps"] for r in runs]), "ttft_s": round(min(r["prompt_ms"] for r in runs) / 1000, 2),
                       "draft_accept_rate": round(acc / dn, 3) if dn else None, "runs": [{k: v for k, v in r.items() if k != "text"} for r in runs]}
    return res


def repeat_identical(base, log):
    p = make_prompt(base, 3000, seed=4242)
    texts = [chat(base, p, max_tokens=200)["text"] for _ in range(3)]
    d = len(set(texts)); log(f"  repeat identity: {d} distinct of 3")
    return {"distinct": d, "runs": 3}


def users_point(base, n_users, prompt_tokens, log):
    prompts = [make_prompt(base, prompt_tokens, seed=7000 + prompt_tokens + i) for i in range(n_users)]
    results = [None] * n_users
    def worker(i):
        results[i] = chat(base, prompts[i])
    t0 = time.time()
    ths = [threading.Thread(target=worker, args=(i,)) for i in range(n_users)]
    [t.start() for t in ths]; [t.join() for t in ths]
    wall = time.time() - t0
    per = [r["decode_tps"] for r in results]
    tot_out = sum(r["predicted_n"] for r in results); tot_in = sum(r["prompt_n"] for r in results)
    acc = sum(r["draft_n_accepted"] or 0 for r in results); dn = sum(r["draft_n"] or 0 for r in results)
    out = {"users": n_users, "prompt_tokens": prompt_tokens, "per_stream_decode_tps": med(per), "per_stream_min": round(min(per), 1),
           "aggregate_decode_tps": round(sum(per), 1), "wall_s": round(wall, 2), "total_tok_s_incl_prefill": round((tot_in + tot_out) / wall, 1),
           "completion_tok_s_wall": round(tot_out / wall, 1), "ttft_max_s": round(max(r["prompt_ms"] for r in results) / 1000, 2),
           "draft_accept_rate": round(acc / dn, 3) if dn else None}
    log(f"  {n_users} users @ {prompt_tokens}: per-stream {out['per_stream_decode_tps']} (min {out['per_stream_min']}), aggregate {out['aggregate_decode_tps']} tok/s, "
        f"wall total {out['total_tok_s_incl_prefill']} tok/s")
    return out


# ---------------------------------------------------------------- server lifecycle
def start_server(cfg, gpu, port, log_path):
    unit = f"gemma-sweep-{cfg['label']}"
    subprocess.run(["systemctl", "--user", "stop", unit], stderr=subprocess.DEVNULL)
    env = dict(cfg["env"])
    env.update({"GPU_INDEX": str(gpu), "PORT": str(port), "HOST": "127.0.0.1", "LOG": log_path,
                "OUT_DIR": os.path.join(os.path.dirname(log_path), "replica-logs"),
                "PATH": os.environ.get("PATH", ""), "LD_LIBRARY_PATH": os.environ.get("LD_LIBRARY_PATH", "")})
    cmd = ["systemd-run", "--user", f"--unit={unit}", "--collect", "-p", "KillMode=mixed", "-p", "KillSignal=SIGINT", "-p", "TimeoutStopSec=120"]
    cmd += [f"--setenv={k}={v}" for k, v in env.items()]
    cmd += [LAUNCHER]
    subprocess.run(cmd, check=True)
    return unit


def wait_ready(unit, port, timeout=900):
    base = f"http://127.0.0.1:{port}"; t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            urllib.request.urlopen(base + "/v1/models", timeout=3)
            post(base, "/v1/chat/completions", {"model": ALIAS, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1}, timeout=120)
            return round(time.time() - t0)
        except Exception:
            pass
        if subprocess.run(["systemctl", "--user", "is-active", "--quiet", unit]).returncode != 0:
            raise RuntimeError("server unit died")
        time.sleep(5)
    raise RuntimeError("server not ready in time")


def card_mem(gpu):
    try:
        out = subprocess.run(["timeout", "15", "xpu-smi", "stats", "-d", str(gpu)], capture_output=True, text=True).stdout
        for line in out.splitlines():
            if "GPU Memory Used" in line and "avg:" in line:
                return int(line.split("avg:")[1].split(",")[0].strip())
    except Exception:
        pass
    return None


def run(args):
    out_dir = args.out or os.path.join(ROOT, "data", "profiles", datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d"), "gemma-sweep")
    os.makedirs(out_dir, exist_ok=True)
    only = set(args.only.split(",")) if args.only else None
    base = f"http://127.0.0.1:{args.port}"
    for cfg in configs():
        if only and cfg["label"] not in only:
            continue
        path = os.path.join(out_dir, cfg["label"] + ".json")
        if os.path.exists(path) and not args.redo:
            print(f"[sweep] skip {cfg['label']} (exists)", flush=True); continue
        log_path = os.path.join(out_dir, cfg["label"] + ".server.log")
        lines = []
        def log(s):
            lines.append(s); print(f"[sweep {time.strftime('%H:%M:%S')}] {s}", flush=True)
        log(f"start {cfg['label']} ({cfg['shape']}, draft {cfg['draft']})")
        unit = start_server(cfg, args.gpu, args.port, log_path)
        result = {"label": cfg["label"], "shape": cfg["shape"], "draft_n_max": cfg["draft"], "slots": cfg["slots"], "ctx_per_slot": cfg["ctx"], "ubatch": cfg["ub"],
                  "launcher": LAUNCHER, "launcher_env": cfg["env"], "gpu": args.gpu, "deterministic_onednn": True, "build": SERVER, "out_tokens": OUT_TOKENS}
        try:
            result["load_s"] = wait_ready(unit, args.port)
            result["card_memory_used_mib_after_load"] = card_mem(args.gpu)
            log(f"  ready in {result['load_s']} s, card memory {result['card_memory_used_mib_after_load']} MiB")
            result["single"] = single_points(base, cfg["single_points"], log)
            result["repeat_identical"] = repeat_identical(base, log)
            result["users"] = [users_point(base, n, 2048, log) for n in cfg["users"]]
            result["users_8k"] = [users_point(base, n, 8192, log) for n in cfg.get("users_8k", [])]
            result["ok"] = True
        except Exception as e:
            result["ok"] = False; result["error"] = repr(e); log(f"  FAILED: {e!r}")
        finally:
            subprocess.run(["systemctl", "--user", "stop", unit], stderr=subprocess.DEVNULL)
        result["log"] = lines
        json.dump(result, open(path, "w"), indent=1)
        log(f"wrote {path}")


def summarize(d):
    rows = []
    for f in sorted(os.listdir(d)):
        if f.endswith(".json") and ".noenv" not in f:
            rows.append(json.load(open(os.path.join(d, f))))
    rows.sort(key=lambda r: (r["slots"], r["draft_n_max"]))
    print("| shape | draft | load s | card GB | prefill 300/2K/8K/16K tok/s | decode @300 / 2K / 8K / 16K ctx tok/s | draft accept | repeats | users: per-stream (aggregate) tok/s | 4 users @ 8K |")
    print("| --- | ---: | ---: | ---: | --- | --- | ---: | --- | --- | --- |")
    for r in rows:
        if not r.get("ok"):
            print(f"| {r['shape']} | {r['draft_n_max']} | failed: {r.get('error','')[:60]} |"); continue
        s = r["single"]
        def g(k, f):
            return f"{s[k][f]:,.0f}" if k in s and s[k].get(f) else "-"
        def gd(k):
            return f"{s[k]['decode_tps']:.1f}" if k in s and s[k].get("decode_tps") else "-"
        acc = [v["draft_accept_rate"] for v in s.values() if v.get("draft_accept_rate")]
        users = ", ".join(f"{u['users']}: {u['per_stream_decode_tps']} ({u['aggregate_decode_tps']})" for u in r["users"]) or "-"
        u8 = ", ".join(f"{u['per_stream_decode_tps']} ({u['aggregate_decode_tps']})" for u in r.get("users_8k", [])) or "-"
        mem = f"{r['card_memory_used_mib_after_load']/1024:.1f}" if r.get("card_memory_used_mib_after_load") else "-"
        print(f"| {r['shape']} | {r['draft_n_max']} | {r.get('load_s','-')} | {mem} | {g("300","prefill_tps")} / {g('2048','prefill_tps')} / {g('8192','prefill_tps')} / {g('15800','prefill_tps')} "
              f"| {gd('300')} / {gd('2048')} / {gd('8192')} / {gd('15800')} | {(f'{statistics.mean(acc):.0%}' if acc else '-')} | "
              f"{'identical' if r['repeat_identical']['distinct']==1 else str(r['repeat_identical']['distinct'])+' distinct'} | {users} | {u8} |")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("run"); a.add_argument("--gpu", type=int, default=0); a.add_argument("--port", type=int, default=19350)
    a.add_argument("--only"); a.add_argument("--out"); a.add_argument("--redo", action="store_true")
    b = sub.add_parser("summarize"); b.add_argument("dir")
    ns = ap.parse_args()
    run(ns) if ns.cmd == "run" else summarize(ns.dir)
