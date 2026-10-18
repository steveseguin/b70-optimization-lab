"""Bind completed selected-view CPU checks; missing evidence always refuses."""
import json
from pathlib import Path
from common import HERE,ROOT,read,require,save,sha,verify_map

GATES=('build','full-shape','reset-bytes','protocol','exec-limits','policy','chain-startup','smoke-policy')

def checked_configs():
 from bracket import load_config
 bracket=load_config(HERE/'configs/bracket.json')
 smoke=load_config(HERE/'configs/smoke.json')
 require(bracket['kind']=='bracket' and smoke['kind']=='smoke','registered bracket and smoke required')
 require(smoke['views']==bracket['views'][:3],'smoke must exercise the exact first three bracket views')
 for config in (bracket,smoke):
  for view in config['views']:
   path=Path(view['selection']).resolve()
   require(path in {HERE/'lineage/selection.json',HERE/'lineage/candidate.json'} and view['selection_sha256']==sha(path),'unregistered view selection')
 return bracket,smoke

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
 require(rows['chain-startup']['total_windows']==22 and sha(ROOT/rows['chain-startup']['archive'])==rows['chain-startup']['archive_sha256'],'all selected chain startup windows required')
 require(len(startup)==4 and {(r['selection'],r['rank']) for r in startup}=={(v,r) for v in ('selection','candidate') for r in (0,1)} and all(r['result'].get('passed') is True for r in startup),'both selected views and ranks require real-parser startup')
 full=rows['full-shape']['runs']
 require(len(full)==4 and all(r['result'].get('passed') is True for r in full),'both ranks, fresh and switched startup required')
 require(all(r['result'].get('views')==5 and r['result'].get('fresh_start_capture_identity') is True for r in full),'five view capture/reset checks required')
 reset=rows['reset-bytes']['runs']
 require(len(reset)==4 and {(r['rank'],r['repeat']) for r in reset}=={(r,n) for r in (0,1) for n in (0,1)},'two reset processes per rank required')
 protocol=rows['protocol']['runs']
 require(len(protocol)==1 and len(protocol[0]['brackets'])==2,'two fresh protocol brackets required')
 for bracket in protocol[0]['brackets']:
  require(len(bracket['rows'])==5 and all(r['cached_tokens']==0 for r in bracket['rows']),'every bracket view cold and exact')
  require(all(r['forced_miss_stats']['misses']==63 and r['forced_miss_tokens']==r['tokens'] for r in bracket['rows']),'every bracket view must preserve all tokens through forced native misses')
 for row in rows.values():
  if row.get('sources'):verify_map(ROOT,row['sources'])
 receipt_artifacts(rows)
 return rows

def seal(operator_evidence):
 rows=validate_receipts()
 checked_configs()
 operator_evidence=Path(operator_evidence).resolve()
 require(operator_evidence.is_relative_to(HERE.parent),'operator byte evidence outside packet121')
 op=read(operator_evidence)
 require(op.get('schema')=='packet121.cpu-byte-identity.v1' and op.get('passed') is True and op.get('device_executed') is False,'operator byte gate incomplete')
 verify_map(ROOT,op['sources'])
 operator_paths={operator_evidence}
 runs=op['runs']
 require(len(runs)==8 and {(r['compiler'],r['repeat'],r['view']) for r in runs}=={(c,n,v) for c in ('GNU','Intel') for n in (1,2) for v in ('control','candidate')},'both compilers, repeats and views required')
 require(len({r['canonical_sha256'] for r in runs})==1,'cross compiler/view canonical bytes differ')
 for run in runs:
  require(run['passed'] and not run['device_executed'] and run['cases']>=300 and run['position_classes']==43 and run['transport_tail_cases']==54,'complete miss, position, fallback and tail gates required')
  if run['view']=='candidate':require(run['negative_controls']>0 and run['reused_tables']==run['restore_submissions']>0,'reverse restore was not exercised')
  import gzip,hashlib
  path=ROOT/run['raw_evidence'];require(sha(path)==run['raw_evidence_sha256'],'byte evidence changed')
  require(hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest()==run['canonical_sha256'],'canonical evidence bytes changed')
  operator_paths.add(path)
  path=ROOT/run['log_path'];require(sha(path)==run['log_sha256'],'byte log changed');operator_paths.add(path)
 for compiler in op['compilers']:
  for name,digest in (('binary','binary_sha256'),('compile_log','compile_log_sha256')):
   path=ROOT/compiler[name];require(sha(path)==compiler[digest],'operator compiler artifact changed');operator_paths.add(path)
 paths=set(HERE.glob('*.py'))|set(HERE.glob('native/*'))|set(HERE.glob('native-src/*'))|set(HERE.glob('lineage/*.json'))|set(HERE.glob('configs/*.json'))
 paths.discard(HERE/'lineage/screen-seal.json')
 paths.update(HERE/'evidence'/(n+'.json') for n in GATES)
 paths.update((HERE/'source-copy-provenance.json',operator_evidence,HERE/'smoke_gate.py'))
 paths.update((HERE/'configs/bracket.json',HERE/'configs/smoke.json',ROOT/rows['chain-startup']['archive']))
 paths.update(HERE.parent.glob('*.py'))
 paths.add(HERE.parent/'source-copy-provenance.json')
 paths.update(operator_paths)
 paths.update(receipt_artifacts(rows))
 sources={str(p.relative_to(ROOT)):sha(p) for p in sorted(paths) if p.is_file()}
 sources.update(rows['build']['sources'])
 sources.update(read(HERE/'source-copy-provenance.json')['sources'])
 sources.update(external_runtime_sources())
 binary=HERE/'build/device/own-rt-iq3'
 require(rows['build']['artifacts']['build/device/own-rt-iq3']==sha(binary),'device binary changed')
 row=dict(schema='packet121.v5.cpu-seal.v1',passed=True,device_executed=False,sources=sources,binary_sha256=sha(binary),restore_table=read(HERE/'lineage/candidate.json')['choices']['restore_table'],operator_evidence=str(operator_evidence.relative_to(ROOT)),operator_evidence_sha256=sha(operator_evidence),startup_views=['production',read(HERE/'lineage/candidate.json')['choices']['restore_table']])
 save(HERE/'lineage/screen-seal.json',row)
 # The screen receipt refers to a wrapper seal independently of native seal.
 (HERE/'placement-validation').mkdir(exist_ok=True)
 save(HERE/'placement-validation/wrapper-seal.json',row)
 return verify()

def verify():
 checked_configs()
 path=HERE/'lineage/screen-seal.json';row=read(path)
 require(row.get('passed') is True and row.get('device_executed') is False,'CPU seal missing')
 verify_map(ROOT,row['sources'])
 require(sha(HERE/'build/device/own-rt-iq3')==row['binary_sha256'],'binary changed')
 require(read(HERE/'lineage/candidate.json')['choices']['restore_table']==row['restore_table'],'selected startup receipt changed')
 require(read(HERE/'placement-validation/wrapper-seal.json')==row,'wrapper seal changed')
 return row

if __name__=='__main__':
 import argparse
 from build_engine import limits
 limits()
 ap=argparse.ArgumentParser();ap.add_argument('--operator-evidence',type=Path)
 a=ap.parse_args();seal(a.operator_evidence) if a.operator_evidence else verify()
