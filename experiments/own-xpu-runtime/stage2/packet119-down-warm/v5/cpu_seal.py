"""Bind completed selected-view CPU checks; missing evidence always refuses."""
import json
from pathlib import Path
from common import HERE,ROOT,read,require,save,sha,verify_map

GATES=('build','full-shape','reset-bytes','protocol','exec-limits','policy')

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
 protocol=rows['protocol']['runs']
 require(len(protocol)==1 and len(protocol[0]['brackets'])==2,'two fresh protocol brackets required')
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
 require(operator_evidence.is_relative_to(HERE.parent),'operator byte evidence outside packet119')
 op=read(operator_evidence)
 require(op.get('schema')=='packet119.cpu-byte-identity.v1' and op.get('passed') is True and op.get('device_executed') is False,'operator byte gate incomplete')
 verify_map(ROOT,op['sources'])
 operator_paths={operator_evidence}
 for name,entry in op['generated_sources'].items():
  require(sha(ROOT/name)==entry['sha256'] and sha(ROOT/entry['source'])==entry['source_sha256'],'operator generated source changed')
  operator_paths.update((ROOT/name,ROOT/entry['source']))
 candidate=read(HERE/'lineage/candidate.json')['choices']['down_warm']
 for view in (candidate,):
  runs=op['views'][view]['runs']
  require(len(runs)==4 and {(r['compiler'],r['repeat']) for r in runs}=={(c,n) for c in ('GNU','Intel') for n in (1,2)},'GNU/Intel two fresh byte runs required')
  for compiler in ('GNU','Intel'):
   require(len({r['candidate_sha256'] for r in runs if r['compiler']==compiler})==1,'fresh operator repeat differs within compiler')
  for run in runs:
   require(run.get('passed') is True and run.get('device_executed') is False and run['expected_sha256']==run['candidate_sha256'],'operator bytes differ')
   require(run['cases']>=10 and run['output_status_checks']>=50 and run['raw_fp32_chain_checks']>=4480 and run['weight_bytes_unchanged']>=11059200 and run['cache_mapping_checks']>=7,'complete byte, raw FP32 chain, immutable weight and cache-address coverage required')
   for name,digest in (('raw_evidence','raw_evidence_sha256'),('cases_path','cases_sha256'),('log_path','log_sha256')):
    path=ROOT/run[name];require(sha(path)==run[digest],'operator raw receipt changed');operator_paths.add(path)
   import gzip,hashlib
   require(hashlib.sha256(gzip.decompress((ROOT/run['raw_evidence']).read_bytes())).hexdigest()==run['expected_sha256'],'operator retained bytes differ')
 for compiler in op['compilers']:
  for name,digest in (('binary','binary_sha256'),('compile_log','compile_log_sha256')):
   path=ROOT/compiler[name];require(sha(path)==compiler[digest],'operator compiler artifact changed');operator_paths.add(path)
 paths=set(HERE.glob('*.py'))|set(HERE.glob('native/*'))|set(HERE.glob('native-src/*'))|set(HERE.glob('lineage/*.json'))|set(HERE.glob('configs/*.json'))
 paths.discard(HERE/'lineage/screen-seal.json')
 paths.update(HERE/'evidence'/(n+'.json') for n in GATES)
 paths.update((HERE/'source-copy-provenance.json',operator_evidence,HERE.parent/'micro_gate.py'))
 paths.update(operator_paths)
 paths.update(receipt_artifacts(rows))
 sources={str(p.relative_to(ROOT)):sha(p) for p in sorted(paths) if p.is_file()}
 sources.update(rows['build']['sources'])
 sources.update(read(HERE/'source-copy-provenance.json')['sources'])
 sources.update(external_runtime_sources())
 binary=HERE/'build/device/own-rt-iq3'
 require(rows['build']['artifacts']['build/device/own-rt-iq3']==sha(binary),'device binary changed')
 row=dict(schema='packet119.v5.cpu-seal.v1',passed=True,device_executed=False,sources=sources,binary_sha256=sha(binary),down_warm=read(HERE/'lineage/candidate.json')['choices']['down_warm'],operator_evidence=str(operator_evidence.relative_to(ROOT)),operator_evidence_sha256=sha(operator_evidence),startup_views=['production',read(HERE/'lineage/candidate.json')['choices']['down_warm']])
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
 require(read(HERE/'lineage/candidate.json')['choices']['down_warm']==row['down_warm'],'selected startup receipt changed')
 require(read(HERE/'placement-validation/wrapper-seal.json')==row,'wrapper seal changed')
 return row

if __name__=='__main__':
 import argparse
 ap=argparse.ArgumentParser();ap.add_argument('--operator-evidence',type=Path)
 a=ap.parse_args();seal(a.operator_evidence) if a.operator_evidence else verify()
