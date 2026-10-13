#!/usr/bin/env python3
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
if spec.get("audit") and mode != "careless":
    open("/app/AUDIT.md", "w").write("".join(f"{tk['ticket']} | {tk['func']}\n" for tk in spec["bugs"] if tk["ticket"] in spec["audit"]))
