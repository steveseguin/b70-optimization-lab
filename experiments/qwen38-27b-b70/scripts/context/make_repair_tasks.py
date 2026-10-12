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
     R3  only for fixes in recipes.py: the function's name also goes into /app/RECIPES.txt   (a rule by condition:
         listing a more.py fix there breaks it too; the recipes.py tickets come after its notice)

  The grader (tests/grade.py, run in the container after the agent stops) restores the original tests, runs each
  ticket's test classes against the agent's library, and checks each rule for every ticket that came after it:
  a ticket is `fixed` when its tests pass and `clean` when it is fixed and no rule in force was broken for it.
  reward = clean / N.

  The task container: the harness cannot run it without network on this host (its `no-network` mode needs docker
  buildx for a sidecar image), so pip and anything that honours the proxy variables are pointed at a dead address
  and the instruction forbids fetching another copy of the library; the runner lists any command of a run that
  touches pip, curl, wget, urllib or the proxy variables.

  Safety: the builder's own screening and self-test run in containers without network; every test process is capped at
  128 MiB of address space, every shell the agent starts at 160 MiB, the task container at 384 MiB (the whole
  reference suite, 671 tests in 156 classes, passes class by class under 96 MiB). The first caps were 800 MiB, 1.5 GiB
  and 2 GiB, and the first run beside the model server lasted 40 seconds: at its 13th command the agent ran
  `t IchunkedTests` on a defect that never stops, the test grew by 70 MiB a second, and the server's memory guard
  (floor 1.6 GiB, about 0.55 GiB of room at that moment) stopped the server before the cap was reached. A cap has to
  be smaller than the room on the host it protects, not merely finite; no two chosen defects break each other's
  test class. Screening keeps several cores busy for some minutes: run the builder only when no model server is up.
  The builder ends with a self-test (the real image, `next` through the queue, `t` once, six scripted solutions with
  known scores) and exits non-zero if any count is off.

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
import sys, unittest, json, resource
resource.setrlimit(resource.RLIMIT_AS, (128 * 2**20, 128 * 2**20))     # a defect that never stops must not eat the host (see the module text)
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


RUN_ALL = r'''
import sys, unittest, json, resource
resource.setrlimit(resource.RLIMIT_AS, (128 * 2**20, 128 * 2**20))
suite = unittest.TestSuite()
for mod in ("test_more", "test_recipes"):
    suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(__import__("tests." + mod, fromlist=["x"])))
r = unittest.TextTestRunner(stream=open("/dev/null", "w"), verbosity=0).run(suite)
print(json.dumps({"run": r.testsRun, "bad": [t.id() for t, _ in r.failures + r.errors]}))
'''


def run_all(root: Path, timeout: int = 240) -> dict | None:
    try:
        p = subprocess.run([sys.executable, "-I", "-c", "import sys; sys.path.insert(0, %r)\n" % str(root) + RUN_ALL],
                           cwd=root, capture_output=True, text=True, timeout=timeout)
        return json.loads(p.stdout.strip().splitlines()[-1]) if p.stdout.strip() else None
    except (subprocess.TimeoutExpired, json.JSONDecodeError, IndexError):
        return None


def screen_one(job: tuple) -> dict | None:
    """One candidate: its function's own test class must fail (1 to MAX_FAIL tests, no hang); then the whole suite
    is run once to count the tests it breaks elsewhere (`collateral`: a defect in a helper breaks its callers)."""
    src_root, work, name, src, cls, c, i = job
    root = Path(work) / f"w{i}"
    if root.exists():
        shutil.rmtree(root)
    shutil.copytree(Path(src_root) / "more_itertools", root / "more_itertools")
    shutil.copytree(Path(src_root) / "tests", root / "tests")
    (root / "more_itertools" / name).write_text(apply(src, [c]))
    got = run_tests(root, TESTS[name], [cls])
    out = None
    if got and 1 <= len(got["bad"]) <= MAX_FAIL:
        every = run_all(root)
        if every is not None:
            own = f"tests.{TESTS[name]}.{cls}."
            mine = f"more_itertools.{name[:-3]}.{c['func']}"          # its own doctest (the suite loads them too)
            other = [t for t in every["bad"] if not t.startswith(own) and t != mine and not t.startswith(mine + ".")]
            # which other test classes break: a defect in a helper breaks its callers, and their ticket could not
            # be closed before this one
            out = dict(c, file=name, cls=cls, fails=len(got["bad"]), of=got["run"], collateral=len(other),
                       breaks=sorted({t.split(".")[2] if t.startswith("tests.") else t for t in other}))
    shutil.rmtree(root, ignore_errors=True)
    return out


def screen(src_root: Path, work: Path, out: Path, per_func: int = 4, workers: int = 4) -> None:
    """Every candidate (at most per_func per function, spread over the kinds of mutation) through screen_one,
    several at a time. Writes the survivors as JSON."""
    from concurrent.futures import ProcessPoolExecutor
    jobs = []
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
            random.Random(func).shuffle(cands)
            picked, kinds = [], set()
            for c in cands:                           # one of each kind first, then whatever is left
                if c["kind"] not in kinds:
                    picked.append(c)
                    kinds.add(c["kind"])
            picked += [c for c in cands if c not in picked]
            jobs += [(str(src_root), str(work), name, src, cls, c, len(jobs) + k) for k, c in enumerate(picked[:per_func])]
    keep = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for got in pool.map(screen_one, jobs):
            if got:
                keep.append(got)
                print(f"keep {got['file']}:{got['func']} line {got['line']} ({got['kind']}): {got['fails']}/{got['of']} tests of "
                      f"{got['cls']} fail, {got['collateral']} elsewhere", flush=True)
    out.write_text(json.dumps(keep, indent=1))
    print(f"{len(keep)} of {len(jobs)} mutations kept over {len({(k['file'], k['func']) for k in keep})} functions; "
          f"{len({(k['file'], k['func']) for k in keep if not k['collateral']})} functions have one that breaks nothing else")


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
open(D + "/.log", "a").write(json.dumps({"ticket": items[pos]["ticket"], "kind": items[pos]["kind"], "at": __import__("time").time()}) + "\n")
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
    cap = lambda: __import__("resource").setrlimit(__import__("resource").RLIMIT_AS, (128 * 2**20, 128 * 2**20))
    p = subprocess.run([sys.executable, "-m", "unittest", "-q", *names], cwd="/app", capture_output=True, text=True, timeout=60, preexec_fn=cap)
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
RUN chmod +x /usr/local/bin/next /usr/local/bin/t && echo 'ulimit -v 163840 2>/dev/null' > /etc/repair-limits.sh \
    && sleep 1 && touch /opt/repair/.built
ENV BASH_ENV=/etc/repair-limits.sh
ENV http_proxy=http://127.0.0.1:9 https_proxy=http://127.0.0.1:9 HTTP_PROXY=http://127.0.0.1:9 HTTPS_PROXY=http://127.0.0.1:9 \\
    PIP_NO_INDEX=1 PIP_DISABLE_PIP_VERSION_CHECK=1
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
- Work from the code in /app only: do not fetch, install or copy any other copy of this library.
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
score = 0.0 if void else counts["clean"] / n
details = {"kind": "repair", "n": n, "correct": counts["clean"], "fixed": counts["fixed"], "clean": counts["clean"], "rules": rules,
           "score": score, "score_raw": counts["clean"] / n, "stray_unmarked_lines": stray[:40], "tests_touched": tests_touched,
           "void": void, "violations": tests_touched,
           "recipes_wrongly_listed": [x for x in recipes_lines if x in {b["func"] for b in spec["bugs"] if b["file"] == "more.py"}],
           "per_key": {k: ("correct" if v["clean"] else "wrong") for k, v in per.items()}, "per_ticket": per,
           "counts": {"correct": counts["clean"], "wrong": n - counts["clean"], "blank": 0, "stale": 0},
           "fixes_lines": len(fixes), "tickets_fetched": len(delivered), "tickets_delivered_twice": len(log) - len(delivered)}
json.dump(details, open(f"{LOG}/details.json", "w"), indent=1)
open(f"{LOG}/reward.txt", "w").write(f"{score:.4f}\n")
print(f"repair score {score:.4f} fixed {counts['fixed']}/{n} clean {counts['clean']}/{n} rules "
      + " ".join(f"{r} {v['kept']}/{v['applies']}" for r, v in rules.items())
      + f" stray_unmarked={len(stray)} tests_touched={len(tests_touched)} tickets={len(delivered)} void={void}")
'''


SOLVE = r'''#!/usr/bin/env python3
"""The scripted solution (also the builder's self-test): put the original line back for every ticket and follow
the rules in force. Modes that break one thing each: `careless` (no notice followed), `nofixes` (no FIXES.md),
`norecipes` (no RECIPES.txt), `allrecipes` (every fix listed in RECIPES.txt, also those in more.py)."""
import json, os, sys
mode = (sys.argv[1:] or ["solve"])[0]
here = "/solution" if os.path.exists("/solution/spec.json") else "/tests"       # the oracle agent has no /tests yet
spec = json.load(open(here + "/spec.json"))
at, mark = spec["rule_at"], spec["mark"]
for tk in spec["bugs"]:
    path = f"/app/more_itertools/{tk['file']}"
    now = open(path).read().split("\n")
    ref = open(f"{here}/reference/{tk['file']}").read().split("\n")
    line = ref[tk["line"] - 1]
    if tk["ticket"] > at["R1"] and mode != "careless":
        line = line + "  " + mark
    now[tk["line"] - 1] = line
    open(path, "w").write("\n".join(now))
    if tk["ticket"] > at["R2"] and mode not in ("careless", "nofixes"):
        open("/app/FIXES.md", "a").write(f"{tk['ticket']} | {tk['func']} | {tk['kind']}\n")
    if tk["ticket"] > at["R3"] and mode not in ("careless", "norecipes") and (tk["file"] == "recipes.py" or mode == "allrecipes"):
        open("/app/RECIPES.txt", "a").write(tk["func"] + "\n")
'''


def selftest(task: Path) -> None:
    """Build the task's image and, in a container without network, run `next` through the queue and `t` once, then
    the grader on the untouched library and on five scripted solutions that each break a known set of rules.
    The counts are known beforehand; any difference is a builder or grader defect."""
    spec = json.loads((task / "tests" / "spec.json").read_text())
    bugs, at, total = spec["bugs"], spec["rule_at"], spec["n_items"]
    n = len(bugs)

    def after(rule: str, keep=lambda b: True) -> int:
        return sum(b["ticket"] > at[rule] and keep(b) for b in bugs)

    want = {"none": (0, 0), "solve": (n, n), "careless": (n, n - after("R1")), "nofixes": (n, n - after("R2")),
            "norecipes": (n, n - after("R3", lambda b: b["file"] == "recipes.py")),
            "allrecipes": (n, n - after("R3", lambda b: b["file"] == "more.py"))}
    tag = f"repair-selftest:{task.name}"
    subprocess.run(["docker", "build", "-q", "--network", "none", "-t", tag, str(task / "environment")], check=True, capture_output=True)
    script = (f"set -e; cp -r /app /app0; for i in $(seq 1 {total + 1}); do next; done > /tmp/next.out; "
              "echo \"next: $(grep -c '^TICKET' /tmp/next.out) tickets, $(grep -c 'QUEUE EMPTY' /tmp/next.out) end\"; "
              f"echo \"t: $(t {bugs[0]['cls']} | tail -1)\"; "
              "for mode in " + " ".join(want) + "; do rm -rf /app /logs; cp -r /app0 /app; mkdir -p /logs; "
              "if [ $mode != none ]; then python3 /solution/solve.py $mode; fi; echo \"== $mode\"; bash /tests/test.sh; done")
    try:
        p = subprocess.run(["docker", "run", "--rm", "--network", "none", "--memory", "384m", "--memory-swap", "384m", "--cpus", "2",
                            "-v", f"{(task / 'tests').resolve()}:/tests:ro", "-v", f"{(task / 'solution').resolve()}:/solution:ro",
                            tag, "bash", "-c", script], capture_output=True, text=True)
    finally:
        subprocess.run(["docker", "rmi", "-f", tag], capture_output=True)
    print(p.stdout.strip() or p.stderr.strip()[-2000:])
    got = {m: (int(a), int(b)) for m, a, b in re.findall(r"== (\w+)\nrepair score [\d.]+ fixed (\d+)/\d+ clean (\d+)/", p.stdout)}
    ok = (got == want and f"next: {total} tickets, 1 end" in p.stdout and re.search(r"t: (FAILED|OK)", p.stdout)
          and f"tickets={total}" in p.stdout)
    print("self-test", "OK" if ok else f"FAILED: got {got}, expected {want} (and the `next` and `t` lines above)")
    if not ok:
        sys.exit(1)


def build(src_root: Path, kept: list[dict], out: Path, n: int, seed: int, image: str, rule_at: tuple[int, ...]) -> None:
    rng = random.Random(seed)
    total = n + len(NOTICES)
    if len(set(rule_at)) != len(NOTICES) or sorted(rule_at) != list(rule_at) or rule_at[0] < 2 or rule_at[-1] >= total:
        sys.exit(f"--rule-at {rule_at}: three rising ticket numbers are needed, each followed by a bug (2 .. {total - 1})")
    by_func: dict[tuple[str, str], list[dict]] = {}
    for k in kept:
        by_func.setdefault((k["file"], k["func"]), []).append(k)
    funcs = sorted(by_func)
    rng.shuffle(funcs)
    funcs.sort(key=lambda f: min(c.get("collateral", 0) for c in by_func[f]) > 0)       # stable: the clean ones first
    # No ticket's defect may break another ticket's test class (that ticket could not be closed before this one).
    want = {"recipes.py": max(n // 4, 1)}                 # a quarter from recipes.py: the rule by condition needs them
    want["more.py"] = n - want["recipes.py"]
    bugs, classes, damaged = [], set(), set()
    for quota in (True, False):                           # second pass: fill from either file
        for f in funcs:
            if len(bugs) >= n or any((b["file"], b["func"]) == f for b in bugs):
                continue
            if quota and sum(b["file"] == f[0] for b in bugs) >= want[f[0]]:
                continue
            for c in sorted(by_func[f], key=lambda c: c.get("collateral", 0)):
                if c["cls"] not in damaged and c["cls"] not in classes and not set(c.get("breaks", [])) & classes:
                    bugs.append(c)
                    classes.add(c["cls"])
                    damaged.update(c.get("breaks", []))
                    break
    if len(bugs) < n:
        sys.exit(f"only {len(bugs)} defects that leave each other's tests alone; asked for {n}")
    print(f"chosen: {sum(not b.get('collateral') for b in bugs)} of {n} break only their own test class; "
          f"{sum(b['file'] == 'recipes.py' for b in bugs)} in recipes.py")
    # order: the recipes.py tickets go after the third notice (its rule is about them), the rest are shuffled
    slots = [t for t in range(1, total + 1) if t not in rule_at]
    late = [t for t in slots if t > rule_at[2]]
    rec, more = [b for b in bugs if b["file"] == "recipes.py"], [b for b in bugs if b["file"] != "recipes.py"]
    rng.shuffle(rec)
    rng.shuffle(more)
    where = dict(zip(rng.sample(late, min(len(rec), len(late))), rec))
    rest = iter(rec[len(where):] + more)
    bugs = [where[t] if t in where else next(rest) for t in slots]
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
    for b in bugs:
        while number + 1 in notices:
            number += 1
            rule, text = notices[number]
            at[rule] = number
            items.append({"ticket": number, "kind": "NOTICE", "text": f"TICKET {number}/{total} (NOTICE) From the maintainer. " + text.format(mark=MARK)})
        number += 1
        items.append({"ticket": number, "kind": "BUG", "text":
                      f"TICKET {number}/{total} (BUG) `{b['func']}`{' (a class)' if b.get('unit') == 'class' else ''} in more_itertools/{b['file']} gives wrong results. "
                      f"Its tests: `t {b['cls']}` (some fail). Fix it, check, then run `next`."})
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
    (tests / "reference").mkdir()
    for name in FILES:
        shutil.copy(src_root / "more_itertools" / name, tests / "reference" / name)
    (task / "solution").mkdir()
    shutil.copytree(tests / "reference", task / "solution" / "reference")       # the oracle agent runs before /tests exists
    shutil.copy(tests / "spec.json", task / "solution" / "spec.json")
    (task / "solution" / "solve.py").write_text(SOLVE)
    (task / "solution" / "solve.sh").write_text("#!/bin/bash\npython3 /solution/solve.py \"$@\"\n")
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
        mode = "repair"
        n_bugs = {n}
        n_items = {total}
        rule_tickets = {json.dumps(at)!r}

        [verifier]
        timeout_sec = 1800.0
        collect = []

        [verifier.env]

        [agent]
        timeout_sec = 132300.0

        [environment]
        memory_mb = 384
        cpus = 2
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
    ap.add_argument("--workers", type=int, default=6, help="candidates screened at a time")
    a = ap.parse_args()
    src = Path(a.src)
    if a.screen:
        screen(src, Path(a.work), Path(a.screen), workers=a.workers)
        return
    if not a.out:
        ap.error("--out is needed")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    kept_file = out / "mutations.json"
    if not kept_file.exists() or not json.loads(kept_file.read_text()):
        # The library's tests run only in a container: no network, read-only source, the script mounted beside it.
        # Each test process is capped at 128 MiB of address space (RUN_CLASS, RUN_ALL), the container at 6 GiB with no
        # swap beyond it. Run this only when no model server is up: it keeps several cores busy for some minutes.
        subprocess.run(["docker", "run", "--rm", "--network", "none", "--memory", "6g", "--memory-swap", "6g", "--cpus", str(a.workers),
                        "-v", f"{src.resolve()}:/src:ro", "-v", f"{Path(__file__).resolve()}:/builder/make_repair_tasks.py:ro",
                        "-v", f"{out.resolve()}:/out", a.image, "python3", "-I", "/builder/make_repair_tasks.py",
                        "--src", "/src", "--screen", "/out/mutations.json", "--workers", str(a.workers)], check=True)
    kept = json.loads(kept_file.read_text())
    build(src, kept, out, a.n, a.seed, a.image, tuple(int(x) for x in a.rule_at.split(",")))
    selftest(out / f"repair-n{a.n}-s{a.seed}")


if __name__ == "__main__":
    main()
