#!/usr/bin/env python3
"""Seal observation-only packet57; inherit exact operator proofs, never speed."""
import argparse,json,os,time
from pathlib import Path
from storage import digest
P=Path(__file__).resolve().parent; ROOT=P.parents[3]; B=P/'build'
DELTA={'main.cpp','mtp.hpp','rank.hpp','request_reset.hpp'}
def require(ok,message):
 if not ok:raise ValueError(message)
def parent_proof():
 binding=json.loads((P/'parent-binding.json').read_text());parent=P.parent/binding['parent_packet']
 require(digest(parent/'build-receipt.json')==binding['seal_sha256'],'parent seal changed')
 base=json.loads((parent/'build-receipt.json').read_text())
 require(base['passed'] and base['device_admission_ready'],'parent not qualified')
 manifest=json.loads((P/'base-source-manifest.json').read_text())['files_sha256']
 for name,expected in manifest.items():
  if Path(name).suffix not in ('.cpp','.hpp','.inc','.bf16'):continue
  require(digest(parent/name)==expected,'parent source changed: '+name)
  require(base['sources'].get(str((parent/name).relative_to(ROOT)))==expected,'parent source unsealed: '+name)
  if name not in DELTA:require(digest(P/name)==expected,'arithmetic source changed: '+name)
 for name in ('selection.json','oracle-binding.json','p56_config.hpp','mtp-manifest.tsv','memory-plan.json'):
  require(digest(P/name)==digest(parent/name),'inherited identity changed: '+name)
 proof=json.loads((P/'parent-device-proof.json').read_text())
 require(set(proof['windows'])=={'K0','K1a','K1b','K2','W0p','KD','WS128x','WS128'},'required parent device proofs missing')
 for name,item in proof['windows'].items():
  path=Path(item['path']);require(digest(path)==item['sha256'],'parent window changed: '+name)
  row=json.loads(path.read_text())
  require(row['passed'] and row['device_executed'] and row['window']==name,'parent device proof incomplete')
  require(row['build_receipt_sha256']==binding['seal_sha256'],'parent proof wrong seal')
  for key,value in {'card':0,'context':4096,'draft_rank':1,'target_split':23}.items():require(row[key]==value,'parent scope differs')
  require(row['artifacts_sha256']==base['artifacts_sha256'],'parent artifacts differ')
 require(digest(Path(proof['dispatch']['path']))==proof['dispatch']['sha256'],'parent qualified dispatch changed')
 k2=json.loads(Path(proof['windows']['K2']['path']).read_text())
 require(k2['dispatch_sha256']==proof['dispatch']['sha256'],'dispatch not qualified by parent K2')
 return base,proof

def checked():
 import build
 from seal_context import precise
 base,proof=parent_proof();current=build.compiled_sources();artifacts={};modes={}
 for mode in ('gnu-host','device'):
  path=P/('build-'+mode+'-receipt.json');row=json.loads(path.read_text())
  require(row['passed'] and row['device_executed'] is False and row['compiled_sources_sha256']==current,'stale '+mode+' build')
  require(digest(B/mode/'compile_commands.json')==row['compile_commands_sha256'],'compiler commands changed')
  for command in json.loads((B/mode/'compile_commands.json').read_text()):precise(command.get('arguments',command.get('command')),mode=='device')
  for name,expected in row['checked_mirror_sha256'].items():require(digest(B/name)==expected,'checked mirror changed')
  for name,expected in row['link_files_sha256'].items():require(digest(B/name)==expected,'link changed');precise((B/name).read_text(),mode=='device')
  for name,expected in row['artifacts_sha256'].items():require(digest(B/name)==expected,'binary changed');artifacts[name]=expected
  modes[mode]=digest(path)
 gate=json.loads((P/'p57-cpu-gates.json').read_text())
 require(gate['passed'] and gate['device_executed'] is False,'CPU gate failed')
 require(gate['binary_sha256']==artifacts['gnu-host/own-rt-iq3'],'stale CPU binary gate')
 require(gate['compiled_sources_sha256']==current,'stale CPU source gate')
 require(digest(B/'p57-tests.log')==gate['unit_tests_log_sha256'],'CPU test log changed')
 for name,expected in gate['unit_test_sources_sha256'].items():require(digest(P/name)==expected,'CPU test changed')
 sources=build.sources()
 parent=P.parent/'packet56-draft-prefix'
 for name,expected in base['sources'].items():
  if '/oracle/' in name:
   own=name.replace(parent.name,P.name);require(digest(ROOT/own)==expected,'inherited oracle changed');sources[own]=expected
  elif not name.startswith(str(parent.relative_to(ROOT))+'/') and name!='scripts/packet49_submission.py':
   require(digest(ROOT/name)==expected,'inherited external dependency changed: '+name);sources[name]=expected
 for name in ('experiments/own-xpu-runtime/stage2/packet34-replay-bench/window.py','experiments/own-xpu-runtime/stage2/packet2/tests/device_window.py'):
  sources[name]=digest(ROOT/name)
 for f in P.iterdir():
  if f.is_file() and not f.is_symlink() and (f.suffix=='.sh' or f.name in ('parent-binding.json','parent-device-proof.json','base-source-manifest.json','runtime-revision.json','p57-preregistration.json')):sources[str(f.relative_to(ROOT))]=digest(f)
 # External owner/kernel inputs remain bound by the actual compile closure.
 result=dict(base)
 result.update(schema='packet57.diagnostic-cpu-seal.v1',parent_packet='packet56-draft-prefix',parent_seal_sha256=digest(P.parent/'packet56-draft-prefix/build-receipt.json'),
  runtime_revision=json.loads((P/'runtime-revision.json').read_text())['runtime_revision'],
  diagnostic=True,qualifying=False,no_speed_claim=True,device_executed=False,device_admission_ready=True,
  sources=sources,artifacts_sha256=artifacts,original_artifacts_sha256=artifacts,mode_receipts_sha256=modes,
  gates_sha256={'p57-cpu-gates.json':digest(P/'p57-cpu-gates.json')},
  inherited_gates={'scope':'Exact packet56 unchanged kernels/controller; not new packet57 device measurements','proof_sha256':digest(P/'parent-device-proof.json')},
  diagnostic_design=json.loads((P/'p57-preregistration.json').read_text()))
 return result

def verify():
 row=json.loads((P/'build-receipt.json').read_text());require(row==checked(),'packet57 source/build/gate binding changed');return row

def main():
 p=argparse.ArgumentParser();p.add_argument('--verify',action='store_true');a=p.parse_args()
 require(os.getpriority(os.PRIO_PROCESS,0)==19,'nice19 required')
 require(set(os.sched_getaffinity(0))<=set(range(4,16))|set(range(20,32)),'helper affinity required')
 if a.verify:row=verify()
 else:
  require(not (P/'build-receipt.json').exists() and not (B/'device-cards01-a').exists(),'never overwrite seal or started chain')
  row=checked();(P/'build-receipt.json').write_text(json.dumps(row,indent=2)+'\n')
 print(json.dumps({'passed':True,'device_executed':False,'diagnostic':True,'qualifying':False,'seal_sha256':digest(P/'build-receipt.json')}))
if __name__=='__main__':main()
