"""Compare a completed precision candidate against retained independent CPU arrays."""
import argparse,hashlib,json,math,struct
from pathlib import Path
BASE=Path(__file__).resolve().parent.parent
CPU=Path('/dev/shm/sc117-reference-capture-cpu-20261028-r2/on')
OLD=Path('/dev/shm/sc117-l4-history-target244-20261028-r3/output/result.json')
def sha(b):return hashlib.sha256(b).hexdigest()
def metrics(a,b):
 assert len(a)==len(b) and len(a)%4==0
 av=struct.unpack('<%df'%(len(a)//4),a);bv=struct.unpack('<%df'%(len(b)//4),b)
 assert all(math.isfinite(v)for v in av+bv)
 delta=[x-y for x,y in zip(av,bv)]
 return dict(unequal_words=sum(a[i:i+4]!=b[i:i+4]for i in range(0,len(a),4)),max_abs=max(map(abs,delta)),rms=math.sqrt(sum(x*x for x in delta)/len(delta)))
def capture(result,layer):
 rows=[x for x in result['layer_captures']if Path(x['path']).name==f'layer-{layer:02d}.bf16'];assert len(rows)==1
 r=rows[0];b=Path(r['path']).read_bytes();assert len(b)==r['bytes']==40960 and sha(b)==r['sha256'] and r['dtype']=='F32 little-endian'
 return b

def run(root):
 out=root/'output';result=json.loads((out/'result.json').read_text());assert result['passed'] and result['error']is None and not result['live_pids'] and all(v==0 for v in result['returncodes'].values())
 old=json.loads(OLD.read_text());refs=json.loads((BASE/'cpu-r2/comparison.json').read_text())['layers'];rows=[]
 for i in range(48):
  cpu=(CPU/f'layer-{i:02d}.f32').read_bytes();assert sha(cpu)==refs[i]['reference_sha256']
  new=capture(result,i);before=capture(old,i)
  rows.append(dict(layer=i,reference_sha256=sha(cpu),candidate_sha256=sha(new),old_sha256=sha(before),candidate_vs_cpu=metrics(new,cpu),old_vs_cpu=metrics(before,cpu),candidate_vs_old=metrics(new,before)))
 state=out/'native/rank1/state-244';index=(state/'state-index.tsv').read_bytes();seal=(state/'state-seal.txt').read_text().splitlines();assert len(seal)==5 and sha(index)==seal[3]
 matches=[line.split('\t')for line in index.decode().splitlines()[1:]if line.startswith('logits.bin\t')];assert len(matches)==1
 name,offset,length,digest=matches[0];assert int(length)==248320*4 and result['verified_full_state_sources']['1'][name]==digest
 if (state/'state.bundle').exists():
  with (state/'state.bundle').open('rb')as f:f.seek(int(offset));native=f.read(int(length))
 else:native=(root/'candidate-logits.f32').read_bytes() # Previously extracted and authenticated before verified archive cleanup.
 assert len(native)==int(length) and sha(native)==digest
 cpu=(BASE/'cpu-r1/original/logits-243.f32').read_bytes();assert sha(cpu)=='9dae567c488c22e87c3212d8d408d0a0dd42fad62b666768caa3d06fc39a01d4'
 values=struct.unpack('<248320f',native);reference=struct.unpack('<248320f',cpu)
 argmax=max(range(len(values)),key=values.__getitem__);assert result['actual_output_ids']==[argmax]
 report=dict(schema='ownrt.precision-candidate-cpu-comparison.v1',native_output=argmax,cpu_argmax=max(range(len(reference)),key=reference.__getitem__),matches_saved_cpu=argmax==16568,logits=metrics(native,cpu),native_top10=[dict(token=i,logit=values[i],cpu_logit=reference[i])for i in sorted(range(len(values)),key=values.__getitem__,reverse=True)[:10]],candidate_logit_16568=values[16568],candidate_logit_6343=values[6343],layers=rows,scope='One fixed teacher-forced244-token prefix. This is not full-suite/free-running fidelity. Layer differences are localization evidence, not a causal proof by themselves.')
 (root/'comparison-cpu.json').write_text(json.dumps(report,indent=2)+'\n');(root/'candidate-logits.f32').write_bytes(native)
 print(json.dumps({k:report[k]for k in ('native_output','cpu_argmax','matches_saved_cpu','logits','candidate_logit_16568','candidate_logit_6343')}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);run(p.parse_args().root)
