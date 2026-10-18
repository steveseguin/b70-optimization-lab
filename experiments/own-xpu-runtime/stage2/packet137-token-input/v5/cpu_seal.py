"""Bind completed selected-view CPU checks; missing evidence always refuses."""
import json
from pathlib import Path
from common import HERE,ROOT,read,require,save,sha,verify_map

GATES=('build','full-shape','reset-bytes','protocol','exec-limits','policy','safety')

def external_runtime_sources():
 """Retain the established v4 support closure and exact dynamic-import inputs."""
 stage=HERE.parents[1]
 wrapper=stage/'screen/v4-lanes/wrapper-seal.json'
 row=read(wrapper)
 require(row.get('passed') is True and row.get('device_executed') is False,'shared wrapper CPU seal incomplete')
 verify_map(ROOT,row['sources'])
 direct=[stage/'packet58-onecard'/name for name in ('memory_plan.py','window.py','suite_driver.py')]
 direct += [stage/'packet56-draft-prefix'/name for name in ('merge_dispatch.py','memory_gate.py','pipeline.py','suite.py','storage.py')]
 direct += [stage/'packet49-integrate/oracle/suite_check.py']
 for path in direct:
  require(row['sources'].get(str(path.relative_to(ROOT)))==sha(path),'runtime dynamic import outside established wrapper closure: '+str(path))
 return {**row['sources'],str(wrapper.relative_to(ROOT)):sha(wrapper)}

def receipt_artifacts(rows):
 """Check every retained native binary/archive, independently of source maps."""
 paths=set()
 def bound(path,digest):
  path=Path(path)
  require(path.is_file() and sha(path)==digest,'CPU receipt artifact changed: '+str(path))
  paths.add(path)
 for name,digest in rows['build']['artifacts'].items():bound(HERE/name,digest)
 bound(HERE/'build/full-shape/fixture',rows['full-shape']['binary_sha256'])
 bound(HERE/'build/reset-bytes/fixture',rows['reset-bytes']['binary_sha256'])
 for run in rows['full-shape']['runs']+rows['full-shape']['startup_runs']:
  artifact=run['artifact']
  require(artifact.get('all_original_bytes_verified') is True and artifact['members']>0,'shape archive lacks original-byte verification')
  bound(ROOT/artifact['path'],artifact['sha256'])
 for row in [rows['protocol'],*rows['protocol']['runs']]:
  require(bool(row['binaries']),'protocol native binary bindings missing')
  for name,digest in row['binaries'].items():bound(ROOT/name,digest)
 return paths

def validate_receipts():
 rows={}
 for name in GATES:
  path=HERE/'evidence'/(name+'.json');row=read(path)
  require(row.get('passed') is True and row.get('device_executed') is False,'incomplete CPU gate '+name)
  rows[name]=row
 startup=rows['full-shape']['startup_runs']
 require(len(startup)==4 and {(r['selection'],r['rank']) for r in startup}=={(v,r) for v in ('selection','candidate') for r in (0,1)} and all(r['result'].get('passed') is True for r in startup),'both selected views and ranks require real-parser startup')
 full=rows['full-shape']['runs']
 require(len(full)==4 and all(r['result'].get('passed') is True for r in full),'both ranks, fresh and switched startup required')
 require(all(r['result'].get('views')==5 and r['result'].get('fresh_start_capture_identity') is True for r in full),'five view capture/reset checks required')
 reset=rows['reset-bytes']['runs']
 require(len(reset)==4 and {(r['rank'],r['repeat']) for r in reset}=={(r,n) for r in (0,1) for n in (0,1)},'two reset processes per rank required')
 for path,digest in rows['protocol']['cpu_runtime_libraries'].items():require(sha(path)==digest,'CPU runtime library changed')
 protocol=rows['protocol']['runs']
 require(len(protocol)==1 and len(protocol[0]['brackets'])==4,'four fresh GNU/Intel protocol brackets required')
 for bracket in protocol[0]['brackets']:
  require(len(bracket['rows'])==5 and all(r['cached_tokens']==0 for r in bracket['rows']),'every bracket view cold and exact')
 for row in rows.values():
  if row.get('sources'):verify_map(ROOT,row['sources'])
 receipt_artifacts(rows)
 return rows

def seal(operator_evidence):
 rows=validate_receipts()
 from bracket import load_config
 config=load_config(HERE/'configs/bracket.json')
 require(config['kind']=='bracket','five-view bracket required')
 operator_evidence=Path(operator_evidence).resolve()
 require(operator_evidence.is_relative_to(HERE.parent),'operator byte evidence outside packet137')
 op=read(operator_evidence)
 require(op.get('passed') is True and op.get('device_executed') is False,'head byte gate incomplete')
 verify_map(ROOT,op['sources'])
 operator_paths={operator_evidence,HERE.parent/'evidence/controller.json',HERE.parent/'evidence/reset-regression.json'}
 runs=op['runs']
 require(len(runs)==4 and {(r['compiler'],r['repeat']) for r in runs}=={(c,n) for c in ('GNU','Intel') for n in (1,2)},'GNU/Intel fresh head bytes required')
 import gzip,hashlib
 for run in runs:
  require(run['expected_sha256']==run['candidate_sha256'] and run['native']['passed'] is True and run['native']['full_vocab_tokens']==5 and run['native']['cases']==17,'incomplete full-vocabulary logit/argmax checks')
  path=ROOT/run['fixture'];require(sha(path)==run['fixture_sha256'] and hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest()==run['candidate_sha256'],'retained head bytes changed');operator_paths.add(path)
 controller=read(HERE.parent/'evidence/controller.json');verify_map(ROOT,controller['sources'])
 require(controller['passed'] is True and controller['device_executed'] is False and len(controller['runs'])==4,'controller gate incomplete')
 for run in controller['runs']:
  require(run['cases']==40 and run['hits_and_misses'] is True and run['negative_controls']==7,'forced arrival gate incomplete')
  path=ROOT/run['binary'];require(sha(path)==run['binary_sha256'],'controller binary changed');operator_paths.add(path)
 reset=read(HERE.parent/'evidence/reset-regression.json');verify_map(ROOT,reset['sources'])
 require(sha(HERE.parent/'reset_regression.py')==reset['gate_sha256'],'private reset gate source changed');operator_paths.add(HERE.parent/'reset_regression.py')
 require(reset['passed'] is True and reset['device_executed'] is False and len(reset['runs'])==4,'private suffix reset gate incomplete')
 for run in reset['runs']:require(run['result']['fixed_exact_cases']==21 and run['result']['negative_control_mismatches']==6,'private active reset regression missing')
 for row in (op,reset):
  for cmd in row['commands']:
   binary=Path(cmd[cmd.index('-o')+1]);compiler='GNU' if cmd[0]=='/usr/bin/g++' else 'Intel'
   require(all(sha(binary)==r['binary_sha256'] for r in row['runs'] if r['compiler']==compiler),'operator fixture binary changed');operator_paths.add(binary)
 sources_extra={**op['sources'],**controller['sources'],**reset['sources'],**rows['safety']['sources']}
 paths=set(HERE.glob('*.py'))|set(HERE.glob('native/*'))|set(HERE.glob('native-src/*'))|set(HERE.glob('lineage/*.json'))|set(HERE.glob('configs/*.json'))
 paths.discard(HERE/'lineage/screen-seal.json')
 paths.update(HERE/'evidence'/(n+'.json') for n in GATES)
 paths.update((HERE/'source-copy-provenance.json',operator_evidence,HERE.parent/'controller_gate.py'))
 paths.update(operator_paths)
 paths.update(receipt_artifacts(rows))
 sources={str(p.relative_to(ROOT)):sha(p) for p in sorted(paths) if p.is_file()}
 sources.update(sources_extra)
 sources.update(rows['build']['sources'])
 sources.update(read(HERE/'source-copy-provenance.json')['sources'])
 sources.update(external_runtime_sources())
 binary=HERE/'build/device/own-rt-iq3'
 require(rows['build']['artifacts']['build/device/own-rt-iq3']==sha(binary),'device binary changed')
 row=dict(schema='packet137.v5.cpu-seal.v1',passed=True,device_executed=False,sources=sources,binary_sha256=sha(binary),cpu_runtime_libraries=rows['protocol']['cpu_runtime_libraries'],suffix_schedule=read(HERE/'lineage/candidate.json')['choices']['suffix_schedule'],operator_evidence=str(operator_evidence.relative_to(ROOT)),operator_evidence_sha256=sha(operator_evidence),startup_views=['production',read(HERE/'lineage/candidate.json')['choices']['suffix_schedule']])
 save(HERE/'lineage/screen-seal.json',row)
 # The screen receipt refers to a wrapper seal independently of native seal.
 (HERE/'placement-validation').mkdir(exist_ok=True)
 save(HERE/'placement-validation/wrapper-seal.json',row)
 return verify()

def verify():
 path=HERE/'lineage/screen-seal.json';row=read(path)
 require(row.get('passed') is True and row.get('device_executed') is False,'CPU seal missing')
 verify_map(ROOT,row['sources'])
 for path,digest in row['cpu_runtime_libraries'].items():require(sha(path)==digest,'CPU runtime library changed')
 require(sha(HERE/'build/device/own-rt-iq3')==row['binary_sha256'],'binary changed')
 require(read(HERE/'lineage/candidate.json')['choices']['suffix_schedule']==row['suffix_schedule'],'selected startup receipt changed')
 require(read(HERE/'placement-validation/wrapper-seal.json')==row,'wrapper seal changed')
 return row

if __name__=='__main__':
 import argparse
 ap=argparse.ArgumentParser();ap.add_argument('--operator-evidence',type=Path)
 a=ap.parse_args();seal(a.operator_evidence) if a.operator_evidence else verify()
