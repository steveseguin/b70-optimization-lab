#!/usr/bin/env python3
"""Verify five recorded real gates; aggregate evidence without launching models.

A wrapper-only source change may invalidate an outer campaign ledger while its
five narrow gates.py execution ledgers remain current. This producer verifies
the narrow evidence independently and never repairs or overwrites a ledger.
"""
import argparse,json,sys,time
from pathlib import Path
from seal40 import P,execution_sources,sha,save
from storage import archive_files
MODES=('none','ngram','hit','miss','mtp')

def require(ok,message):
 if not ok:raise ValueError(message)

def validate(compiler,ledger_paths=None,packet=P):
 packet=Path(packet).resolve()
 current=execution_sources([sys.executable,'-B',str(packet/'gates.py')],packet)
 binary=sha(packet/'build'/compiler/'own-rt-iq3')
 explicit=list(ledger_paths or [])
 require(not explicit or len(explicit)==5,'exactly five explicit ledger paths required')
 rows=[];previous_end=0;roots=set();selected=set()
 for index,mode in enumerate(MODES):
  receipt=f'real-{mode}.json' if compiler=='gnu-host' else f'real-{compiler}-{mode}.json'
  receipt_path=packet/receipt;digest=sha(receipt_path);result=json.loads(receipt_path.read_text())
  require(result.get('passed') is True and result.get('device_executed') is False,mode+': CPU result failed')
  require(result.get('mode')==mode and result.get('binary_sha256')==binary,mode+': result identity changed')
  require(result.get('token_matches')==8 and result.get('layer_matches')==384 and result.get('layer_total')==384,mode+': incomplete exactness coverage')
  require(result.get('fixture_sha256') and result.get('controller_signature'),mode+': missing underlying exactness evidence')
  phase='real-'+compiler+'-'+mode
  candidates=explicit[index:index+1] if explicit else sorted((packet/'evidence').glob('qualification-'+phase+'-*.json'))
  valid=[]
  for candidate in candidates:
   candidate=Path(candidate).resolve()
   require(candidate.is_relative_to(packet/'evidence'),mode+': ledger outside packet evidence')
   ledger=json.loads(candidate.read_text())
   if ledger.get('phase')!=phase or ledger.get('receipt_sha256')!={receipt:digest}:continue
   if ledger.get('passed') is not True or ledger.get('returncode')!=0 or ledger.get('problems') or ledger.get('device_executed') is not False:continue
   if ledger.get('source_sha256')!=current or ledger.get('binary_sha256',{}).get(compiler+'/own-rt-iq3')!=binary:continue
   command=ledger.get('command',[])
   if len(command)!=13 or command[:6]!=['nice','-n','19','ionice','-c','3'] or command[7]!='-B':continue
   if Path(command[8]).resolve()!=packet/'gates.py' or command[9:]!=['real',mode,'--compiler',compiler]:continue
   log=(packet/ledger['log']).resolve()
   require(log.is_relative_to(packet/'evidence') and sha(log)==ledger['log_sha256'],mode+': execution log changed')
   valid.append((candidate,ledger))
  require(len(valid)==1,mode+': need exactly one current successful receipt-bound ledger; found '+str(len(valid)))
  path,ledger=valid[0];start=ledger['start_unix_ns'];end=ledger['end_unix_ns']
  require(isinstance(start,int) and isinstance(end,int) and previous_end<start<end,mode+': launches not distinct chronological serial executions')
  root=Path(result['root']).resolve()
  require(root.is_relative_to(packet/'build') and str(root) not in roots,mode+': owner output reused')
  require(path not in selected,mode+': ledger reused')
  roots.add(str(root));selected.add(path);previous_end=end
  rows.append(dict(mode=mode,passed=True,receipt=receipt,receipt_sha256=digest,seconds=result['seconds'],token_matches=8,layer_matches=384,
                   execution_phase=phase,execution_start_unix_ns=start,execution_end_unix_ns=end,
                   execution_ledger=str(path.relative_to(packet)),execution_ledger_sha256=sha(path),output_root=str(root)))
 require(current==execution_sources([sys.executable,'-B',str(packet/'gates.py')],packet),'gate sources changed during aggregation')
 require(binary==sha(packet/'build'/compiler/'own-rt-iq3'),'binary changed during aggregation')
 for row in rows:
  require(sha(packet/row['receipt'])==row['receipt_sha256'] and sha(packet/row['execution_ledger'])==row['execution_ledger_sha256'],'evidence changed during aggregation')
 return dict(passed=True,compiler=compiler,device_executed=False,binary_sha256=binary,source_sha256=current,rows=rows,modes=5,
             start_unix_ns=rows[0]['execution_start_unix_ns'],end_unix_ns=rows[-1]['execution_end_unix_ns'],no_speed_claim=True,
             aggregation_only=True,models_launched=0,aggregated_unix_ns=time.time_ns(),producer_sha256=sha(packet/'real40_summary.py'),
             scope='Five current, exact receipt-bound narrow execution ledgers; outer failed campaign evidence is preserved unchanged.')

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--compiler',choices=('gnu-host','icpx-host'),required=True)
 ap.add_argument('--ledger',action='append',type=Path,help='Exactly five ledger paths in none,ngram,hit,miss,mtp order; default discovers exact current bindings')
 a=ap.parse_args();result=validate(a.compiler,a.ledger);destination=P/f'real-campaign-{a.compiler}.json'
 if destination.exists():
  result['prior_summary_archive']=archive_files([destination],P/'evidence'/f'prior-real-summary-{a.compiler}-{time.time_ns()}.jsonl.gz')
 save(destination,result)
 print(json.dumps(dict(passed=True,compiler=a.compiler,modes=5,models_launched=0)))
if __name__=='__main__':main()
