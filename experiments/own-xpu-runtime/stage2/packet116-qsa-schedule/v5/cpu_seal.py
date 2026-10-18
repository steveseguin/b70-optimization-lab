"""Bind completed selected-view CPU checks; missing evidence always refuses."""
import json
from pathlib import Path
from common import HERE,ROOT,read,require,save,sha,verify_map

GATES=('build','full-shape','reset-bytes','protocol','startup','import-limits','launch-limits')

def validate_receipts():
 rows={}
 for name in GATES:
  path=HERE/'evidence'/(name+'.json');row=read(path)
  require(row.get('passed') is True and row.get('device_executed') is False,'incomplete CPU gate '+name)
  rows[name]=row
 full=rows['full-shape']['runs']
 require(len(full)==4 and all(r['result'].get('passed') is True for r in full),'both ranks, fresh and switched startup required')
 require(all(r['result'].get('views')==5 and r['result'].get('fresh_start_capture_identity') is True for r in full),'five view capture/reset checks required')
 reset=rows['reset-bytes']['runs']
 require(len(reset)==4 and {(r['rank'],r['repeat']) for r in reset}=={(r,n) for r in (0,1) for n in (0,1)},'two reset processes per rank required')
 protocol=rows['protocol']['runs']
 require(len(protocol)==1 and len(protocol[0]['brackets'])==2,'two fresh protocol brackets required')
 for bracket in protocol[0]['brackets']:
  require(len(bracket['rows'])==5 and all(r['cached_tokens']==0 for r in bracket['rows']),'every bracket view cold and exact')
 startup=rows['startup']['runs']
 require(len(startup)==22 and {r['view'] for r in startup}=={'selection','candidate'},'only both selected views require eleven startup windows')
 require(rows['import-limits'].get('resource_limits_unchanged') is True,'device import changes resource limits')
 require(len(rows['launch-limits']['cases'])==2 and rows['launch-limits']['cases'][1].get('negative_control') is True,'actual exec limit interception and negative cap required')
 for row in rows.values():
  if row.get('sources'):verify_map(ROOT,row['sources'])
  if row.get('binaries'):verify_map(ROOT,row['binaries'])
 for name,path in (('full-shape','build/full-shape/fixture'),('reset-bytes','build/reset-bytes/fixture')):
  require(sha(HERE/path)==rows[name]['binary_sha256'],'CPU fixture changed: '+name)
 verify_map(HERE,rows['build']['artifacts'])
 return rows

def seal(operator_evidence):
 rows=validate_receipts()
 from bracket import load_config
 config=load_config(HERE/'configs/bracket.json')
 require(config['kind']=='bracket','five-view bracket required')
 operator_evidence=Path(operator_evidence).resolve()
 require(operator_evidence.is_relative_to(HERE.parent),'operator byte evidence outside packet116')
 op=read(operator_evidence)
 require(op.get('passed') is True and op.get('device_executed') is False,'operator byte gate incomplete')
 require(op.get('arithmetic')=='iq3-p49-split32-v1' and op.get('within_compiler_production_candidate_bytes') is True,'exact QSA arithmetic byte gate required')
 verify_map(HERE.parent,op['source_sha256'])
 require({c['compiler'] for c in op['compilers']}=={'GNU','Intel'} and all(len(c['runs'])==2 for c in op['compilers']),'both compilers require two fresh exact processes')
 paths=set(HERE.glob('*.py'))|set(HERE.glob('native/*'))|set(HERE.glob('native-src/*'))|set(HERE.glob('lineage/*.json'))|set(HERE.glob('configs/*.json'))
 paths.discard(HERE/'lineage/screen-seal.json')
 paths.update(HERE/'evidence'/(n+'.json') for n in GATES)
 paths.update((HERE/'source-copy-provenance.json',HERE/'check-copy-provenance.json',operator_evidence,HERE.parent/'micro/qualification.py',HERE.parent/'micro/run_micro.py'))
 sources={str(p.relative_to(ROOT)):sha(p) for p in sorted(paths) if p.is_file()}
 sources.update(rows['build']['sources'])
 sources.update({str((HERE/name).relative_to(ROOT)):digest for name,digest in rows['build']['artifacts'].items()})
 sources.update({str((HERE.parent/name).relative_to(ROOT)):digest for name,digest in op['source_sha256'].items()})
 sources.update(read(HERE/'source-copy-provenance.json')['sources'])
 binary=HERE/'build/device/own-rt-iq3'
 require(rows['build']['artifacts']['build/device/own-rt-iq3']==sha(binary),'device binary changed')
 row=dict(schema='packet116.v5.cpu-seal.v1',passed=True,device_executed=False,sources=sources,binary_sha256=sha(binary),qsa_schedule=read(HERE/'lineage/candidate.json')['choices']['qsa_schedule'],operator_evidence=str(operator_evidence.relative_to(ROOT)),operator_evidence_sha256=sha(operator_evidence),startup_views=['production',read(HERE/'lineage/candidate.json')['choices']['qsa_schedule']])
 save(HERE/'lineage/screen-seal.json',row)
 # The screen receipt refers to a wrapper seal independently of native seal.
 (HERE/'placement-validation').mkdir(exist_ok=True)
 save(HERE/'placement-validation/wrapper-seal.json',row)
 return verify()

def verify():
 path=HERE/'lineage/screen-seal.json';row=read(path)
 require(row.get('passed') is True and row.get('device_executed') is False,'CPU seal missing')
 verify_map(ROOT,row['sources'])
 require(sha(HERE/'build/device/own-rt-iq3')==row['binary_sha256'],'binary changed')
 require(read(HERE/'lineage/candidate.json')['choices']['qsa_schedule']==row['qsa_schedule'],'selected startup receipt changed')
 require(read(HERE/'placement-validation/wrapper-seal.json')==row,'wrapper seal changed')
 return row

if __name__=='__main__':
 import argparse
 ap=argparse.ArgumentParser();ap.add_argument('--operator-evidence',type=Path)
 a=ap.parse_args();seal(a.operator_evidence) if a.operator_evidence else verify()
