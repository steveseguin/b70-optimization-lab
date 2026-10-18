#!/usr/bin/env python3
"""Current GNU native comparisons and rollback classification, once each."""
import json,sys,time
from seal40 import P,record_phase
from storage import archive_files

def main():
 names=['real-controller-gates.json','rollback-inventory.json']+[f'real-native-{m}.json' for m in ('none','ngram','hit','miss','mtp')]
 prior=[P/name for name in names if (P/name).is_file()]
 if prior:archive_files(prior,P/'evidence'/f'prior-native-real-{time.time_ns()}.jsonl.gz')
 receipts=['real-controller-gates.json']+[f'real-native-{m}.json' for m in ('none','ngram','hit','miss','mtp')]
 record_phase('real-native-comparisons',[sys.executable,'-B',str(P/'real_controller_gate.py')],receipts)
 result=json.loads((P/'real-controller-gates.json').read_text())
 assert result['passed'] and len(result['rows'])==5 and all(row['tokens']==8 and row['fixtures']==384 for row in result['rows'])
 record_phase('real-native-rollback',[sys.executable,'-B',str(P/'audit_rollback.py')],['rollback-inventory.json'])
 print('PASS: five native real comparisons and complete rollback inventory',flush=True)
if __name__=='__main__':main()
