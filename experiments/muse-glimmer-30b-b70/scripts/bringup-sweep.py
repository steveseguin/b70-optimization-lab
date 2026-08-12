#!/usr/bin/env python3
"""Bring-up sweep runner for Muse Glimmer 30B on B70 card pairs.

Takes a lane config JSON; for each config entry launches llama-server,
benches a fixed greedy prompt set, records timings plus output hashes to
JSONL, and tears the server down. The first entry should be the no-spec
reference; later analysis compares output hashes against it (greedy spec
decoding must be byte-identical or the config is a correctness FAIL).
"""
import hashlib
import fcntl
import json
import os
import subprocess
import sys
import time
import urllib.request

BIN = os.environ.get("MUSE_SWEEP_BIN", "/home/steve/src/llama.cpp-muse-glimmer/build-sycl-b70-aot-bmg-g31/bin/llama-server")
MODEL = os.environ.get("MUSE_SWEEP_MODEL", "/mnt/fast-ai/llm-models/muse-glimmer-30b-gguf/Muse-Glimmer-30B-UD-Q8_K_XL.gguf")
DRAFT = os.environ.get("MUSE_SWEEP_DRAFT", "/mnt/fast-ai/llm-models/muse-glimmer-30b-gguf/dflash-kquant.gguf")
GPU_LOCK_DEFAULT = "/run/lock/muse-glimmer-gpu-exclusive.lock"


def gpu_lock_path():
    override = os.environ.get("MUSE_GPU_LOCK_PATH")
    if override and os.environ.get("MUSE_GPU_LOCK_ALLOW_OVERRIDE") != "1":
        raise RuntimeError(
            "MUSE_GPU_LOCK_PATH override requires MUSE_GPU_LOCK_ALLOW_OVERRIDE=1; "
            "operational launches must use the canonical host lock"
        )
    return override or GPU_LOCK_DEFAULT

PROMPTS = {
    "prose": "Write a detailed technical explanation of how a B-tree index accelerates database range queries, covering node structure, fanout, height, and cache behavior.",
    "code": "Implement an LRU cache class in Python with O(1) get and put using a doubly linked list plus dict. Include docstrings and a small usage example.",
    "json": "Produce only a JSON array of 12 objects, fields name, priority (1-3), eta_minutes, describing the ordered steps of a server migration runbook. No prose outside the JSON.",
}


def acquire_gpu_lock(path=None):
    path = path or gpu_lock_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.lseek(fd, 0, os.SEEK_SET)
        owner = os.read(fd, 512).decode(errors="replace").strip() or "unknown owner"
        os.close(fd)
        raise RuntimeError(f"GPU host is already reserved: {owner}") from None

    owner = f"benchmark pid={os.getpid()} argv={' '.join(sys.argv)}\n".encode()
    os.ftruncate(fd, 0)
    os.write(fd, owner)
    os.fsync(fd)
    return fd


def preflight_binary(env):
    try:
        check = subprocess.run(
            [BIN, "--version"], env=env, stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE, text=True, timeout=30, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"llama-server preflight failed: {exc}") from exc
    if check.returncode != 0:
        detail = check.stderr.strip().splitlines()[-1] if check.stderr.strip() else "no stderr"
        raise RuntimeError(
            f"llama-server preflight exited {check.returncode}: {detail}"
        )


def http_json(port, path, payload, timeout=900):
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def wait_health(port, proc, tries=75):
    for _ in range(tries):
        if proc.poll() is not None:
            return False
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2)
            return True
        except Exception:
            time.sleep(4)
    return False


def run_config(lane, cfg, port, gpus, out, lock_fd, model=MODEL):
    env = dict(os.environ)
    env["ONEAPI_DEVICE_SELECTOR"] = f"level_zero:{gpus}"
    env.setdefault("UR_L0_USE_IMMEDIATE_COMMANDLISTS", "1")
    env.setdefault("UR_L0_ENABLE_RELAXED_ALLOCATION_LIMITS", "1")
    env.setdefault("GGML_SYCL_ENABLE_VMM", "1")
    env.update(cfg.get("env", {}))

    args = [
        BIN, "-m", model, "--host", "127.0.0.1", "--port", str(port),
        "-ngl", "99", "-c", "32768", "--parallel", "1", "-b", "1024", "-ub", "1024",
        "--threads", "8", "-fa", "on", "--jinja",
    ]
    if cfg.get("spec", True):
        draft_model = cfg.get("draft", DRAFT)
        args += [
            "--spec-type", cfg.get("spec_type", "draft-dflash"), "--spec-draft-model", draft_model,
            "--spec-draft-n-max", str(cfg.get("n_max", 5)),
            "--spec-draft-ngl", "99",
        ]
        if "p_min" in cfg:
            args += ["--spec-draft-p-min", str(cfg["p_min"])]
    args += cfg.get("args", [])

    log_path = f"/mnt/fast-ai/bench-results/muse-glimmer-30b/servers/sweep-{lane}-{cfg['label']}.log"
    with open(log_path, "w") as lf:
        # The child inherits the lock so an abrupt runner death cannot make the
        # host appear free while llama-server is still alive.
        proc = subprocess.Popen(
            args, env=env, stdout=lf, stderr=subprocess.STDOUT,
            pass_fds=(lock_fd,), start_new_session=True,
        )
    try:
        if not wait_health(port, proc):
            out.write(json.dumps({"lane": lane, "label": cfg["label"], "error": "server failed to start"}) + "\n")
            out.flush()
            return
        row = {"lane": lane, "label": cfg["label"], "config": {k: v for k, v in cfg.items() if k != "label"}, "prompts": {}}
        for pname, ptext in PROMPTS.items():
            msgs = [
                {"role": "system", "content": "Reasoning strength: low"},
                {"role": "user", "content": ptext},
            ]
            tpl = http_json(port, "/apply-template", {"messages": msgs}, timeout=60)
            r = http_json(port, "/completion", {
                "prompt": tpl["prompt"], "n_predict": 256,
                "temperature": 0, "cache_prompt": False,
            })
            t = r["timings"]
            dn = t.get("draft_n") or 0
            da = t.get("draft_n_accepted") or 0
            row["prompts"][pname] = {
                "gen_tok_s": round(t["predicted_per_second"], 3),
                "predicted_n": t["predicted_n"],
                "draft_n": dn,
                "draft_accepted": da,
                "accept_pct": round(da / dn * 100, 1) if dn else None,
                "text_sha": hashlib.sha256(r["content"].encode()).hexdigest()[:16],
                "text_head": r["content"][:60],
            }
        out.write(json.dumps(row) + "\n")
        out.flush()
        print(f"[{lane}] {cfg['label']}: " + "  ".join(
            f"{p}={v['gen_tok_s']}t/s({v['accept_pct']}%)" for p, v in row["prompts"].items()))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        time.sleep(2)


def main():
    cfg = json.load(open(sys.argv[1]))
    lock_path = gpu_lock_path()
    lock_fd = acquire_gpu_lock(lock_path)
    try:
        base_env = dict(os.environ)
        preflight_binary(base_env)
        print(f"[{cfg['lane']}] acquired exclusive GPU host lock {lock_path}", flush=True)
        os.makedirs(os.path.dirname(cfg["out"]), exist_ok=True)
        with open(cfg["out"], "a") as out:
            for c in cfg["configs"]:
                run_config(
                    cfg["lane"], c, cfg["port"], cfg["gpus"], out,
                    lock_fd, cfg.get("model", MODEL),
                )
        print(f"[{cfg['lane']}] sweep complete -> {cfg['out']}", flush=True)
    finally:
        os.close(lock_fd)


if __name__ == "__main__":
    main()
