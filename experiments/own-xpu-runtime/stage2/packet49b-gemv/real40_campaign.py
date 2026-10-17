#!/usr/bin/env python3
"""Five fresh inherited real-model gates, serial, with immutable recorder logs."""
import argparse,json,os,sys,time
from pathlib import Path
from seal40 import P,record_phase,save,sha,execution_sources
from storage import archive_files

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--compiler',choices=('gnu-host','icpx-host'),required=True)
 a=ap.parse_args()
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert os.environ.get('OMP_NUM_THREADS')=='2'
 compiler=a.compiler;binary=P/'build'/compiler/'own-rt-iq3'
 initial_binary=sha(binary);rows=[];started=time.time_ns()
 sources=execution_sources([sys.executable,'-B',str(P/'gates.py')],P)
 for mode in ('none','ngram','hit','miss','mtp'):
  assert sha(binary)==initial_binary,'binary changed; no next mode launched'
  assert execution_sources([sys.executable,'-B',str(P/'gates.py')],P)==sources,'source changed; no next mode launched'
  if rows:assert rows[-1]['passed'],'previous mode failed; no retry or next launch'
  receipt=f'real-{mode}.json' if compiler=='gnu-host' else f'real-{compiler}-{mode}.json'
  previous=[P/receipt]
  if compiler=='gnu-host':previous.extend(P/'evidence'/f'real-{mode}-rank{rank}-arguments.jsonl.gz' for rank in (0,1))
  previous=[f for f in previous if f.is_file()]
  archive=archive_files(previous,P/'evidence'/f'prior-real-{compiler}-{mode}-{time.time_ns()}.jsonl.gz') if previous else None
  print(f'BEGIN {compiler} {mode}',flush=True)
  ledger=record_phase('real-'+compiler+'-'+mode,[sys.executable,'-B',str(P/'gates.py'),'real',mode,'--compiler',compiler],[receipt])
  result=json.loads((P/receipt).read_text())
  assert result['passed'] and result['token_matches']==8 and result['layer_matches']==384
  assert result['binary_sha256']==initial_binary
  rows.append(dict(mode=mode,passed=True,receipt=receipt,receipt_sha256=sha(P/receipt),seconds=result['seconds'],token_matches=8,layer_matches=384,prior_archive=archive,execution_phase=ledger['phase'],execution_start_unix_ns=ledger['start_unix_ns']))
  print(f'END {compiler} {mode}: 8 tokens, 384 fixtures, {result["seconds"]:.3f}s',flush=True)
 result=dict(passed=True,compiler=compiler,device_executed=False,binary_sha256=initial_binary,source_sha256=sources,rows=rows,modes=len(rows),start_unix_ns=started,end_unix_ns=time.time_ns(),no_speed_claim=True)
 save(P/f'real-campaign-{compiler}.json',result)
 print(json.dumps(dict(passed=True,compiler=compiler,modes=len(rows))),flush=True)
if __name__=='__main__':main()
