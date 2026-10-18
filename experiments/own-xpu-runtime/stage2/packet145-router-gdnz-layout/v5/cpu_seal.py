"""Local closed composition seal. CPU readiness is separate from device evidence."""
import argparse,json
from pathlib import Path
from p145_v5_build_engine import P,LOCAL,ROOT,sha,save
GATES=('build','full-shape','bytes','exec-limits','safety','submission-rehearsal','admission')

def check_sources(rows):
 for name,digest in rows.items():
  path=ROOT/name
  assert path.is_file() and sha(path)==digest,'source changed: '+name

def seal():
 rows={name:json.loads((P/'evidence'/(name+'.json')).read_text()) for name in GATES}
 for name,row in rows.items():
  assert row.get('passed') is True and row.get('device_executed') is False,name
  if 'sources' in row:check_sources(row['sources'])
 shape=rows['full-shape'];assert len(shape['runs'])==8 and len(shape['startup_runs'])==8
 check_sources(rows['build']['artifacts']);check_sources(rows['bytes']['binaries']);check_sources(rows['submission-rehearsal']['artifacts'])
 assert sha(P/'build/full-shape/fixture')==shape['binary_sha256']
 for run in shape['runs']+shape['startup_runs']:assert sha(ROOT/run['artifact']['path'])==run['artifact']['sha256']
 for run in rows['bytes']['runs']:assert sha(ROOT/run['artifact'])==run['artifact_sha256']
 assert all(r['result']['passed'] and r['result']['views']==5 for r in shape['runs'])
 assert len(rows['bytes']['runs'])==4 and len({r['sha256'] for r in rows['bytes']['runs']})==1
 assert rows['submission-rehearsal']['rehearsal_only'] and rows['submission-rehearsal']['corrupt_receipt_refused']
 paths=set((LOCAL/'proposals').glob('*.txt'))|set(P.glob('*.py'))|set(P.glob('native/*'))|set(P.glob('native-src/*'))|set(P.glob('configs/*.json'))
 paths.update(f for f in (P/'lineage').rglob('*.json') if f.name!='screen-seal.json')
 paths.update(LOCAL/n for n in ('class_layout.hpp','layout_bytes.cpp','shared_oracle.py','oracle-binding.json','prepare_submission.py','packet56_submission.py','bundle_selection.py','selection-template.json','preregistration.json'))
 paths.update(f for f in (LOCAL/'native-base').rglob('*') if f.is_file())
 for root in (LOCAL/'lineage-inputs/vendor/repo',LOCAL/'lineage-inputs/submission-tools',LOCAL/'lineage-inputs/report-fixture'):
  paths.update(f for f in root.rglob('*') if f.is_file() and 'build' not in f.relative_to(root).parts)
 paths.update(f for f in LOCAL.iterdir() if f.is_file() and f.suffix in ('.py','.hpp','.cpp','.bf16','.tsv'))
 paths.update(LOCAL/'lineage-inputs'/n for n in ('legacy-fixtures.json','legacy-fixtures.tar.gz','current-aliases.json','packet136-chain-evidence.json.gz','vendor-origin.json'))
 paths.update(P/'evidence'/(name+'.json') for name in GATES)
 paths.update(ROOT/name for name in rows['submission-rehearsal']['artifacts'])
 for mode in ('device','gnu-host'):paths.add(P/'build'/mode/'own-rt-iq3')
 paths.add(P/'build/full-shape/fixture')
 for run in shape['runs']+shape['startup_runs']:paths.add(ROOT/run['artifact']['path'])
 for run in rows['bytes']['runs']:paths.add(ROOT/run['artifact'])
 for name in rows['bytes']['binaries']:paths.add(ROOT/name)
 sources={str(f.relative_to(ROOT)):sha(f) for f in sorted(paths) if f.is_file()}
 sources.update(rows['build']['sources'])
 # Oracle identity is checked through its binding, never entered as copied sources.
 import subprocess,sys
 subprocess.run([sys.executable,'-B',str(LOCAL/'shared_oracle.py'),'--require-complete'],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,check=True,timeout=180)
 row=dict(schema='packet145.cpu-composition.v1',passed=True,device_executed=False,device_quality_pending=True,arithmetic='iq3-p49-split32-v1',sources=sources,variants=['router-order600','gdnz-order600'],gates=list(GATES),binary_sha256=sha(P/'build/device/own-rt-iq3'))
 save(P/'cpu-seal.json',row)
 for v in row['variants']:save(P/'lineage'/v/'screen-seal.json',row)
 save(P/'placement-validation/wrapper-seal.json',row)
 return verify()
def verify():
 row=json.loads((P/'cpu-seal.json').read_text());assert row['passed'] and row['device_executed'] is False
 check_sources(row['sources'])
 for v in row['variants']:assert json.loads((P/'lineage'/v/'screen-seal.json').read_text())==row
 assert json.loads((P/'placement-validation/wrapper-seal.json').read_text())==row
 return row
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--seal',action='store_true');a=ap.parse_args();seal() if a.seal else verify();print('CPU composition seal PASS')
