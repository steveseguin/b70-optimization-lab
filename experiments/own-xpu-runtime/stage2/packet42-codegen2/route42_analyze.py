"""Archive production route GEN, with static counts and final-SPIRV bindings."""
import gzip, hashlib, importlib.util, json, re
from pathlib import Path
P=Path(__file__).resolve().parent;OLD=P.parent/'packet33-codegen';A=P/'route42-assembly';A.mkdir(exist_ok=True)
spec=importlib.util.spec_from_file_location('p33analyze',OLD/'analyze.py');a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
offline=json.loads((P/'route42-offline.json').read_text());rows=[]
sources=[('incumbent',OLD/'build/igc-bc39da',i,phase,shape) for phase in range(5) for i,shape in [(4+phase*2,'rounded'),(5+phase*2,'plain')]]
sources += [('candidate',P/offline['rows'][0]['dump'],i,phase,shape) for phase,i0 in [(0,1),(1,3),(4,5)] for i,shape in [(i0,'rounded'),(i0+1,'plain')]]
sources += [('candidate',P/offline['rows'][1]['dump'],1,2,'sg32')]
for family,folder,entry,phase,shape in sources:
 f,=folder.glob('*_%04d.asm'%entry);raw=f.read_bytes();t=raw.decode();name=f'{family}.stage{phase}.{shape}';out=A/(name+'.asm.gz');out.write_bytes(gzip.compress(raw,mtime=0));symbol=t.splitlines()[0].removeprefix('//.kernel ')
 binary,body=a.binary_text_sections(folder)[symbol];encoded=f.with_suffix('.dat').read_bytes();assert body.startswith(encoded) and not any(body[len(encoded):])
 row=dict(name=name,phase=phase,shape=shape,asm=str(out.relative_to(P)),asm_sha256=hashlib.sha256(raw).hexdigest(),kernel=symbol,whole_static=a.stats(a.instructions(t.splitlines())),grf=int(re.search(r'numGRF=(\d+)',t)[1]),spill_metadata=[l for l in t.splitlines() if l.startswith('//.spill')],offline_gen_binding=dict(progbin_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),dat_sha256=hashlib.sha256(encoded).hexdigest(),elf_text_sha256=hashlib.sha256(body).hexdigest(),dat_equals_text_prefix_zero_padding=True))
 row['block_counts']={x[:3]:a.stats(a.instructions(x.splitlines())) for x in re.split(r'(?m)^// B',t)[1:]}
 for z in folder.glob('*.zeinfo'):
  if symbol in z.read_text():
   dest=A/(name+'.zeinfo.gz');dest.write_bytes(gzip.compress(z.read_bytes(),mtime=0));row['zeinfo']=str(dest.relative_to(P));break
 rows.append(row)
(P/'route42-codegen.json').write_text(json.dumps(dict(device_executed=False,method='Whole static GEN counts, all scalar-type/exception/rounding branches included. Not dynamic instruction or timing predictions. Candidate SPIRV exact offsets in native binary are in route42-offline.json.',rows=rows),indent=2)+'\n')
for r in rows:print(r['name'],r['whole_static']['instructions'],r['whole_static']['memory_messages'],r['grf'])
