"""Packet189 source/build admission (k3x rebuild of the entry TUs); device quality stays pending."""
import argparse,json,subprocess,sys
from pathlib import Path
from p189_v5_build_engine import P,LOCAL,ROOT,sha,save
GATES=('build','full-shape','k3-state','admission','analysis','controller','safety','exec-limits','loader')
MODES=('v3','v3k','k3x','k3trims')
def check_sources(rows):
 for name,digest in rows.items():
  assert (ROOT/name).is_file() and sha(ROOT/name)==digest,'source changed: '+name

def seal():
 rows={n:json.loads((P/'evidence'/(n+'.json')).read_text()) for n in GATES}
 for name,row in rows.items():
  assert row['passed'] and row['device_executed'] is False,name
  if 'sources' in row:check_sources(row['sources'])
 check_sources(rows['build']['artifacts'])
 paths=set(P.glob('*.py'))|set(P.glob('native/*'))|set(P.glob('native-src/*'))|set(P.glob('configs/*.json'))|set((LOCAL/'proposals').glob('*.txt'))
 paths.update(P/'lineage'/mode/n for mode in MODES for n in ('selection.json','dispatch-speed6.json','memory-plan.json'))
 paths.update(f for f in (LOCAL/'analysis').rglob('*') if f.is_file())
 paths.update(LOCAL/n for n in ('shared_oracle.py','oracle-binding.json','storage.py','kernel_guard.hpp','chain-registration.json','packet56_submission.py','selection-template.json','bundle_selection.py','kd_reference.py','kd_projection_replay.py','receipt_replay.py','build_engine.py'))
 for folder in ('submission-vendor','submission-templates','timing-fixture'):
  paths.update((LOCAL/'lineage-inputs'/folder).glob('*'))
 for folder in (LOCAL/'native-base',LOCAL/'lineage-inputs/vendor/repo'):
  paths.update(f for f in folder.rglob('*') if f.is_file() and not f.is_symlink() and 'build' not in f.relative_to(folder).parts)
 # Evidence root paths are historical regression data, not external dependencies.
 paths.update(P/'evidence'/(n+'.json') for n in GATES if n!='retained-report-regression')
 sources={str(f.relative_to(ROOT)):sha(f) for f in sorted(paths)}
 for gate in rows.values():sources.update(gate.get('sources',{}))
 sources.update(rows['build']['sources']);sources.update(rows['build']['artifacts'])
 subprocess.run([sys.executable,'-B',str(LOCAL/'shared_oracle.py'),'--require-complete'],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,check=True,timeout=180)
 row=dict(schema='packet189.cpu-composition.v1',passed=True,device_executed=False,device_quality_pending=True,arithmetic='iq3-p49-split32-v1',sources=sources,variants=list(MODES),gates=list(GATES),binary_sha256=sha(P/'build/device/own-rt-iq3'))
 save(P/'cpu-seal.json',row)
 for mode in MODES:save(P/'lineage'/mode/'screen-seal.json',row)
 save(P/'placement-validation/wrapper-seal.json',row)
 return verify()
def verify():
 row=json.loads((P/'cpu-seal.json').read_text());assert row['passed'] and row['device_executed'] is False
 check_sources(row['sources'])
 for mode in row['variants']:assert json.loads((P/'lineage'/mode/'screen-seal.json').read_text())==row
 assert json.loads((P/'placement-validation/wrapper-seal.json').read_text())==row
 return row
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--seal',action='store_true');a=ap.parse_args();seal() if a.seal else verify();print('CPU source/build seal PASS; device quality pending')
