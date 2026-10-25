import os, json, hashlib, subprocess, shutil
from pathlib import Path
R=Path('/home/steve/llm-optimizations'); L=R/'experiments/own-xpu-runtime/gsq-rco-iq3s'; O=L/'service-speed/d-mtp-fp8'
T=Path('/dev/shm/d-mtp-fp8'); T.mkdir(exist_ok=False)
os.environ['TMPDIR']=str(T)
A=json.loads((L/'service-speed/a-reset-stream/build-receipt.json').read_text()); B=json.loads((L/'recurrent-f32/evidence/native-build.json').read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run(c,label):
    assert shutil.disk_usage('/').free>=27600000000
    with (O/'evidence'/f'{label}.log').open('w') as f:
        subprocess.run(c,stdout=f,stderr=subprocess.STDOUT,check=True,cwd=R,env=os.environ)
    print(label, 'done', flush=True)
commands=[]
for c,label in [(A['commands'][0].copy(),'entry-base'),(B['commands'][4].copy(),'16-base')]:
    c[c.index('-MF')+1]=str(T/(label+'.d'));c[c.index('-o')+1]=str(T/(label+'.o'))
    run(c,label);commands.append(c)
link=A['commands'][1].copy()
link=[str(T/'entry-base.o') if x==A['commands'][0][-1] else str(T/'16-base.o') if x==B['commands'][4][-1] else x for x in link]
link[link.index('-o')+1]=str(T/'baseline')
run(link,'baseline-link');commands.append(link)
r={'commands':commands,'binary_sha256':sha(T/'baseline'),'expected_binary_sha256':A['binary_sha256'],'objects':{str(T/'entry-base.o'):sha(T/'entry-base.o'),str(T/'16-base.o'):sha(T/'16-base.o')},'matched':sha(T/'baseline')==A['binary_sha256'],'native_invoked':False}
(O/'evidence/reproducibility.json').write_text(json.dumps(r,indent=2)+'\n')
print('baseline matched:',r['matched'],r['binary_sha256'],flush=True)
assert r['matched']
