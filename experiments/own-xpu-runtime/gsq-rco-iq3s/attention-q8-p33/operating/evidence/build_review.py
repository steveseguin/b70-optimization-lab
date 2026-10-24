"""Offline artifact readback; never invokes native artifact or compiler."""
import hashlib,json,resource,shlex
from pathlib import Path
R=Path('/home/steve/llm-optimizations');P=Path(__file__).resolve().parents[2];cache={}
def sha(path):
 p=Path(path);p=p if p.is_absolute() else R/p
 if str(p) not in cache:
  h=hashlib.sha256()
  with p.open('rb') as stream:
   while b:=stream.read(262144):h.update(b)
  cache[str(p)]=h.hexdigest()
 return cache[str(p)]
def verify(mapping):
 for p,h in mapping.items():assert sha(p)==h,p
def run():
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 f=P/'evidence/native-build.json';j=json.loads(f.read_text());parent=P.parent/'integration/evidence/full-native-build.json';old=json.loads(parent.read_text());prep=json.loads((P/'preparation.json').read_text())
 assert j['passed'] and j['mode']=='native' and not j['native_binary_invoked'];assert j['objects_reused']==39 and len(j['object_sha256'])==40
 assert sha(parent)==j['control_compilation_receipt_sha256']==prep['control_build_sha256'];assert sha(P/'preparation.json')==j['preparation_sha256']
 for m in (j['source_sha256'],j['dependencies'],j['object_sha256'],j['prerequisite_sha256'],prep['source_sha256']):verify(m)
 assert sha(j['binary'])==j['binary_sha256'] and sha(j['commands'][0][0])==j['compiler_sha256']
 assert len(j['commands'])==2 and '-c' in j['commands'][0] and '-fno-fast-math' in j['commands'][0] and '-ffp-contract=off' in j['commands'][0]
 assert len(j['reused_object_provenance'])==40 and sum(x['reuse'] for x in j['reused_object_provenance'])==39
 changed={str(P.parent/'integration/build/private/source/diet-native/native-src/main.cpp'),str(P.parent/'integration/generic_engine.hpp')}
 for row in j['reused_object_provenance']:
  assert sha(row['object'])==row['object_sha256']==old['object_sha256'][row['object']]
  assert sha(row['depfile'])==row['depfile_sha256'];verify(row['dependencies'])
  deps=shlex.split(Path(row['depfile']).read_text().replace('\\\n',' ').split(':',1)[1]);repo={str(Path(x).resolve()) for x in deps if str(Path(x).resolve()).startswith(str(R)+'/')}
  assert repo==set(row['dependencies']),(row['index'],'depfile set differs');assert bool(repo&changed)==(not row['reuse'])
  if row['reuse']:assert row['object'] in j['commands'][1] and row['object'] in j['object_sha256'] and not row['affected']
 assert j['reused_object_provenance'][0]['object'] not in j['commands'][1] and j['offline']['p33_object_reused_unchanged']
 d=Path(j['binary']).parent
 for name,key in [('entry-device.bc','entry_device_sha256'),('kernel-entries.log','kernel_entries_sha256'),('symbols.log','symbols_sha256')]:assert sha(d/name)==j['offline'][key]
 symbols=(d/'symbols.log').read_text();assert 'p33::Kernel<0u, (iq3::Type)8, 6144u, 1u>' in symbols,'linked Q8p33 family'
 cpu=json.loads((P/'evidence/cpu-proof.json').read_text());scale=json.loads((P/'evidence/scale-census.json').read_text());assert cpu['passed'] and cpu['proof']['passed'];verify(cpu['source_sha256']);assert sha(P/'scale_census.py')==scale['source_sha256']
 assert scale['passed'] and scale['all_scales_finite'] and len(scale['tensors'])==48 and scale['totals']['infinity']==scale['totals']['nan']==0
 out=P/'operating/evidence/independent-build-review.json'
 r=dict(schema='ownrt.gsq.attention-independent-build-review.v1',passed=True,native_executed=False,build_receipt_sha256=sha(f),binary_sha256=j['binary_sha256'],source_pins=len(j['source_sha256']),entry_dependencies=len(j['dependencies']),linked_objects=40,reused_objects=39,actual_depfiles_reparsed=40,changed_shared_dependency_intersections_in_reused_objects=0,unique_files_rehashed=len(cache),cpu_proof_sha256=sha(P/'evidence/cpu-proof.json'),scale_census_sha256=sha(P/'evidence/scale-census.json'),scale_totals=scale['totals'],checks=['Exactly one native compilation/link; oldentry0 excluded and39 original objects retained','Build/source/dependency/object/compiler/binary/prerequisite and offline artifact hashes independently match','All40 actual retained depfiles reparsed: onlyentry0 intersects changed Engine/main or generic_engine','Q8K6144Split1 p33 kernel family linked; original p33 object retained','Exact48 policy with variant6/shape/BF16/no-routes/fp32/extent Matrix guards source-reviewed','P6/P33 tile8-stride256 adjacentSG32 arithmetic and exact expanded Q8 representation source-reviewed'],limitations=['No candidate native execution by reviewer; CPU exceptional results and actual finite weight census do not establish arbitrary activationNaN semantics on GPU','Runtime correctness still requires per-arm baseline token/state gates; no speed promotion','Object reuse applies only to this exact source delta/dependency closure'],source_sha256={str(P/'prepare.py'):sha(P/'prepare.py'),str(P/'preparation.json'):sha(P/'preparation.json'),str(P/'overlay.patch'):sha(P/'overlay.patch'),str(Path(__file__).resolve()):sha(__file__)})
 with out.open('x') as s:json.dump(r,s,indent=2);s.write('\n')
 print(json.dumps({'passed':True,'sha256':sha(out),'source_pins':len(j['source_sha256']),'objects':40,'reused':39}))
if __name__=='__main__':run()
