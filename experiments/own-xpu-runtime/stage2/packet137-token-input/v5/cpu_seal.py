"""Packet137 CPU seal. A partial table or inherited pass never admits a device."""
import subprocess,sys
from pathlib import Path
from common import HERE,ROOT,read,require,save,sha,verify_map
GATES=('build','full-shape','reset-bytes','protocol','state-regression','exec-limits','policy','safety')
def symlinks():
 links=read(HERE.parent/'parent-manifest.json')['symlinks']
 require(len(links)==182,'parent link inventory changed')
 for name,target in links.items():
  path=HERE.parent/name
  require(path.is_symlink() and str(path.readlink())==target,'parent symlink changed: '+name)
 return len(links)
def oracle():
 sys.path.insert(0,str(HERE.parent))
 from shared_oracle import static_binding
 binding=static_binding()
 command=['nice','-n','19','taskset','-c','8-15,24-31','python3','-B',str(HERE.parent/'shared_oracle.py'),'--require-complete']
 cp=subprocess.run(command,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=180)
 require(cp.returncode==0,'shared oracle refused: '+cp.stderr[-2000:])
 return dict(binding=binding,command=command,returncode=0)
def safe_sources(rows):
 # Oracle authority is checked by its exact original binding, never source maps.
 result={}
 for name,digest in rows.items():
  if '/oracle/' in name:continue
  path=ROOT/name
  require(path.resolve().is_relative_to(ROOT),'external source map refused: '+name)
  result[name]=digest
 return result

def external_runtime_sources():
 wrapper=HERE.parents[1]/'screen/v4-lanes/wrapper-seal.json';row=read(wrapper)
 require(row.get('passed') is True and row.get('device_executed') is False,'shared wrapper CPU seal incomplete')
 sources=safe_sources(row['sources']);verify_map(ROOT,sources)
 return {**sources,str(wrapper.relative_to(ROOT)):sha(wrapper)}
def validate_receipts():
 rows={name:read(HERE/'evidence'/(name+'.json')) for name in GATES}
 inherited=read(HERE.parent/'parent136-binding.json');verify_map(ROOT,inherited['sources'])
 for name,row in rows.items():
  require(row.get('passed') is True and row.get('device_executed') is False,'incomplete CPU gate '+name)
  if row.get('sources'):verify_map(ROOT,safe_sources(row['sources']))
 for name,digest in rows['build']['artifacts'].items():require(sha(HERE/name)==digest,'changed binary '+name)
 startup=rows['full-shape']['startup_runs'];require(len(startup)>=4 and all(r['result']['passed'] for r in startup),'startup gate incomplete')
 full=rows['full-shape']['runs'];require(len(full)==4 and all(r['result']['views']==5 and r['result']['fresh_start_capture_identity'] for r in full),'five-view capture/reset incomplete')
 reset=rows['reset-bytes']['runs'];require(len(reset)==4 and {(r['rank'],r['repeat']) for r in reset}=={(r,n) for r in (0,1) for n in (0,1)},'reset repeats incomplete')
 state=rows['state-regression']['runs'];require(len(state)==4 and all(r['cases']==491 and r['position_classes']==43 for r in state),'bank cancellation/redo regression incomplete')
 require(len({r['canonical_sha256'] for r in state})==1,'token input state regression bytes differ')
 for run in state:require(sha(ROOT/run['archive'])==run['archive_sha256'],'state transcript changed')
 require(sha(HERE/'build/reset-bytes/fixture')==rows['reset-bytes']['binary_sha256'],'reset fixture changed')
 require(sha(HERE/'build/full-shape/fixture')==rows['full-shape']['binary_sha256'],'full-shape fixture changed')
 require(all(r['rollback_checks']==(5 if r['rank']==0 else 0) for r in reset),'host/device history rollback regression incomplete')
 require(all(r['bank_resets']==(6 if r['rank']==0 else 0) for r in reset),'six bank roles reset regression incomplete')
 for run in full+startup:
  a=run['artifact'];require(a['all_original_bytes_verified'] and a['members']>0 and sha(ROOT/a['path'])==a['sha256'],'shape archive changed')
 for run in rows['protocol']['runs']:
  require(len(run['brackets'])==4,'GNU/Intel fresh CPU brackets missing')
  for bracket in run['brackets']:
   require(len(bracket['rows'])==5 and all(r['cached_tokens']==0 and r['draft_proposals'] for r in bracket['rows']),'CPU proposal replay missing')
  for name,digest in run['binaries'].items():require(sha(ROOT/name)==digest,'protocol binary changed')
 for name,digest in rows['protocol']['cpu_runtime_libraries'].items():require(sha(name)==digest,'CPU runtime changed')
 table=read(HERE.parent/'evidence/table.json');require(table.get('passed') is True and table.get('complete') is True and table['rows']==248320 and table['bytes']==1271398400,'full table proof required')
 require(sha(table['path'])==table['sha256'] and Path(table['path']).stat().st_size==table['bytes'],'table changed')
 require({r['compiler'] for r in table['runs']}=={'GNU','Intel'},'two compiler table replay required')
 for run in table['runs']:
  require(sha(run['command'][0])==run['binary_sha256'],'table proof binary changed')
  require(sha(HERE.parent/'build/table'/(run['compiler']+'-248320.log'))==run['log_sha256'],'table replay log changed')
 verify_map(ROOT,table['sources'])
 target=read(HERE.parent/'evidence/target.json');require(target['passed'] and len(target['runs'])==4,'target block gate incomplete');verify_map(ROOT,target['sources'])
 for run in target['runs']:
  require(run['result']['block_cases']==131072 and run['result']['history_steps']==4096,'scale/history coverage incomplete')
  require(sha(ROOT/run['binary'])==run['binary_sha256'],'target binary changed')
 return rows,table,target

def seal():
 symlinks()
 rows,table,target=validate_receipts()
 from bracket import load_config
 load_config(HERE/'configs/bracket.json');binding=oracle()
 paths=set(HERE.glob('*.py'))|set(HERE.glob('native/*'))|set(HERE.glob('native-src/*'))|set(HERE.glob('lineage/*.json'))|set(HERE.glob('configs/*.json'))
 paths.add(HERE/'launch-environment.json');paths.discard(HERE/'lineage/screen-seal.json');paths.update(HERE/'evidence'/(n+'.json') for n in GATES)
 paths.add(HERE.parent/'parent136-binding.json')
 paths.add(HERE.parent/'parent-manifest.json')
 paths.add(HERE.parent/'PREREGISTRATION.md')
 paths.update((HERE.parent/'evidence/table.json',HERE.parent/'evidence/target.json',HERE/'source-copy-provenance.json',HERE.parent/'oracle-binding.json',HERE.parent/'shared_oracle.py'))
 sources={str(p.relative_to(ROOT)):sha(p) for p in paths if p.is_file()}
 for path in [HERE/'build/reset-bytes/fixture',HERE/'build/full-shape/fixture',*(ROOT/r['archive'] for r in rows['state-regression']['runs'])]:sources[str(path.relative_to(ROOT))]=sha(path)
 sources.update(read(HERE.parent/'parent136-binding.json')['sources'])
 for run in table['runs']:
  for path in (Path(run['command'][0]),HERE.parent/'build/table'/(run['compiler']+'-248320.log')):sources[str(path.relative_to(ROOT))]=sha(path)
 for row in [*rows.values(),table,target]:sources.update(safe_sources(row.get('sources',{})))
 sources.update(external_runtime_sources())
 binary=HERE/'build/device/own-rt-iq3'
 require(rows['build']['artifacts']['build/device/own-rt-iq3']==sha(binary),'device binary changed')
 row=dict(schema='packet137.v5.cpu-seal.v1',passed=True,device_executed=False,sources=sources,binary_sha256=sha(binary),cpu_runtime_libraries=rows['protocol']['cpu_runtime_libraries'],table={k:table[k] for k in ('path','sha256','bytes','rows')},oracle=binding,startup_views=['original','draft_table','target_buffers','both'])
 save(HERE/'lineage/screen-seal.json',row);save(HERE/'placement-validation/wrapper-seal.json',row);return verify()
def verify():
 symlinks()
 row=read(HERE/'lineage/screen-seal.json');require(row.get('passed') is True and row.get('device_executed') is False,'CPU seal missing')
 verify_map(ROOT,row['sources'])
 require(sha(HERE/'build/device/own-rt-iq3')==row['binary_sha256'],'binary changed')
 for name,digest in row['cpu_runtime_libraries'].items():require(sha(name)==digest,'CPU runtime changed')
 table=row['table'];require(sha(table['path'])==table['sha256'] and Path(table['path']).stat().st_size==1271398400,'table changed')
 for name in ('selection','candidate','draft_table','target_buffers'):
  c=read(HERE/'lineage'/(name+'.json'))['choices'];require(c['token_table_sha256']==table['sha256'] and c['token_table_path']==table['path'],'table selection changed')
 require(read(HERE/'placement-validation/wrapper-seal.json')==row,'wrapper seal changed');oracle();return row
if __name__=='__main__':
 if '--seal' in sys.argv:seal()
 else:verify()
