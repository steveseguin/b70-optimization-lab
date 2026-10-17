# Packet80 one-shot preparation

Run with nice19, CPUs8-15,24-31, Python-B and stdin /dev/null:

    nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/ops/packet80-orchestration/orchestrate.py </dev/null

This helper never launches the printed chain command. It reads each packet's
own compare/best logic in an isolated process, selects only both-lane exact
13/13 improving winners, fast-reseals the composition, runs the CPU/chain/input/
storage/window/queue prechecks and writes ready.json. Missing evidence keeps
that packet's choice at production. Dense stays production and experts wide64.
Rerun when new evidence arrives. A changed seal or started chain refuses.
Preparation in progress: ready.json is authoritative only when ready=true and
verify_ready.py passes. Combined device exactness and performance stay pending.
