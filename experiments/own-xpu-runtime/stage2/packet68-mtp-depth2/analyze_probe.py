"""Summarize actual discarded-row costs only after all thirteen exact streams."""
import argparse,json,statistics
from pathlib import Path
P=Path(__file__).resolve().parent

def main():
 ap=argparse.ArgumentParser();ap.add_argument('output',type=Path);a=ap.parse_args()
 w=json.loads((a.output/'window.json').read_text());assert w['passed'] and w['device_executed']
 paths=sorted((a.output/'run').rglob('depth2-cost.jsonl'))
 rows=[dict(json.loads(line),source=str(p)) for p in paths for line in p.read_text().splitlines()]
 assert len(paths)==13 and len(rows)==39,(len(paths),len(rows))
 assert all(r['discarded'] and not r['cancelled'] and not r['batched_verifier'] for r in rows)
 out=dict(schema='packet68.cost-probe.v1',passed=True,diagnostic=True,device_executed=True,rows=rows,
  medians={k:statistics.median(r[k] for r in rows) for k in ('half_with_snapshot_ms','half_gpu_ms','restore_ms')},
  limitation='23/25 lane-B real composition, hypothetical repeated latest input token; not an M=3 batched verifier and not a speed result')
 print(json.dumps(out,indent=2))
if __name__=='__main__':main()
