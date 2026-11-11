# Mean act_freq (MHz) per tile over a run's telemetry samples with freq > 300 MHz; the run window is
# (previous named log's mtime, this log's mtime] in monotonic time (offset from now). The first name's window
# starts 60 s before its log's mtime. Usage: clk_runs.py RUNDIR name1 name2 ...
import os, sys, time
d = sys.argv[1]; names = sys.argv[2:]
off = time.time() - time.monotonic()
rows = [l.split() for l in open(d + "/telemetry.smp")]
ends = [os.path.getmtime(f"{d}/{n}.log") - off for n in names]
for i, n in enumerate(names):
    t1 = ends[i]; t0 = ends[i - 1] if i else t1 - 60
    per = {}
    for r in rows:
        t = float(r[0])
        if t0 < t <= t1 and r[2].isdigit() and int(r[2]) > 300:
            per.setdefault(int(r[1]), []).append(int(r[2]))
    print(n, ' '.join(f"t{k}:{sum(v)/len(v):.0f}({len(v)})" for k, v in sorted(per.items())))
