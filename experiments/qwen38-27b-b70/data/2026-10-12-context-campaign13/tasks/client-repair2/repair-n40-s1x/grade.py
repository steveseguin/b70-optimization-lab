#!/usr/bin/env python3
"""Grade a repair marathon (runs in the task container after the agent has stopped)."""
import ast, hashlib, json, os, re, shutil, subprocess, sys
T, APP, LOG = "/tests", "/app", "/logs/verifier"
os.makedirs(LOG, exist_ok=True)
open(f"{LOG}/reward.txt", "w").write("0.0000\n")          # whatever happens below, there is a reward
spec = json.load(open(f"{T}/spec.json"))
MARK, rule_at = spec["mark"], spec["rule_at"]

def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest() if os.path.exists(p) else None

def read(p):
    try:
        return open(p, errors="replace").read()
    except OSError:
        return ""

tests_touched = [f for f, h in spec["tests_sha"].items() if sha(f"{APP}/tests/{f}") != h]
work = "/tmp/grade"
shutil.rmtree(work, ignore_errors=True)
os.makedirs(work)
if os.path.isdir(f"{APP}/more_itertools"):
    shutil.copytree(f"{APP}/more_itertools", f"{work}/more_itertools")
shutil.copytree(f"{T}/orig_tests", f"{work}/tests")                    # the original tests, whatever the agent did

def run(mod, cls):
    code = ("import sys, unittest, json, resource\n"
            "resource.setrlimit(resource.RLIMIT_AS, (128 * 2**20, 128 * 2**20))\n"
            "sys.path.insert(0, %r)\n" % work +
            "m = __import__('tests.' + sys.argv[1], fromlist=['x'])\n"
            "s = unittest.defaultTestLoader.loadTestsFromTestCase(getattr(m, sys.argv[2]))\n"
            "r = unittest.TextTestRunner(stream=open('/dev/null', 'w'), verbosity=0).run(s)\n"
            "print(json.dumps({'run': r.testsRun, 'bad': len(r.failures) + len(r.errors)}))\n")
    try:
        p = subprocess.run([sys.executable, "-I", "-c", code, mod, cls], cwd=work, capture_output=True, text=True, timeout=30)
        return json.loads(p.stdout.strip().splitlines()[-1])
    except Exception:
        return {"run": 0, "bad": 1}

def units(text):
    """{name: (first line, last line)} of the top-level functions and classes, as the parser sees them."""
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return {}
    return {n.name: (n.lineno, n.end_lineno) for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}

def new_lines(now, then):
    """The lines of `now` that `then` does not hold (by content, each line of `then` used once)."""
    old, out = {}, []
    for ln in then:
        old[ln] = old.get(ln, 0) + 1
    for ln in now:
        if old.get(ln, 0):
            old[ln] -= 1
        elif ln.strip():
            out.append(ln)
    return out

files = {}
for name in sorted({b["file"] for b in spec["bugs"]}):
    now, then = read(f"{APP}/more_itertools/{name}"), read(f"{T}/broken/{name}")
    files[name] = {"now": now.splitlines(), "then": then.splitlines(), "u_now": units(now), "u_then": units(then)}

def block(f, which, unit):
    span = f["u_" + which].get(unit)
    return f[which][span[0] - 1:span[1]] if span else []

# lines added or changed outside every ticket's function, without the mark: the per-ticket check cannot see them
stray = []
for name, f in files.items():
    inside = {"now": set(), "then": set()}
    for b in spec["bugs"]:
        for which in ("now", "then"):
            span = f["u_" + which].get(b["func"]) if b["file"] == name else None
            if span:
                inside[which].update(range(span[0], span[1] + 1))
    rest = {w: [ln for i, ln in enumerate(f[w], 1) if i not in inside[w]] for w in ("now", "then")}
    stray += [f"{name}: {ln.strip()[:80]}" for ln in new_lines(rest["now"], rest["then"]) if not ln.rstrip().endswith(MARK)]

fixes = [ln.strip() for ln in read(f"{APP}/FIXES.md").splitlines() if ln.strip()]
recipes_lines = [ln.strip().strip("`") for ln in read(f"{APP}/RECIPES.txt").splitlines() if ln.strip()]
log = []
for ln in read("/opt/repair/.log").splitlines():
    try:
        log.append(json.loads(ln))
    except ValueError:
        pass
per, counts = {}, {"fixed": 0, "clean": 0}
rules = {r: {"applies": 0, "kept": 0} for r in ("R1", "R2", "R3")}
for tk in spec["bugs"]:
    f = files[tk["file"]]
    res = run(tk["module"], tk["cls"])
    fixed = res["run"] > 0 and res["bad"] == 0
    changed = new_lines(block(f, "now", tk["func"]), block(f, "then", tk["func"]))
    row = {"fixed": fixed, "changed_lines": len(changed), "tests": res}
    broken = []
    def judge(rule, kept):
        row[rule] = bool(kept)
        if fixed:
            rules[rule]["applies"] += 1
            rules[rule]["kept"] += bool(kept)
            if not kept:
                broken.append(rule)
    if tk["ticket"] > rule_at["R1"]:
        # every new line of the function carries the mark; a fix made elsewhere counts if no unmarked line is anywhere
        judge("R1", all(ln.rstrip().endswith(MARK) for ln in changed) and (bool(changed) or not stray))
    if tk["ticket"] > rule_at["R2"]:
        judge("R2", any(re.match(r"\W*%d\s*\|" % tk["ticket"], ln) and tk["func"] in ln for ln in fixes))
    if tk["ticket"] > rule_at["R3"]:
        # the rule has a condition: listed if the fix is in recipes.py, NOT listed if it is in more.py
        judge("R3", (tk["func"] in recipes_lines) == (tk["file"] == "recipes.py"))
    row["clean"] = bool(fixed and not broken)
    counts["fixed"] += fixed
    counts["clean"] += row["clean"]
    per[f"t{tk['ticket']}"] = row
n = len(spec["bugs"])
void = bool(tests_touched)
delivered = sorted({r.get("ticket") for r in log})
audit = None
if spec.get("audit"):
    # the audit ticket: `<ticket> | <function>` for the BUG tickets before the FIXES.md notice; the first line for a
    # ticket number counts, and a line is right when number and function are both right
    asked = {b["ticket"]: b["func"] for b in spec["bugs"] if b["ticket"] in set(spec["audit"])}
    said = {}
    for ln in read(f"{APP}/AUDIT.md").splitlines():
        m = re.match(r"\W*(\d{1,6})\s*\|\s*`?(\w+)", ln)
        if m:
            said.setdefault(int(m.group(1)), m.group(2))
    audit = {"asked": len(asked), "right": sum(said.get(t) == f for t, f in asked.items()), "lines": len(said),
             "other_tickets": len([t for t in said if t not in asked])}
score = 0.0 if void else counts["clean"] / n
details = {"kind": "repair", "n": n, "correct": counts["clean"], "fixed": counts["fixed"], "clean": counts["clean"], "rules": rules,
           "score": score, "score_raw": counts["clean"] / n, "stray_unmarked_lines": stray[:40], "tests_touched": tests_touched,
           "void": void, "violations": tests_touched,
           "recipes_wrongly_listed": [x for x in recipes_lines if x in {b["func"] for b in spec["bugs"] if b["file"] == "more.py"}],
           "per_key": {k: ("correct" if v["clean"] else "wrong") for k, v in per.items()}, "per_ticket": per,
           "counts": {"correct": counts["clean"], "wrong": n - counts["clean"], "blank": 0, "stale": 0},
           "fixes_lines": len(fixes), "tickets_fetched": len(delivered), "tickets_delivered_twice": len(log) - len(delivered),
           "audit": audit}
json.dump(details, open(f"{LOG}/details.json", "w"), indent=1)
open(f"{LOG}/reward.txt", "w").write(f"{score:.4f}\n")
print(f"repair score {score:.4f} fixed {counts['fixed']}/{n} clean {counts['clean']}/{n} rules "
      + " ".join(f"{r} {v['kept']}/{v['applies']}" for r, v in rules.items())
      + f" stray_unmarked={len(stray)} tests_touched={len(tests_touched)} tickets={len(delivered)} void={void}"
      + (f" audit {audit['right']}/{audit['asked']}" if audit else ""))
