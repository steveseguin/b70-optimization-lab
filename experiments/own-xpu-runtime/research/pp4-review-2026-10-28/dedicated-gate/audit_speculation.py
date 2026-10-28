#!/usr/bin/env python3
"""Offline ROW identity/work census; host envelopes are not GPU timings."""
import argparse,collections,hashlib,json,struct
from pathlib import Path

def audit(root):
 root=Path(root);d=json.loads((root/'driver-result.json').read_text());p=json.loads((root/'plan.json').read_text());rows=[json.loads(x) for x in (root/'commands.jsonl').read_text().splitlines()];assert d['passed'] and len(d['output_ids'])==512
 issued={x['row']:x for x in d['issued_proposals']};rejected={x['row'] for x in d['rejected_proposals']};accepted={x['row']['id'] for x in rows if x['event']=='completed' and x.get('stage')==0 and x['op']==25};decode=[x for x in rows if x['event']=='completed' and x.get('stage')==0 and x['op']==24 and x['row']['fixture']>1]
 summary=[]
 for depth in (1,2,3):
  ids={k for k,v in issued.items() if v['depth']==depth};summary.append(dict(depth=depth,issued=len(ids),explicit_rejected=len(ids&rejected),accepted=len(ids&accepted),unaccepted_nonrejected=len(ids-accepted-rejected)))
 def work(rs):return sum(struct.unpack('<8i4d',bytes.fromhex(x['reply_hex']))[8] for x in rs)
 bad=[x for x in decode if x['row']['id'] in rejected];unused=[x for x in decode if x['row']['id'] not in accepted];stage=[]
 for rank in range(len(p['stages'])):
  rr=[x for x in rows if x['event']=='completed' and x.get('stage')==rank and x['op']==24 and x['row']['fixture']>1];native=[json.loads(x) for x in (root/f'stage{rank}/native/timings.jsonl').read_text().splitlines()];native=[x for x in native if x['fixture']>1];assert len(rr)==len(native)
  stage.append(dict(stage=rank,decode_rows=len(rr),native_half_completion_ms=sum(x['half_completion_ms'] for x in native),reply_busy_ms=work(rr),native_speculative_flag_count=sum(x['speculative'] for x in native)))
 provider=[x for x in rows if x['event']=='completed' and x.get('owner')=='provider' and x['row']['fixture']>1];captures=[x for x in rows if x['event']=='parent-captured' and x['row']['fixture']>1];heads=collections.Counter(x['provider']['available_depth'] for x in provider)
 timings=[json.loads(x) for x in (root/'tokens.jsonl').read_text().splitlines()];span=timings[-1]['committed_monotonic_s']-timings[0]['committed_monotonic_s'];saved=work(bad)/1000
 return dict(schema='ownrt.actual-speculation-work-audit.v1',source=str(root),outputs=512,decode_intervals=511,span_seconds=span,stages=stage,issued_depths=summary,provider_completed=len(provider),capture_ack_count=len(captures),native_head_availability=dict(heads),explicit_rejected_decode_rows=len(bad),explicit_rejected_reply_busy_ms=work(bad),all_unaccepted_decode_rows=len(unused),all_unaccepted_reply_busy_ms=work(unused),optimistic_remove_all_rejected_work_seconds=saved,optimistic_rate_if_all_rejected_busy_were_serial_critical=511/(span-saved),scope='Native busy work sums are not disjoint critical-path durations; bound assumes every rejected stage0 ROW disappears without losing useful overlap. A depth1 policy may lose useful deeper hits. Native speculative=false on ring ROWs does not identify accepted guesses.',source_hashes={f:hashlib.sha256((root/f).read_bytes()).hexdigest() for f in ('driver-result.json','commands.jsonl','tokens.jsonl')})
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('output',type=Path);a.add_argument('--out',type=Path,required=True);v=a.parse_args();r=audit(v.output)
 with v.out.open('x') as f:json.dump(r,f,indent=2);f.write('\n')
 print(json.dumps(r,indent=2))
