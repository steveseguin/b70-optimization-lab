import re, sys, datetime as dt
# usage: srvlog.py server.log start_epoch end_epoch  (container log is UTC)
pat=re.compile(r'INFO (\d\d-\d\d \d\d:\d\d:\d\d) \[loggers\.py:\d+\] Engine 000: Avg prompt throughput: ([\d.]+) tokens/s, Avg generation throughput: ([\d.]+) tokens/s, Running: (\d+) reqs')
def parse(path, year=2026):
    out=[]
    with open(path, errors='replace') as f:
        for l in f:
            m=pat.search(l)
            if m:
                t=dt.datetime.strptime(f"{year}-{m.group(1)}", "%Y-%m-%d %H:%M:%S").replace(tzinfo=dt.timezone.utc).timestamp()
                out.append((t, float(m.group(2)), float(m.group(3)), int(m.group(4))))
    return out
def window(rows, t0, t1):
    P=G=0.0; busy=0; prev=None; n=0
    for t,p,g,r in rows:
        if t0 < t <= t1 + 10:
            d = 10.0 if prev is None or t-prev>11 else t-prev
            P+=p*d; G+=g*d; n+=1
            if r>0 or g>0: busy+=d
        prev=t
    return {'lines':n,'prompt_tok':round(P),'gen_tok':round(G),'active_s':round(busy)}
if __name__=='__main__':
    rows=parse(sys.argv[1]); print(window(rows, float(sys.argv[2]), float(sys.argv[3])))
