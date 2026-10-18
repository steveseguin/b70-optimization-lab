# Packet58g CPU build and validation

Run serially from the repository root. Never execute the device binaries here.
Every command uses nice 19, helper cores, Python -B and null stdin.

```bash
P=experiments/own-xpu-runtime/stage2/packet58g-onecard
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/build.py" gnu-host < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/build.py" device < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/fullshape_submit_gate.py" < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/postload_allocation_gate.py" < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/k1_cpu_gate.py" < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/test_engine_reset.py" < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/mask_cpu_gate.py" < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/admission_cpu_gate.py" < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/python_gates.py" < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/seal.py" < /dev/null
nice -n 19 taskset -c 8-15,24-31 python3 -B "$P/seal.py" --verify < /dev/null
```

The separate `fullshape-submit` CPU executable links verbatim device validation
mirrors for generic adapter/performance paths in addition to the common actual
p28, p30, p33, p39, p49c and p49d submitters. The p54 route/recurrence checks are
in p49d_route.hpp, p49d_recurrence.hpp and p49d_submit.cpp in this lineage.
All selected paths are reached by actual prepare_commands at production size;
there are no manually fabricated Matrix rows or small fake address allocations.

The mock uses distinct mmap reservations with complete production byte extents,
page alignment, no populated weight pages and no compute. The real owner/Arena
and cache initialization remain in the loop. Only payload reads/copies and kernel
execution are replaced. 3,446 allocation rows total 72,920,824,692 logical bytes;
24,287,732,980 device bytes exactly match the failed 58f live log. This is virtual
address reservation, not 73 GB of RAM. Gates record and bound actual RSS.

Miniature reset tests retain the normal host executable because miniature
synthetic shapes are deliberately outside the production device ABI.
K1 now exercises actual p28 indirect IQ3 against unchanged direct p39 output.
Both binary modes are compiled one at a time. Build scratch remains below 1 GB.
Full-size scratch is deleted automatically. No live protocol file is used by tests.
