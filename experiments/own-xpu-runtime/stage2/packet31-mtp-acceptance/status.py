"""Read-only progress and resource sampler for the two CPU numerical jobs."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,json
P=Path(__file__).resolve().parent

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--draft-pid",type=int);a=ap.parse_args()
    receipt=json.loads((P/"target-run-receipt.json").read_text());pids=[];progress={}
    for name,row in receipt["prompts"].items():
        d=P/"build"/name
        positions=[json.loads(l) for l in (d/"positions.jsonl").read_text().splitlines()]
        draft=P/"build"/(name+"-draft.jsonl")
        rows=[json.loads(l) for l in draft.read_text().splitlines()] if draft.exists() else []
        progress[name]=dict(target_positions=len(positions),draft_scored=len(rows),full_draft_hits={k:sum(r["sources"][k]["hit"] for r in rows) for k in ("mtp_fp8_iq3","mtp_int8_iq3","mtp_fp8_official")},target_finished=row.get("returncode")==0)
        if "returncode" not in row:pids.append(row["pid"])
    if a.draft_pid:pids.append(a.draft_pid)
    resources={}
    for pid in pids:
        f=Path(f"/proc/{pid}/status")
        if f.exists():
            st={line.split(":")[0]:line.split(":",1)[1].strip() for line in f.read_text().splitlines() if ":" in line}
            resources[str(pid)]={k:st[k] for k in ("RssAnon","VmRSS","VmHWM","Threads")}
    sample=dict(utc=datetime.now(timezone.utc).isoformat(),resources=resources,progress=progress)
    with (P/"resource-samples.jsonl").open("a") as f:f.write(json.dumps(sample)+"\n")
    print(json.dumps(sample))
if __name__=="__main__":main()
