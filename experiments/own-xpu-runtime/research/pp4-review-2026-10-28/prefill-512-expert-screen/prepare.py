#!/usr/bin/env python3
"""CPU route-only preparation; never opens tensor payloads or contacts devices."""
import collections,hashlib,json,pathlib,struct
here=pathlib.Path(__file__).resolve().parent
runtime=here.parents[2]
source=pathlib.Path('/dev/shm/ownrt-lab-experts/routes-4096.bin')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
records=collections.defaultdict(list)
with source.open('rb') as f:
 while f.tell()<source.stat().st_size:
  n=struct.unpack('<I',f.read(4))[0];assert 0<n<1024
  label=f.read(n).decode();rows,slots=struct.unpack('<II',f.read(8));assert slots==10*rows
  records[label].append({'offset':f.tell(),'rows':rows,'bytes':slots*12});f.seek(slots*12,1)
placement=runtime/'gsq-rco-iq3s/loader/placement.tsv'
entries=[l.split() for l in placement.read_text().splitlines()]
families={22:('IQ2_S',17.40),18:('IQ3_XXS',9.82),20:('IQ4_NL',11.17),42:('Q2_0',4.94)}
cases=[];inputdir=here/'inputs';inputdir.mkdir(exist_ok=False)
for kind,(family,weight) in families.items():
 chosen_layers=set()
 for e in entries:
  name=e[1]
  if '_exps.weight' not in name or int(e[3])!=kind:continue
  layer=int(name.split('.')[1])
  if not 24<=layer<=47 or layer in chosen_layers:continue
  # Alternate gate/up when the family has them, without inventing routes.
  op='down' if kind in (20,42) else ('gate' if not chosen_layers else 'up')
  if f'ffn_{op}_exps' not in name:continue
  label=f'blk.{layer}.exps{op}';rs=records[label]
  assert len(rs)>=16 and all(r['rows']==32 for r in rs[:16])
  with source.open('rb') as f:
   raw=b''
   for r in rs[:16]:f.seek(r['offset']);raw+=f.read(r['bytes'])
  assert len(raw)==512*10*12 and raw[:256*10*12]!=raw[256*10*12:]
  routes=list(struct.iter_unpack('<III',raw));k,rows,experts=map(int,e[9:]);assert experts==512
  assert all(0<=a<512 and b==0 and c==rows for a,b,c in routes)
  # Cheap CPU integer bucket support census uses exact captured slot order.
  tiles=lambda seq:sum((n+3)//4 for n in collections.Counter(a for a,b,c in seq).values())
  paired=tiles(routes[:2560])+tiles(routes[2560:]);whole=tiles(routes)
  identifier=f'{family}-l{layer}-{op}';p=inputdir/(identifier+'.routes.bin');p.write_bytes(raw)
  cases.append({'id':identifier,'family':family,'type':kind,'profile_weight_percent':weight,'tensor':name,'shard':e[0],'tensor_offset':int(e[4]),'tensor_bytes':int(e[5]),'dimensions':[k,rows,experts],'route_label':label,'routes':str(p.relative_to(here)),'routes_sha256':sha(p),'source_records':rs[:16],'paired256_T4_tiles':paired,'whole512_T4_tiles':whole,'T4_tile_reduction_percent':100*(1-whole/paired),'scope':'Historical actual native routes from synthetic rank1 driver stream; layers24-47, not current reference-policy stage0. Actual model tensor bytes to be read only in root-authorized later run.'})
  chosen_layers.add(layer)
  if len(chosen_layers)==2:break
 assert len(chosen_layers)==2,(family,chosen_layers)
pins=[placement,runtime/'gsq-rco-iq3s/loader/shard-auth.tsv',runtime/'research/prefill-experts/evidence/cputest/test_experts.cpp',runtime/'research/prefill-iq4-packed/bench/harness.hpp',runtime/'engine/src/stage2/packet194-expert-diet-engine/prefill_experts.hpp',runtime/'engine/src/gsq-rco-iq3s/dense-packed-block/engine/build/source/prefill_experts_policies.hpp',runtime/'engine/src/stage2/packet2/loader/gguf.cpp',runtime/'engine/src/stage2/packet2/loader/gguf.hpp']
m={'schema':'ownrt.prefill512-operator-registration.v1','status':'prepared-uncompiled-unrun','device_calls':0,'model_payload_reads':0,'route_source':str(source),'route_source_bytes':source.stat().st_size,'route_historical_sha256_not_reread':'73b1cdfc51bc74b8a485a75dcae6276371ad36d942f052d3879451a132efa7ea','model':'SC117-Qwen3.8-Flash-Next-GSQ-RCO-abliterated-IQ3_S-eec4e10a (historical mixed per-tensor quant)','arithmetic':'unchanged existing xgroup Bucket+Tiles; T4 S4 GRF128, RW2 IQ2_S and RW1 other families; GDIV4 RLOOP4','cases':cases,'sources':{str(p):sha(p)for p in pins},'gate':'All output F32 words and every status equal512 vs paired256, for512/257/511 rows plus separately labeled invalid/partial routes. Actual IDs never remapped/repeated.','timing':'Existing interleaved hot/cold harness adapted to event spans covering all bucket+tile kernels (four baseline versus two candidate); no endpoint claim.','threshold':'For each cache condition, average within family across its two layers, then sum(profile_weight*(1-candidate/control))/43.33; >10% reduction and all gates pass supports next integration decision. No end-to-end extrapolation.'}
(here/'registration.json').write_text(json.dumps(m,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'cases':len(cases),'route_bytes_read':sum(61440 for _ in cases),'tile_reduction_percent':{c['id']:c['T4_tile_reduction_percent'] for c in cases}}))
