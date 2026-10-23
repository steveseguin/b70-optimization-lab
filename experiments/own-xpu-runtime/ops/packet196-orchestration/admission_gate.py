#!/usr/bin/env python3
"""Recompute the qualified diet screen from raw tokens/timings and its unchanged oracle. CPU only."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path('/home/steve/llm-optimizations');X=ROOT/'experiments/own-xpu-runtime'
P=X/'stage2/packet196-onecard-diet-chain';D=X/'stage2/packet58-onecard-diet-engine'
S=D/'screen/evidence/card0-58de-v5-a/resident/WSCREEN';LABELS=['A0','B0','A1','B1','A2']
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def evaluate():
 sys.path.insert(0,str(D/'screen'))
 import suite_driver as driver, mechanism, compare_bracket, views
 manifest=driver.oracle_inputs();output=S/'run';driver.verify_lookup_views(output,'resident')
 rows=[]
 for label in LABELS:
  row=driver.summarize(output,'WSCREEN',manifest,label,128)
  assert row['passed'] and row['request_count']==12 and all(r['exact_oracle'] for r in row['requests'])
  row.update(label=label,view='max23+diet' if label.startswith('B') else 'max23');rows.append(row)
 comparison=compare_bracket.compare(rows)
 readout=mechanism.readout(output/'run',LABELS,None,True)
 decision=compare_bracket.s58de_decision(comparison,readout)
 stored=json.loads((S/'summary.json').read_text());window=json.loads((S/'window.json').read_text())
 assert stored['passed'] and stored['device_executed'] and comparison['rates']==stored['rates']
 assert decision==stored['s58de_decision'], 'decision differs from raw data'
 assert decision['screen_winner'] and decision['chain_rule'] and not decision['kill_rules_fired']
 assert window['passed'] and window['device_executed'] and window['returncode']==0 and window['stop_reasons']==[]
 assert window['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip()
 assert window['memory_admission']['required_bytes']==100487123456 and window['postload_memory']['full_cache_bytes']==23049601024
 drm=[]
 for file in (output/'run').rglob('drm-memory-*.txt'):
  for line in file.read_text().splitlines():
   if line.startswith('drm-total-vram0:'):
    value,unit=line.split(':',1)[1].split();drm.append(int(value)*{'KiB':1024,'MiB':1024**2,'B':1}[unit])
 assert drm and max(drm)<=30500000000
 ledger=json.loads((ROOT/'scripts/packet58_onecard_record_threshold.json').read_text())['records'][-1]
 assert ledger['reference_submission']=='cmvkcqznb002lng01fsrhjn7t' and ledger['threshold_tok_s']==36.60251162011413
 files=[S/'summary.json',S/'window.json',*[f for f in output.rglob('*') if f.is_file() and f.suffix in ('.json','.jsonl','.txt','.tsv')],
        *[D/'screen'/n for n in ('suite_driver.py','suite_metrics.py','mechanism.py','compare_bracket.py','views.py','resident_receipt.py','oracle-binding.json')]]
 records=[dict(name=f.name,parent_relpath=str(f.relative_to(ROOT)),parent_digest=sha(f)) for f in sorted(set(files))]
 return dict(schema='packet196.admission.v1',passed=True,device_executed=False,model_reads=False,screen_packet=D.name,
   rates=comparison['rates'],decision=decision,exact_requests=60,drm_peak_bytes=max(drm),boot_id=window['boot_id'],
   record_bar=dict(reference_submission=ledger['reference_submission'],threshold_tok_s=ledger['threshold_tok_s']),files=records,
   note='Raw fixed-suite token/timing replay and per-view kernel boundaries; no new model execution. Screen and chain admission pass; a new record remains unmeasured.')
def main():
 row=evaluate();out=P/'evidence/diet-admission.json'
 if '--verify' in sys.argv:
  assert json.loads(out.read_text())==row,'admission changed'
 else:out.write_text(json.dumps(row,indent=2,ensure_ascii=False)+'\n')
 print(json.dumps({k:row[k] for k in ('passed','rates','exact_requests','drm_peak_bytes')}))
if __name__=='__main__':main()
