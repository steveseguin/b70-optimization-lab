# Packet80 one-shot preparation

Run with nice19, CPUs8-15,24-31, Python-B and stdin /dev/null:

    nice -n 19 taskset -c 8-15,24-31 python3 -B experiments/own-xpu-runtime/ops/packet80-orchestration/orchestrate.py </dev/null

This helper never launches the printed chain command. It reads each packet's
own compare/best logic in an isolated process, selects only both-lane exact
13/13 improving winners, fast-reseals the composition, runs the CPU/chain/input/
storage/window/queue prechecks and writes ready.json. Missing evidence keeps
that packet's choice at production. Dense stays production and experts wide64.
Rerun when new evidence arrives. A changed seal or started chain refuses.
Preparation passed on October17: ordered host cleanup, fast route, fused norm,
hc-wide, rank1 at24/24, wide64 experts and production dense. Packet79 had no
lane-A winner. ready.json is authoritative only when ready=true and
verify_ready.py passes. Combined device exactness and performance stay pending;
the chain command has not been launched.

Retention: ready.json, ready-first-pass.json and screens-current.json exceed
1MiB because they retain each packet's comparison rows and individual source
and receipt hashes. Keep these maps: verify_ready.py consumes the latest ready
map, and the screen snapshot explains selection. Rerunning orchestrate.py
regenerates current maps and check logs from the frozen packets and local
build. The first-pass snapshot is historical; the latest ready.json and logs
are the current verification pair. Shared wrapper evidence remains at the
hash-pinned paths recorded in those maps.
