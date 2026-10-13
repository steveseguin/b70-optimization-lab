#!/usr/bin/env python3
"""freeagent: a stand-alone coding agent program that shares no code with the lab's test harness.

One loop, one tool: the model may call `shell(command)`, which runs bash inside the task container
(`docker exec`). It sends its whole history on every call and manages nothing — no truncation, no
summaries, no notes; that is the point of the experiment. It stops when a reply carries no command,
or at the step/time/call cap. Every call and token count is logged for the record.

Usage: freeagent.py --api-base URL --model M --container NAME --instruction FILE --out DIR
                     [--max-steps N] [--time-limit S] [--max-tokens N] [--temperature F]
"""
import argparse, json, os, re, subprocess, sys, time, urllib.request, urllib.error

SYSTEM = """You are an autonomous software engineer working inside a Linux container at /app.

You have one tool: shell(command) runs a bash command in the container (two-minute limit; long output
is truncated). Use it for everything: reading code, editing files, running tests.

Work carefully and verify your work. When the job in the instructions below is completely done, reply
with a short summary and no command."""

TOOL = {"type": "function", "function": {"name": "shell", "description": "Run a bash command in the task container.",
        "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}}
FENCE = re.compile(r"```(?:bash|sh|shell)\s*\n(.*?)```", re.S)


class Agent:
    def __init__(self, a):
        self.a = a
        self.messages = [{"role": "system", "content": SYSTEM},
                         {"role": "user", "content": open(a.instruction).read()}]
        self.steps, self.t0 = [], time.time()
        self.usage = {"n_lm_calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "cached_tokens": 0,
                      "reasoning_tokens": 0, "total_iters": 0, "n_bash": 0, "hit_lm_call_cap": False}

    def call(self):
        body = {"model": self.a.model, "messages": self.messages, "max_tokens": self.a.max_tokens,
                "temperature": self.a.temperature, "tools": [TOOL],
                "chat_template_kwargs": {"enable_thinking": True}}
        req = urllib.request.Request(self.a.api_base.rstrip("/") + "/chat/completions",
                                     json.dumps(body).encode(), {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=900) as r:
            return json.load(r)

    def shell(self, command):
        try:
            p = subprocess.run(["docker", "exec", self.a.container, "bash", "-lc", command],
                               capture_output=True, text=True, timeout=150)
            out = (p.stdout + p.stderr).strip()
            return (out[-6000:] + f"\n(exit_code={p.returncode})") if out else f"(exit_code={p.returncode})"
        except subprocess.TimeoutExpired:
            return "(command timed out after 150 s)"

    def run(self):
        a = self.a
        while len(self.steps) < a.max_steps and time.time() - self.t0 < a.time_limit:
            try:
                resp = self.call()
            except urllib.error.HTTPError as e:
                self.steps.append({"error": f"HTTP {e.code}: {e.read()[:400].decode(errors='replace')}"})
                break
            except Exception as e:
                self.steps.append({"error": f"{type(e).__name__}: {e}"})
                break
            u = resp.get("usage") or {}
            self.usage["n_lm_calls"] += 1
            for k in ("prompt_tokens", "completion_tokens", "cached_tokens", "reasoning_tokens"):
                self.usage[k] += u.get(k) or 0
            msg = (resp.get("choices") or [{}])[0].get("message") or {}
            self.messages.append(msg)
            call = next((c for c in msg.get("tool_calls") or []
                         if (c.get("function") or {}).get("name") == "shell"), None)
            cmd, tool_id = None, None
            if call is not None:
                tool_id = call.get("id") or "call_0"
                try:
                    cmd = json.loads(call["function"].get("arguments") or "{}").get("command", "")
                except json.JSONDecodeError:
                    cmd = ""
            else:
                m = FENCE.search(msg.get("content") or "")     # a plain fenced block also counts
                if m:
                    cmd = m.group(1)
            if not cmd:
                break                                          # the agent's final words
            t1 = time.time()
            out = self.shell(cmd)
            self.steps.append({"cmd": cmd, "seconds": round(time.time() - t1, 1)})
            self.usage["n_bash"] += 1
            if tool_id is not None:
                self.messages.append({"role": "tool", "tool_call_id": tool_id, "content": out})
            else:
                self.messages.append({"role": "user", "content": "Output of your command:\n" + out})
            self.usage["total_iters"] += 1
        self.usage["hit_lm_call_cap"] = len(self.steps) >= a.max_steps
        return self.steps

    def save(self):
        os.makedirs(self.a.out + "/agent", exist_ok=True)
        json.dump(self.messages, open(self.a.out + "/agent/trajectory.json", "w"), indent=1)
        json.dump(self.usage, open(self.a.out + "/agent/usage.json", "w"), indent=1)
        json.dump(self.steps, open(self.a.out + "/agent/timing.json", "w"), indent=1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--api-base", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--container", required=True)
    ap.add_argument("--instruction", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-steps", type=int, default=900)
    ap.add_argument("--time-limit", type=float, default=3300.0)
    ap.add_argument("--max-tokens", type=int, default=8192)
    ap.add_argument("--temperature", type=float, default=0.0)
    a = ap.parse_args()
    agent = Agent(a)
    agent.run()
    agent.save()
    u = agent.usage
    print(f"freeagent done: {u['n_lm_calls']} calls, {u['n_bash']} commands, "
          f"{u['completion_tokens']} tokens written, {time.time() - agent.t0:.0f} s")


if __name__ == "__main__":
    main()
