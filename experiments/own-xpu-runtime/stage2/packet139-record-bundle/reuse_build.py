"""Verify byte-identical packet137 v5 engines and frozen CPU evidence."""
import json,subprocess,sys
from pathlib import Path
from build_engine import P,ROOT,B,sha,save,limits
OLD=P.with_name('packet137-token-input')
def verify_native():
 row=json.loads((P/'native-reuse.json').read_text())
 from chain_seal import check_map
 check_map(ROOT,row['sources'])
 for mode in ('gnu-host','device'):
  assert sha(B/mode/'own-rt-iq3')==row['artifacts']['build/'+mode+'/own-rt-iq3']==sha(OLD/'v5/build'/mode/'own-rt-iq3')
 for n,h in json.loads((P/'copy139.json').read_text())['native_files'].items():assert sha(P/n)==h,n
 return row
if __name__=='__main__':verify_native();print('packet137 native identity verified')
