"""Reuse full-logit reference comparisons only after every captured byte repeats."""
import hashlib,json,sys
from pathlib import Path
P=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def inventory(root):
 return {str(f.relative_to(root)):sha(f) for pattern in ('row-*/*.bf16','row-*/*.bin','draft-final-state/*.bin') for f in root.glob(pattern)}
def main(name):
 run=json.loads((P/f'capture-run-{name}.json').read_text());old=run['previous']
 assert run['passed'] and old['passed']
 current_input=json.loads((P/f'capture-input-{name}.json').read_text())
 original=P.parent/'packet36-draft'
 old_input=json.loads((original/f'capture-input-{name}.json').read_text())
 assert current_input['streams']==old_input['streams'] and current_input['target_rows_sha256']==old_input['target_rows_sha256']
 def table_rows(path):
  return [line.split()[:3] for line in path.read_text().splitlines()]
 assert table_rows(P/'build'/f'capture-{name}.tsv')==table_rows(original/'build'/f'capture-{name}.tsv')
 now=inventory(Path(run['output']));before=inventory(Path(old['output']))
 assert now and now==before
 assert (Path(run['output'])/'draft-capture.jsonl').read_bytes()==(Path(old['output'])/'draft-capture.jsonl').read_bytes()
 report_path=original/f'agreement-{name}.json';report=json.loads(report_path.read_text())
 previous_repeat=json.loads((P/f'capture-repeat-{name}.json').read_text())
 assert previous_repeat['binary_sha256']==old['binary_sha256']
 assert previous_repeat['sha256']==before and previous_repeat['original_comparison_sha256']==sha(report_path)
 for row in report['rows']:assert row['logits_sha256']==now[f"row-{row['position']}/logits.bf16"]
 receipt=dict(passed=True,device_executed=False,prompt=name,previous_binary_sha256=old['binary_sha256'],
              binary_sha256=run['binary_sha256'],files=len(now),sha256=now,
              original_comparison_sha256=sha(report_path),
              reason='Final compile-time wrappers preserve every captured sample, logit and cache byte; full reference distances therefore remain exact.')
 path=P/f'capture-repeat-{name}.json';path.write_text(json.dumps(receipt,indent=2)+'\n')
 report['previous_binary_sha256']=report['binary_sha256'];report['binary_sha256']=run['binary_sha256']
 report['exact_repeat_receipt_sha256']=sha(path);report['reference_comparison_source']=str(report_path);report['reference_comparison_reexecuted']=False
 (P/report_path.name).write_text(json.dumps(report,indent=2)+'\n')
 from storage import discard
 old_root=Path(old['output']).resolve()
 if old_root.parent==(P/'build') and old_root.name.startswith('draft-cpu-') and old_root!=Path(run['output']).resolve():discard(old_root)
 print(name,len(now),'captured files repeat exactly')
if __name__=='__main__':main(sys.argv[1])
