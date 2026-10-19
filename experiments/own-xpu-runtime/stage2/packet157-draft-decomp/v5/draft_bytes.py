"""Miniature arithmetic parity, both timing modes and independent processes."""
import json,resource,subprocess
from p157_v5_build_engine import P,ROOT,B,sha,save,limits,run

def main():
 limits();out=B/'draft-bytes';out.mkdir(exist_ok=True);prior=json.loads((P/'engine-commands.json').read_text())
 args=list(next(r['command'] for r in prior if r['name']=='gnu-host-entry-main'));args=args[:args.index('-c')]
 run([*args,'-c',P/'native/draft_bytes.cpp','-o',out/'entry.o'],'draft-bytes-compile')
 link=list(next(r['command'] for r in prior if r['name']=='gnu-host-link'));link=[str(out/'entry.o') if x.endswith('/entry-main.o') else x for x in link if not x.endswith('own-rt-iq3-entry.cpp.o')];link[link.index('-o')+1]=str(out/'fixture');run(link,'draft-bytes-link')
 rows=[]
 for mode in ('off','split'):
  selection=json.loads((P/'lineage'/mode/'selection.json').read_text());selection['choices'].update(head='production',experts='production');path=out/(mode+'.json');save(path,selection)
  for repeat in (1,2):
   limits();dest=out/(mode+str(repeat));cp=subprocess.run([str(out/'fixture'),str(path),sha(path),str(dest)],stdin=subprocess.DEVNULL,capture_output=True,text=True)
   log=P/'evidence'/('draft-bytes-'+mode+str(repeat)+'.log');log.write_text(cp.stdout+cp.stderr);assert cp.returncode==0,log.read_text()[-4000:]
   rows.append(dict(mode=mode,repeat=repeat,result=json.loads(cp.stdout),state=json.loads((dest/'draft-state/all-state.json').read_text()),log_sha256=sha(log)))
 assert all(r['state']==rows[0]['state'] and r['result']==rows[0]['result'] for r in rows),'timing changed miniature draft state/proposals'
 # Allocation labels are not filesystem paths. Use tuples, never a path/hash map.
 for row in rows:row['state']['mutable_sha256']=sorted(row['state']['mutable_sha256'].items())
 save(P/'evidence/draft-bytes.json',dict(passed=True,device_executed=False,rows=rows,full_model_quality_pending=True,mini_target_choices=['production head','production experts'],unchanged_draft_selection=True,sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'draft_bytes.py',P/'native/draft_bytes.cpp',P/'native-src/mtp.hpp',P/'native/split_timing.hpp']}))
 print('Miniature draft state/proposals: control/timed x2 fresh processes PASS')
if __name__=='__main__':resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,)*2);main()
