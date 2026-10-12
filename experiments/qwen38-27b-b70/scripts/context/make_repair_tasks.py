#!/usr/bin/env python3
"""Build a "repair marathon" task: a real library with injected defects, worked through as tickets (2026-10-12).

Why: every context result so far is on one synthetic family (a prose ledger). This is real code with a real test
suite, and the three things a long agent session has to carry are all there: what it is doing, what it has done, and
standing instructions that arrived along the way ("from now on ...") and must still hold 200K tokens later.

The library is more-itertools 10.7.0 (MIT; sdist checked by sha256, never installed on the host). The builder

  1. finds single-token mutations of its functions (a comparison turned round, + for -, `and` for `or`, True for
     False, 0 for 1, a `not` dropped), one per function,
  2. keeps those that make the function's own test class fail (1 to MAX_FAIL tests) and do not hang; this screening
     runs the library's tests, so it runs inside a container without network (`--screen`, called by the builder),
  3. applies N of them at once and writes a task directory in the harness's layout:

     /app/more_itertools   the library with all N defects       /app/tests   its test suite, untouched
     t CLASS [CLASS ...]   runs those test classes (last lines of the output)
     next                  prints the next ticket, once: a BUG ("`chunked` in more.py gives wrong results; tests:
                           ChunkedTests") or a NOTICE that sets a standing rule from then on

  Standing rules (the instruction holds one; three arrive as NOTICE tickets, at tickets RULE_AT):
     R0  never change anything under /app/tests                                  (instruction)
     R1  every line added or changed in the library ends with the comment `# fixed`
     R2  after each fix, one line in /app/FIXES.md: `<ticket> | <function> | <a few words>`
     R3  only for fixes in recipes.py: the function's name also goes into /app/RECIPES.txt   (a rule by condition)

  The grader (tests/grade.py, run in the container after the agent stops) restores the original tests, runs each
  ticket's test classes against the agent's library, and checks each rule for every ticket that came after it:
  a ticket is `fixed` when its tests pass and `clean` when it is fixed and no rule in force was broken for it.
  reward = clean / N.

  make_repair_tasks.py --src DIR --out TASKS_DIR [--n 40] [--seed 0] [--image python:3.12-slim]
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import random
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

FILES = ("more.py", "recipes.py")
TESTS = {"more.py": "test_more", "recipes.py": "test_recipes"}
MAX_FAIL = 12
MARK = "# fixed"
SWAP_CMP = {ast.Lt: "<=", ast.LtE: "<", ast.Gt: ">=", ast.GtE: ">", ast.Eq: "!=", ast.NotEq: "=="}
CMP_TEXT = {ast.Lt: "<", ast.LtE: "<=", ast.Gt: ">", ast.GtE: ">=", ast.Eq: "==", ast.NotEq: "!="}


# ------------------------------------------------------------------ mutations (text edits found through the AST)
def offsets(src: str) -> list[int]:
    out, n = [0], 0
    for line in src.splitlines(keepends=True):
        n += len(line.encode())
        out.append(n)
    return out


def candidates(src: str) -> list[dict]:
    """Single-token edits inside top-level functions: {func, line, start, end, new, kind} with byte offsets into
    the source. Docstrings, defaults, decorators and annotations are left alone; one-line edits only."""
    data, lines, out = src.encode(), offsets(src), []
    tree = ast.parse(src)

    def at(node_line: int, col: int) -> int:
        return lines[node_line - 1] + col

    def between(a: ast.expr, b: ast.expr) -> tuple[int, int] | None:
        if a.end_lineno is None or a.end_col_offset is None or a.end_lineno != b.lineno:
            return None
        return at(a.end_lineno, a.end_col_offset), at(b.lineno, b.col_offset)

    def code(block: list[ast.stmt]) -> list[ast.stmt]:
        """The statements of a function or class without docstrings (those of its methods too)."""
        out = []
        for st in block:
            if isinstance(st, ast.Expr) and isinstance(st.value, ast.Constant) and isinstance(st.value.value, str):
                continue
            out.append(st)
        return out

    for fn in tree.body:                             # a unit is a top-level function, or a class with its methods
        if not isinstance(fn, (ast.FunctionDef, ast.ClassDef)) or fn.name.startswith("_"):
            continue
        body = code(fn.body)
        if isinstance(fn, ast.ClassDef):
            body = [st for meth in body if isinstance(meth, ast.FunctionDef) for st in code(meth.body)]
        for stmt in body:
            for node in ast.walk(stmt):
                edit = None
                if isinstance(node, ast.Compare) and len(node.ops) == 1 and type(node.ops[0]) in SWAP_CMP:
                    span = between(node.left, node.comparators[0])
                    old = CMP_TEXT[type(node.ops[0])]
                    if span and data[span[0]:span[1]].decode().strip() == old:
                        text = data[span[0]:span[1]].decode()
                        edit = (span[0], span[1], text.replace(old, SWAP_CMP[type(node.ops[0])]), "comparison")
                elif isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub)) and isinstance(node.right, ast.Constant) \
                        and type(node.right.value) is int and node.right.value in (1, 2):
                    span = between(node.left, node.right)
                    old, new = ("+", "-") if isinstance(node.op, ast.Add) else ("-", "+")
                    if span and data[span[0]:span[1]].decode().strip() == old:
                        edit = (span[0], span[1], data[span[0]:span[1]].decode().replace(old, new), "plus or minus")
                elif isinstance(node, ast.BoolOp) and len(node.values) == 2:
                    span = between(node.values[0], node.values[1])
                    old, new = ("and", "or") if isinstance(node.op, ast.And) else ("or", "and")
                    if span and data[span[0]:span[1]].decode().strip() == old:
                        edit = (span[0], span[1], data[span[0]:span[1]].decode().replace(old, new), "and / or")
                elif isinstance(node, ast.Constant) and type(node.value) is bool and node.lineno == node.end_lineno and node.end_col_offset is not None:
                    s, e = at(node.lineno, node.col_offset), at(node.lineno, node.end_col_offset)
                    if data[s:e].decode() == str(node.value):
                        edit = (s, e, str(not node.value), "True / False")
                elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not) and node.lineno == node.operand.lineno:
                    s, e = at(node.lineno, node.col_offset), at(node.operand.lineno, node.operand.col_offset)
                    if data[s:e].decode().strip() == "not":
                        edit = (s, e, "", "a dropped not")
                if edit:
                    line = src.encode()[:edit[0]].count(b"\n") + 1
                    out.append({"func": fn.name, "line": line, "start": edit[0], "end": edit[1], "new": edit[2], "kind": edit[3],
                                "unit": "class" if isinstance(fn, ast.ClassDef) else "function"})
    return out


def apply(src: str, edits: list[dict]) -> str:
    data = src.encode()
    for e in sorted(edits, key=lambda e: -e["start"]):
        data = data[:e["start"]] + e["new"].encode() + data[e["end"]:]
    return data.decode()


def test_classes(test_src: str) -> dict[str, str]:
    """{function name as the tests spell it, lower-case without underscores: class name}."""
    out = {}
    for n in ast.parse(test_src).body:
        if isinstance(n, ast.ClassDef) and n.name.lower().endswith(("tests", "test")):
            key = re.sub(r"tests?$", "", n.name.lower())
            out[key] = n.name
    return out


# ------------------------------------------------------------------ screening (runs INSIDE the container)
RUN_CLASS = r'''
import sys, unittest, json
mod, classes = sys.argv[1], sys.argv[2:]
suite = unittest.TestSuite()
m = __import__("tests." + mod, fromlist=["x"])
for c in classes:
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(getattr(m, c)))
r = unittest.TextTestRunner(stream=open("/dev/null", "w"), verbosity=0).run(suite)
print(json.dumps({"run": r.testsRun, "bad": [t.id() for t, _ in r.failures + r.errors]}))
'''


def run_tests(root: Path, mod: str, classes: list[str], timeout: int = 20) -> dict | None:
    try:
        p = subprocess.run([sys.executable, "-I", "-c", "import sys; sys.path.insert(0, %r)\n" % str(root) + RUN_CLASS, mod, *classes],
                           cwd=root, capture_output=True, text=True, timeout=timeout)
        return json.loads(p.stdout.strip().splitlines()[-1]) if p.stdout.strip() else None
    except (subprocess.TimeoutExpired, json.JSONDecodeError, IndexError):
        return None


def screen(src_root: Path, work: Path, out: Path, per_func: int = 4) -> None:
    """For every candidate (at most per_func per function, spread over kinds): does the function's own test class
    fail, without hanging? Writes the survivors as JSON."""
    keep = []
    for name in FILES:
        src = (src_root / "more_itertools" / name).read_text()
        classes = test_classes((src_root / "tests" / f"{TESTS[name]}.py").read_text())
        by_func: dict[str, list[dict]] = {}
        for c in candidates(src):
            by_func.setdefault(c["func"], []).append(c)
        for func, cands in sorted(by_func.items()):
            cls = classes.get(func.replace("_", "").lower())
            if not cls:
                continue
            base = run_tests(src_root, TESTS[name], [cls])
            if not base or base["bad"] or not base["run"]:
                continue                              # the class must pass on the untouched library
            rng = random.Random(func)
            rng.shuffle(cands)
            seen_kinds, tried = set(), 0
            for c in sorted(cands, key=lambda c: c["kind"] in seen_kinds):
                if tried >= per_func:
                    break
                tried += 1
                seen_kinds.add(c["kind"])
                if work.exists():
                    shutil.rmtree(work)
                shutil.copytree(src_root / "more_itertools", work / "more_itertools")
                shutil.copytree(src_root / "tests", work / "tests")
                (work / "more_itertools" / name).write_text(apply(src, [c]))
                got = run_tests(work, TESTS[name], [cls])
                if got and 1 <= len(got["bad"]) <= MAX_FAIL:
                    keep.append(dict(c, file=name, cls=cls, fails=len(got["bad"]), of=got["run"]))
                    print(f"keep {name}:{func} line {c['line']} ({c['kind']}): {len(got['bad'])}/{got['run']} tests of {cls} fail", flush=True)
    out.write_text(json.dumps(keep, indent=1))
    print(f"{len(keep)} mutations kept over {len({(k['file'], k['func']) for k in keep})} functions")


# ------------------------------------------------------------------ the task
NEXT = r'''#!/usr/bin/env python3
import json, os, sys
D = "/opt/repair"
items = [json.loads(l) for l in open(D + "/tickets.jsonl")]
pos_file = D + "/.pos"
pos = int(open(pos_file).read()) if os.path.exists(pos_file) else 0
if pos >= len(items):
    print(open(D + "/end_text").read()); sys.exit(0)
open(pos_file, "w").write(str(pos + 1))
print(items[pos]["text"])
'''

T_CMD = r'''#!/usr/bin/env python3
"""t CLASS [CLASS ...]: run those test classes of /app/tests against /app/more_itertools (the last 40 lines)."""
import subprocess, sys, re
if len(sys.argv) < 2:
    sys.exit("usage: t TestClass [TestClass ...]   (a class of tests/test_more.py or tests/test_recipes.py)")
names = []
for c in sys.argv[1:]:
    hit = [m for m in ("test_more", "test_recipes") if re.search(r"(?m)^class %s\(" % re.escape(c), open(f"/app/tests/{m}.py").read())]
    if not hit:
        sys.exit(f"t: no test class {c} in tests/test_more.py or tests/test_recipes.py")
    names.append(f"tests.{hit[0]}.{c}")
try:
    p = subprocess.run([sys.executable, "-m", "unittest", "-q", *names], cwd="/app", capture_output=True, text=True, timeout=60)
    out = (p.stdout + p.stderr).strip().splitlines()
except subprocess.TimeoutExpired:
    out = ["t: the tests did not finish within 60 seconds (an endless loop?)"]
print("\n".join(out[-40:]))
'''

DOCKERFILE = """FROM {image}
COPY more_itertools /app/more_itertools
COPY tests /app/tests
COPY tickets.jsonl end_text /opt/repair/
COPY next t /usr/local/bin/
RUN chmod +x /usr/local/bin/next /usr/local/bin/t && sleep 1 && touch /opt/repair/.built
WORKDIR /app
"""

INSTRUCTION = """You maintain the Python library in /app/more_itertools (its tests are in /app/tests). There is a queue
of {n_items} tickets. Run the command `next` to receive the next ticket; each ticket is printed once.

- A BUG ticket names a function that gives wrong results and the test class that shows it. Find the cause in the
  library, fix it, and check with `t TestClass` (it runs that class and prints the end of the output). Each bug is a
  small mistake in the named function (or in a method of the named class). Then fetch the next ticket.
- A NOTICE ticket is an instruction from the maintainer that holds from that ticket on, for every later ticket,
  until the queue is empty. There is nothing to fix for a NOTICE; fetch the next ticket.

Rules for the whole job:
- Never change anything under /app/tests. The tests are right; the library is wrong.
- Do not look for the tickets on disk; work through them with `next`, in order, one at a time.
- Use `t` for tests (one or a few classes); do not run the whole suite.
- When `next` says the queue is empty, the job is done.
"""

END_TEXT = "QUEUE EMPTY: no tickets are left. Check that everything the notices asked for is in place, then stop."

NOTICES = [
    ("R1", "From now on, every line you add or change in the library must end with the comment `{mark}` (two spaces "
           "before it). This holds for every fix from this ticket on, until the queue is empty."),
    ("R2", "From now on, after each fix, append one line to /app/FIXES.md in exactly this form: "
           "`<ticket number> | <function name> | <a few words on what was wrong>`. One line per BUG ticket, from this ticket on."),
    ("R3", "From now on, whenever a fix is in recipes.py (not more.py), also append the name of the fixed function "
           "as a line of its own to /app/RECIPES.txt. Fixes in more.py do not go into that file."),
]

GRADE = r'''#!/usr/bin/env python3
"""Grade a repair marathon (runs in the task container after the agent has stopped)."""
import hashlib, json, os, re, shutil, subprocess, sys
T, APP, LOG = "/tests", "/app", "/logs/verifier"
os.makedirs(LOG, exist_ok=True)
spec = json.load(open(f"{T}/spec.json"))
MARK = spec["mark"]

def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest() if os.path.exists(p) else None

tests_touched = [f for f, h in spec["tests_sha"].items() if sha(f"{APP}/tests/{f}") != h]
work = "/tmp/grade"
shutil.rmtree(work, ignore_errors=True)
os.makedirs(work)
shutil.copytree(f"{APP}/more_itertools", f"{work}/more_itertools")
shutil.copytree(f"{T}/orig_tests", f"{work}/tests")                    # the original tests, whatever the agent did

def run(mod, cls):
    code = ("import sys, unittest, json; sys.path.insert(0, %r)\n" % work +
            "m = __import__('tests.' + sys.argv[1], fromlist=['x'])\n"
            "s = unittest.defaultTestLoader.loadTestsFromTestCase(getattr(m, sys.argv[2]))\n"
            "r = unittest.TextTestRunner(stream=open('/dev/null', 'w'), verbosity=0).run(s)\n"
            "print(json.dumps({'run': r.testsRun, 'bad': len(r.failures) + len(r.errors)}))\n")
    try:
        p = subprocess.run([sys.executable, "-I", "-c", code, mod, cls], cwd=work, capture_output=True, text=True, timeout=60)
        return json.loads(p.stdout.strip().splitlines()[-1])
    except Exception:
        return {"run": 0, "bad": 1}

def read(p):
    try:
        return open(p, errors="replace").read()
    except OSError:
        return ""

fixes = [ln.strip() for ln in read(f"{APP}/FIXES.md").splitlines() if ln.strip()]
recipes_lines = [ln.strip().strip("`") for ln in read(f"{APP}/RECIPES.txt").splitlines() if ln.strip()]
rule_at = spec["rule_at"]
per, counts = {}, {"fixed": 0, "clean": 0}
rules = {r: {"applies": 0, "kept": 0} for r in ("R1", "R2", "R3")}
for tk in spec["bugs"]:
    key = f"t{tk['ticket']}"
    now = read(f"{APP}/more_itertools/{tk['file']}").splitlines()
    then = read(f"{T}/broken/{tk['file']}").splitlines()
    res = run(tk["module"], tk["cls"])
    fixed = res["run"] > 0 and res["bad"] == 0
    # the lines of this function that differ from the broken library handed out (by content, inside the function)
    def body(lines, name):
        """The lines of the top-level function or class `name` (to the next statement at the margin)."""
        out, on = [], False
        for ln in lines:
            if re.match(r"(def|class) %s\b" % re.escape(name), ln):
                on = True
            elif on and ln and not ln[0].isspace() and not ln.startswith(")"):
                break
            if on:
                out.append(ln)
        return out
    body_now, body_then = body(now, tk["func"]), body(then, tk["func"])
    old = {}
    for ln in body_then:
        old[ln] = old.get(ln, 0) + 1
    changed = []
    for ln in body_now:
        if old.get(ln, 0):
            old[ln] -= 1
        elif ln.strip():
            changed.append(ln)
    row = {"fixed": fixed, "changed_lines": len(changed), "tests": res}
    ok = fixed
    if tk["ticket"] > rule_at["R1"]:
        kept = bool(changed) and all(ln.rstrip().endswith(MARK) for ln in changed)
        row["R1"] = kept
        if fixed:
            rules["R1"]["applies"] += 1; rules["R1"]["kept"] += kept; ok = ok and kept
    if tk["ticket"] > rule_at["R2"]:
        kept = any(re.match(r"\W*%d\s*\|" % tk["ticket"], ln) and tk["func"] in ln for ln in fixes)
        row["R2"] = kept
        if fixed:
            rules["R2"]["applies"] += 1; rules["R2"]["kept"] += kept; ok = ok and kept
    if tk["ticket"] > rule_at["R3"] and tk["file"] == "recipes.py":
        kept = tk["func"] in recipes_lines
        row["R3"] = kept
        if fixed:
            rules["R3"]["applies"] += 1; rules["R3"]["kept"] += kept; ok = ok and kept
    row["clean"] = bool(ok)
    counts["fixed"] += fixed; counts["clean"] += bool(ok)
    per[key] = row
# R3 the other way round: a more.py function in RECIPES.txt is the rule applied where it does not hold
wrongly = [n for n in recipes_lines if n in {b["func"] for b in spec["bugs"] if b["file"] == "more.py"}]
n = len(spec["bugs"])
void = bool(tests_touched)
details = {"n": n, "correct": counts["clean"], "fixed": counts["fixed"], "clean": counts["clean"], "rules": rules,
           "recipes_wrongly_listed": wrongly, "tests_touched": tests_touched, "void": void, "violations": tests_touched,
           "per_key": {k: ("correct" if v["clean"] else "wrong") for k, v in per.items()}, "per_ticket": per,
           "counts": {"correct": counts["clean"], "wrong": n - counts["clean"], "blank": 0, "stale": 0},
           "fixes_lines": len(fixes), "tickets_fetched": int(read("/opt/repair/.pos") or 0)}
json.dump(details, open(f"{LOG}/details.json", "w"), indent=1)
score = 0.0 if void else counts["clean"] / n
open(f"{LOG}/reward.txt", "w").write(f"{score:.4f}\n")
print(f"repair score {score:.4f} fixed {counts['fixed']}/{n} clean {counts['clean']}/{n} rules "
      + " ".join(f"{r} {v['kept']}/{v['applies']}" for r, v in rules.items())
      + f" recipes_wrongly_listed={len(wrongly)} tests_touched={len(tests_touched)} void={void}")
'''


def build(src_root: Path, kept: list[dict], out: Path, n: int, seed: int, image: str, rule_at: tuple[int, ...]) -> None:
    rng = random.Random(seed)
    by_func: dict[tuple[str, str], list[dict]] = {}
    for k in kept:
        by_func.setdefault((k["file"], k["func"]), []).append(k)
    funcs = sorted(by_func)
    rng.shuffle(funcs)
    # a quarter from recipes.py (the rule by condition needs them), the rest from more.py
    want_rec = max(n // 4, 1)
    rec = [f for f in funcs if f[0] == "recipes.py"][:want_rec]
    more = [f for f in funcs if f[0] == "more.py"][:n - len(rec)]
    chosen = rec + more
    if len(chosen) < n:
        sys.exit(f"only {len(chosen)} functions with a usable mutation; asked for {n}")
    rng.shuffle(chosen)
    bugs = [rng.choice(by_func[f]) for f in chosen]
    task = out / f"repair-n{n}-s{seed}"
    if task.exists():
        shutil.rmtree(task)
    env, tests = task / "environment", task / "tests"
    env.mkdir(parents=True)
    tests.mkdir()
    shutil.copytree(src_root / "more_itertools", env / "more_itertools")
    shutil.copytree(src_root / "tests", env / "tests")
    shutil.copytree(src_root / "tests", tests / "orig_tests")
    (tests / "broken").mkdir()
    for name in FILES:
        text = apply((src_root / "more_itertools" / name).read_text(), [b for b in bugs if b["file"] == name])
        ast.parse(text)
        (env / "more_itertools" / name).write_text(text)
        (tests / "broken" / name).write_text(text)
    # tickets: the bugs in order, with the three notices put in before the tickets given by rule_at
    items, spec_bugs, at, number = [], [], {}, 0
    notices = dict(zip(rule_at, NOTICES))
    total = n + len(NOTICES)
    for b in bugs:
        while number + 1 in notices:
            number += 1
            rule, text = notices[number]
            at[rule] = number
            items.append({"ticket": number, "kind": "NOTICE", "text": f"TICKET {number}/{total} (NOTICE) From the maintainer. " + text.format(mark=MARK)})
        number += 1
        items.append({"ticket": number, "kind": "BUG", "text":
                      f"TICKET {number}/{total} (BUG) `{b['func']}`{' (a class)' if b.get('unit') == 'class' else ''} in more_itertools/{b['file']} gives wrong results. "
                      f"Its tests: `t {b['cls']}` ({b['fails']} of {b['of']} fail). Fix the function, check, then run `next`."})
        spec_bugs.append({"ticket": number, "func": b["func"], "file": b["file"], "cls": b["cls"], "module": TESTS[b["file"]],
                          "line": b["line"], "kind": b["kind"], "fails": b["fails"]})
    (env / "tickets.jsonl").write_text("".join(json.dumps(i) + "\n" for i in items))
    (env / "end_text").write_text(END_TEXT)
    (env / "next").write_text(NEXT)
    (env / "t").write_text(T_CMD)
    (env / "Dockerfile").write_text(DOCKERFILE.format(image=image))
    (task / "instruction.md").write_text(INSTRUCTION.format(n_items=total))
    sha = {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted((src_root / "tests").glob("*.py"))}
    (tests / "spec.json").write_text(json.dumps({"kind": "repair", "mark": MARK, "rule_at": at, "bugs": spec_bugs, "tests_sha": sha,
                                                 "n_items": total, "seed": seed, "library": "more-itertools 10.7.0"}, indent=1))
    (tests / "grade.py").write_text(GRADE)
    (tests / "test.sh").write_text("#!/bin/bash\nmkdir -p /logs/verifier\npython3 /tests/grade.py\n")
    (task / "solution").mkdir()
    (task / "solution" / "solve.sh").write_text("#!/bin/bash\necho 'no scripted solution: see tests/spec.json for the injected lines'\n")
    (task / "task.toml").write_text(textwrap.dedent(f"""\
        schema_version = "1.3"
        artifacts = []

        [task]
        name = "local/repair-n{n}-s{seed}"
        description = "repair marathon: more-itertools 10.7.0 with {n} injected defects, {total} tickets, three standing rules by notice"
        authors = []
        keywords = ["context", "repair"]

        [metadata]
        seed = {seed}
        kind = "repair"
        mode = "memory"
        n_bugs = {n}
        n_items = {total}
        rule_tickets = {json.dumps(at)!r}

        [verifier]
        timeout_sec = 600.0
        collect = []

        [verifier.env]

        [agent]
        timeout_sec = 132300.0

        [environment]
        """))
    print(f"wrote {task}: {n} bugs ({sum(b['file'] == 'recipes.py' for b in bugs)} in recipes.py), notices at tickets {at}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", required=True, help="the unpacked more-itertools 10.7.0 sdist")
    ap.add_argument("--out", help="directory for the task (and for mutations.json)")
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--image", default="python:3.12-slim")
    ap.add_argument("--rule-at", default="3,9,16", help="ticket numbers of the three notices")
    ap.add_argument("--screen", metavar="OUT_JSON", help="(inside the container) screen the mutations and write the survivors")
    ap.add_argument("--work", default="/tmp/repair-work")
    a = ap.parse_args()
    src = Path(a.src)
    if a.screen:
        screen(src, Path(a.work), Path(a.screen))
        return
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    kept_file = out / "mutations.json"
    if not kept_file.exists():
        # the library's tests run only in a container: no network, read-only source, the script mounted beside it
        subprocess.run(["docker", "run", "--rm", "--network", "none", "--memory", "1g", "--cpus", "2",
                        "-v", f"{src.resolve()}:/src:ro", "-v", f"{Path(__file__).resolve()}:/builder/make_repair_tasks.py:ro",
                        "-v", f"{out.resolve()}:/out", a.image, "python3", "-I", "/builder/make_repair_tasks.py",
                        "--src", "/src", "--screen", "/out/mutations.json"], check=True)
    kept = json.loads(kept_file.read_text())
    build(src, kept, out, a.n, a.seed, a.image, tuple(int(x) for x in a.rule_at.split(",")))


if __name__ == "__main__":
    main()
