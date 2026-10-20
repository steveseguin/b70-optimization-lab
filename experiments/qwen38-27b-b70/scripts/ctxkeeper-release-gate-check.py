#!/usr/bin/env python3
"""Receipt checks for ctxkeeper's registered G1–G4 release gate (no GPU work).

The runner owns lifecycle; this helper writes an atomic status.json and fails
closed on absent/malformed evidence. G4 quality is observational, as registered.
"""
import argparse
import datetime
import hashlib
import json
import re
import shlex
import sys
import tarfile
from pathlib import Path


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write(path, data):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(path)


def record(out, gate, status, evidence):
    path = Path(out) / "status.json"
    data = json.loads(path.read_text())
    previous = data["gates"].get(gate, {})
    # The shell's ERR trap adds context without erasing a failed check's detail.
    keep = previous if previous.get("status") == "failed" and status == "failed" else {}
    data["gates"][gate] = {**keep, "status": status, "updated_at": now(), **evidence}
    data["updated_at"] = now()
    write(path, data)


def g1(trial, elapsed):
    trial = Path(trial)
    d = json.loads((trial / "verifier/details.json").read_text())
    timing = json.loads((trial / "agent/timing.json").read_text())
    usage = json.loads((trial / "agent/usage.json").read_text())
    checks = {
        "not_void": d.get("void") is False,
        "fixed_40_of_40": d.get("n") == 40 and d.get("fixed") == 40,
        "clean_at_least_38": d.get("clean", -1) >= 38,
        "audit_at_least_6": (d.get("audit") or {}).get("asked") == 7 and (d.get("audit") or {}).get("right", -1) >= 6,
        "within_45_minutes": elapsed <= 2700,
        "no_client_errors": bool(timing) and all("error" not in x for x in timing),
        "not_step_capped": usage.get("hit_lm_call_cap") is False,
    }
    return all(checks.values()), {"checks": checks, "elapsed_seconds": elapsed,
        "fixed": d.get("fixed"), "clean": d.get("clean"), "audit": d.get("audit"),
        "rules": d.get("rules"), "details": str(trial / "verifier/details.json"),
        "readme_recite_when_required": d.get("clean", -1) < 38}


def demo(path, rc, gate):
    if gate not in ("G2", "G4"):
        raise ValueError("only G2 and G4 use the long_chat demo")
    text = Path(path).read_text()
    rows = re.findall(r"^(\d+)/(\d+) checks passed; history about ([\d,]+) tokens", text, re.M)
    if len(rows) != 1:
        raise ValueError("exactly one completed long_chat summary required")
    passed, total, history = (int(x.replace(",", "")) for x in rows[0])
    checks = re.findall(r"^\[(PASS|FAIL)\]", text, re.M)
    complete = total == 4 and len(checks) == 4 and checks.count("PASS") == passed
    # G4 has no quality bar. Exit 1 means completed demo with a failed check;
    # a crash/timeout or truncated output is still a failed smoke.
    ok = complete and rc == (0 if passed == total else 1)
    if gate == "G2":
        ok = ok and passed == 4 and history > 262144
    else:
        ok = ok and history >= 100000
    return ok, {"returncode": rc, "passed": passed, "total": total,
        "history_approx_tokens": history, "quality_expected_4_of_4": passed == 4,
        "quality_required": gate == "G2", "log": path}


def sdk(url, out):
    from openai import OpenAI
    from openai.types.chat import ChatCompletion, ChatCompletionChunk
    client = OpenAI(base_url=url, api_key="unused", max_retries=0, timeout=180)
    quick = {"chat_template_kwargs": {"enable_thinking": False}}
    args = dict(model="qwen38-27b-fp8", extra_body=quick, temperature=0)
    plain = client.chat.completions.create(**args, max_tokens=256,
        messages=[{"role": "user", "content": "Say hello in five words."}])
    assert isinstance(plain, ChatCompletion) and plain.choices
    assert plain.choices[0].message.content and plain.choices[0].finish_reason == "stop"
    tools = [{"type": "function", "function": {"name": "shell", "description": "Run a bash command.",
        "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}}]
    tool = client.chat.completions.create(**args, max_tokens=512, tools=tools,
        messages=[{"role": "user", "content": "Use the shell tool to run `echo ok`."}])
    assert isinstance(tool, ChatCompletion) and tool.choices
    calls = tool.choices[0].message.tool_calls or []
    assert tool.choices[0].finish_reason == "tool_calls" and calls
    assert any(c.function.name == "shell" and isinstance(json.loads(c.function.arguments).get("command"), str)
               and json.loads(c.function.arguments)["command"].strip()
               for c in calls)
    chunks = list(client.chat.completions.create(**args, max_tokens=256, stream=True,
        messages=[{"role": "user", "content": "Count from one to five in words."}]))
    assert chunks and all(isinstance(c, ChatCompletionChunk) for c in chunks)
    content = "".join(c.choices[0].delta.content or "" for c in chunks if c.choices)
    assert content.strip() and any(c.choices and c.choices[0].finish_reason == "stop" for c in chunks)
    write(Path(out), {"plain": plain.model_dump(mode="json"), "tool": tool.model_dump(mode="json"),
        "stream_text": content, "chunks": len(chunks), "passed": True})


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action", choices=("init", "record", "g1", "demo", "sdk", "env", "idle", "finish"))
    ap.add_argument("args", nargs="*")
    a = ap.parse_args()
    if a.action == "init":
        out, version, venv, image, archive, source = a.args
        with tarfile.open(archive) as tar:
            for filename in ("ctxkeeper.py", "notesdelta.py", "examples/long_chat.py"):
                members = [m for m in tar.getmembers() if m.isfile() and (m.name == filename or m.name.endswith("/" + filename))]
                if len(members) != 1:
                    raise ValueError(f"release archive must contain exactly one {filename}")
                if hashlib.sha256(tar.extractfile(members[0]).read()).hexdigest() != digest(Path(source) / filename):
                    raise ValueError(f"release source differs from archive: {filename}")
        write(Path(out) / "status.json", {"format": "ctxkeeper.release-gate.v1", "version": version,
            "status": "running", "started_at": now(), "venv": venv, "image": image,
            "source_archive": archive, "archive_sha256": digest(archive),
            "demo_sha256": digest(Path(source) / "examples/long_chat.py"),
            "gates": {g: {"status": "not_run"} for g in ("G1", "G2", "G3", "G4")}})
    elif a.action == "record":
        out, gate, status, message = a.args
        record(out, gate, status, {"message": message})
    elif a.action == "g1":
        out, trial, elapsed = a.args
        try:
            ok, data = g1(trial, float(elapsed))
        except Exception as exc:
            ok, data = False, {"error": str(exc)}
        record(out, "G1", "passed" if ok else "failed", data)
        print(json.dumps(data, ensure_ascii=False))
        return 0 if ok else 1
    elif a.action == "demo":
        out, gate, path, rc = a.args
        try:
            ok, data = demo(path, int(rc), gate)
        except Exception as exc:
            ok, data = False, {"error": str(exc)}
        record(out, gate, "passed" if ok else "failed", data)
        print(json.dumps(data, ensure_ascii=False))
        return 0 if ok else 1
    elif a.action == "sdk":
        sdk(*a.args)
    elif a.action == "env":
        for line in Path(a.args[0]).read_text().splitlines():
            if line.startswith("Environment="):
                value = line.split("=", 1)[1]
                # Quoted systemd assignments contain spaces; never eval them.
                values = shlex.split(value) if value.startswith(('"', "'")) else [value]
                for value in values:
                    if not re.match(r"[A-Za-z_][A-Za-z_0-9]*=", value):
                        raise ValueError("invalid environment assignment")
                    sys.stdout.buffer.write(value.encode() + b"\0")
    elif a.action == "idle":
        rows = []
        kinds = set()
        for line in sys.stdin:
            m = re.match(r"vllm:num_requests_(running|waiting)(?:\{.*?\})?\s+(\S+)", line)
            if m:
                kinds.add(m[1]); rows.append(float(m[2]))
        return 0 if kinds == {"running", "waiting"} and all(x == 0 for x in rows) else 1
    elif a.action == "finish":
        out, rc, cleanup = a.args
        path = Path(out) / "status.json"
        d = json.loads(path.read_text())
        ok = int(rc) == 0 and int(cleanup) == 0 and all(d["gates"][g]["status"] == "passed" for g in ("G1", "G2", "G3", "G4"))
        d.update(status="passed" if ok else "failed", exit_code=int(rc), cleanup_ok=int(cleanup) == 0,
                 finished_at=now())
        write(path, d)
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
