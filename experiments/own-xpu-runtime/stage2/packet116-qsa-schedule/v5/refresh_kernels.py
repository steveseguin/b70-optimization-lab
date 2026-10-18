"""Refresh both QSA objects after concurrent source review, before final seals."""
import json
from build_engine import P,ROOT,B,sha,save,limits,run
def main():
 limits();commands=json.loads((P/'engine-commands.json').read_text());row=json.loads((P/'evidence/build.json').read_text())
 kernel_paths=[P.parent/'p116_qsa_submit.cpp',*P.parent.glob('p116*.hpp')]
 before={str(f.relative_to(ROOT)):sha(f) for f in kernel_paths}
 for mode in ('gnu-host','device'):
  for stem in ('p116_submit','link'):
   old=next(r for r in commands if r['name']==mode+'-'+stem)
   updated=run(old['command'],old['name']+'-reviewed')
   old['reviewed_seconds']=updated['seconds']
  row['artifacts'][f'build/{mode}/own-rt-iq3']=sha(B/mode/'own-rt-iq3')
  row['artifacts'][f'build/{mode}/p116_submit.o']=sha(B/mode/'p116_submit.o')
 assert before=={str(f.relative_to(ROOT)):sha(f) for f in kernel_paths},'kernel source changed during refresh'
 row['sources'].update(before)
 row['sources'][str((P/'refresh_kernels.py').relative_to(ROOT))]=sha(P/'refresh_kernels.py')
 row['commands']=commands;row['reviewed_kernel_refresh']=True
 save(P/'engine-commands.json',commands);save(P/'evidence/build.json',row)
if __name__=='__main__':main()
