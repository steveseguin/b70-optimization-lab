"""Reproducible conditional-CFG sums; never cycles or measured issue counts."""
import gzip,hashlib,importlib.util,json,re
from pathlib import Path
P=Path(__file__).resolve().parent;OLD=P.parent/'packet33-codegen';A=P/'expert-assembly';A.mkdir(exist_ok=True)
spec=importlib.util.spec_from_file_location('p33analyze',OLD/'analyze.py');a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
base=[14,15,16,23,24,26,27,28,29,36,37,39]+list(range(40,57))+[58]
pair=[12,13,14,21,22,24,25,26,27,34,35,37,38,40,41]+list(range(42,57))
pair2=[57,58,59,66,67,69,70,71,72,79,80,82,83,85,86]+list(range(87,103))+[104]
rowspec=[('p28.paired.wg32.IQ2_S',OLD/'build/igc-a6003b',76,base,16),('p28.paired.wg32.IQ3_S',OLD/'build/igc-a6003b',82,base,16),('p33.down.bank',OLD/'build/igc-p33-cfc890008950',1,[22,23,24,31],8),('p33.down.select',OLD/'build/igc-p33-cfc890008950',2,[78,79,80]+list(range(87,144)),8),('p42.down.bank_scalar',P/'build/expert/igc',1,[22,23,24,31],8),('p42.down.select_vector',P/'build/expert/igc',2,[78,79,80]+list(range(87,144)),8),('p42.gate.packed.IQ2_S',P/'build/expert/igc',3,pair+pair2,32),('p42.gate.packed.IQ3_S',P/'build/expert/igc',4,pair+[57,59],16)]
rows=[]
for name,folder,entry,path,weights in rowspec:
 files=[f for f in folder.glob('*_%04d.asm'%entry) if ('6KernelI' in f.read_text().splitlines()[0])];assert len(files)==1,(name,files);f=files[0];raw=f.read_bytes();t=raw.decode();blocks={int(x[:3]):a.instructions(x.splitlines()) for x in re.split(r'(?m)^// B',t)[1:]};chosen=[ins for block in path for ins in blocks[block]]
 out=A/(name+'.asm.gz');out.write_bytes(gzip.compress(raw,mtime=0));r=dict(name=name,asm=str(out.relative_to(P)),asm_sha256=hashlib.sha256(raw).hexdigest(),source_dump=str(f),kernel=t.splitlines()[0],whole_static=a.stats(a.instructions(t.splitlines())),conditional_path_blocks=path,weights_per_active_lane=weights,conditional_cfg_sum=a.stats(chosen),condition='valid route; finite normal half scales; full interior tile; both projections for gate; all lookup arms active across SIMD lanes for select; excludes reduction and prologue; loop bookkeeping included for gate')
 r['instructions_per_weight']=r['conditional_cfg_sum']['instructions']/weights;r['messages_per_weight']=r['conditional_cfg_sum']['memory_messages']/weights
 if 'select' in name:
  for label,offsets in [('homogeneous_min',[4,5]),('homogeneous_max',[1,3])]:
   path2=[78,79,80]+[b+o for b in range(87,143,7) for o in [0]+offsets]+[143];r[label]=dict(blocks=path2,**a.stats([ins for b in path2 for ins in blocks[b]]))
 sections=a.binary_text_sections(folder);symbol=t.splitlines()[0].removeprefix('//.kernel ');binary,body=sections[symbol];encoded=f.with_suffix('.dat').read_bytes();assert body.startswith(encoded) and not any(body[len(encoded):]);r['offline_gen_binding']={'progbin_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'dat_sha256':hashlib.sha256(encoded).hexdigest(),'elf_text_sha256':hashlib.sha256(body).hexdigest(),'dat_equals_text_prefix_zero_padding':True};
 r['block_counts']={str(k):a.stats(v) for k,v in blocks.items()};r['grf']=int(re.search(r'numGRF=(\d+)',t)[1]);r['spill_metadata']=[l for l in t.splitlines() if l.startswith('//.spill')]
 for z in folder.glob('*.zeinfo'):
  if t.splitlines()[0].removeprefix('//.kernel ') in z.read_text():
   dest=A/(name+'.zeinfo.gz');dest.write_bytes(gzip.compress(z.read_bytes(),mtime=0));r['zeinfo']=str(dest.relative_to(P));break
 rows.append(r)
report=dict(device_executed=False,method='GEN conditional-CFG instruction sums, not cycles. 16 paired weights means eight gate plus eight up weights; common activation traffic counted once. Counts are SIMD instructions normalized per active lane weight, not divided again by SIMD32. Odd/tail/nonfinite paths excluded from hot-path figures and retained in full compressed dumps.',rows=rows)
(P/'expert-codegen.json').write_text(json.dumps(report,indent=2)+'\n')
for r in rows:print(r['name'],r['conditional_cfg_sum']['instructions'],r['conditional_cfg_sum']['memory_messages'],r['weights_per_active_lane'])
