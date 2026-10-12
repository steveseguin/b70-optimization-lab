"""Sequential low-priority CPU capture. Five numerical threads, no device access."""
from pathlib import Path
import hashlib,json,os,subprocess,time,signal
P=Path(__file__).resolve().parent; B=P/"build"
names=("incident-retrospective","code-review","customer-email","benchmark-analysis")
def save(p,x):p.write_text(json.dumps(x,indent=2)+"\n")
assert os.getpriority(os.PRIO_PROCESS,0)==19
receipt={"device_executed":False,"threads":5,"prompts":{}}
for name in names:
    inp=B/("input-"+name); out=B/name
    data=json.loads((inp/"input.json").read_text())
    cmd=[str(B/"target-cpu"),str(inp),str(out),"10800","64"]
    start=time.monotonic()
    with (B/(name+".log")).open("w") as log:
        child=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,env={**os.environ,"OMP_NUM_THREADS":"5","MKL_NUM_THREADS":"1","OPENBLAS_NUM_THREADS":"1","IQ3_MODEL_DIR":data["model_dir"]})
        for sig in (signal.SIGTERM,signal.SIGINT):
            signal.signal(sig,lambda signum,frame: child.send_signal(signum) if child.poll() is None else None)
        row={"pid":child.pid,"command":cmd,"peak_rss_anon_kib":0};receipt["prompts"][name]=row
        while child.poll() is None:
            try:
                status=Path(f"/proc/{child.pid}/status").read_text()
                anon=int(next(l for l in status.splitlines() if l.startswith("RssAnon:")).split()[1])
                row["peak_rss_anon_kib"]=max(row["peak_rss_anon_kib"],anon)
                if anon>7_500_000:child.terminate();row["memory_stop"]=True
            except (FileNotFoundError,StopIteration):pass
            save(P/"target-run-receipt.json",receipt);time.sleep(5)
        row.update(returncode=child.returncode,elapsed_seconds=time.monotonic()-start)
    save(P/"target-run-receipt.json",receipt)
    if child.returncode:raise RuntimeError(name+" failed")
