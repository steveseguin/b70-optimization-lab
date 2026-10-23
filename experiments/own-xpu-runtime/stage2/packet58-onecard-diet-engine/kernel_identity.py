#!/usr/bin/env python3
"""Packet58-onecard-diet-engine device-code identity of the production path (CPU only; offline tools, no device).

A. FINAL DEVICE IMAGE (the authority). clang-offload-extract pulls every embedded sycl-spir64 image out of the record engine
   (packet58-onecard-cache23 build/device/own-rt-iq3 = the 36.602512 tok/s chain's engine 083e3853..., read in place and
   digest-verified) and out of this packet's engine; images are matched by their EntryPoint kernel-name sets (llvm-spirv
   --to-text). Required: every record image is present in the new engine BYTE-IDENTICAL (SPIR-V bytes), and the new engine
   adds exactly one image whose only entry point is p58ag_diet::GateUp::submit. So the production path's device code is
   byte-for-byte the record's; the diet is one added kernel image.
B. RECORD TU OBJECT (packet194's per-kernel method). The pinned packet58aj p58ag_submit.o (replaced-objects.json) and the
   rebuilt one are unbundled, split per kernel (sycl-post-link -split=kernel) and compared as SPIR-V text: every inherited
   kernel present, opcode-identical and canonically identical; the rebuilt record TU adds no kernel. The diet TU object
   (p58ag_diet_submit.o) holds p58ag_diet::GateUp plus vtable-instantiated copies of production kernels (the pinned header
   binds through Production); those duplicates are linkonce_odr and resolve to the record TU's definitions at the device
   link, which A proves on the final image.
"""
import glob,hashlib,json,re,resource,shutil,subprocess,tempfile
from pathlib import Path
from build_engine import P,ROOT,B,sha,save,limits
T=Path('/opt/intel/oneapi/compiler/2026.0/bin/compiler')
NEW=B/'device/p58ag_submit.o';DIET=B/'device/p58ag_diet_submit.o';ENGINE=B/'device/own-rt-iq3'
PARENT=P.parent/'packet58-onecard-cache23';PARENT_ENGINE=PARENT/'build/device/own-rt-iq3';RECORD_ENGINE_SHA='083e3853427041be36faeaf804781e4204b79ed19296648e0aaa7f6c5f1b151a'
RECORD_KERNELS={'gateup_halfcache':'_ZTSZZNK9p58ag_exp6KernelILN3iq34TypeE22ELj2560ELj64ELb0ELb1ELj0ELb1EE6submit','gateup_direct_decode':'_ZTSZZNK9p58ag_exp6KernelILN3iq34TypeE22ELj2560ELj64ELb0ELb1ELj0ELb0EE6submit'}
DIET_KERNEL='_ZTSZZNK10p58ag_diet6GateUp6submit'
EXT='--spirv-ext=+all,-SPV_INTEL_runtime_aligned,-SPV_KHR_untyped_pointers,-SPV_KHR_fma'
def run(cmd):subprocess.run([str(c) for c in cmd],check=True,capture_output=True,timeout=900)
def kernels(d):
    out={}
    for f in sorted(glob.glob(str(d/'*.bc'))):
        nm=subprocess.run([str(T/'llvm-nm'),'--defined-only',f],capture_output=True,text=True).stdout
        for l in nm.splitlines():
            k=l.split()[-1]
            if k.startswith('_ZTS') and (' W ' in l or ' T ' in l):out[k]=f
    return out
def text(f):
    run([T/'llvm-spirv',EXT,'--spirv-text',f,'-o',f+'.spt']);return [l.strip() for l in Path(f+'.spt').read_text().splitlines() if l.strip() and not l.startswith(';')]
def canon(lines):
    names={}
    for s in lines:
        m=re.match(r'\d+ Decorate (\d+) LinkageAttributes "([^"]+)" (Import|Export)',s)
        if m:names[m.group(1)]=m.group(2)
        m=re.match(r'\d+ EntryPoint \d+ (\d+) "([^"]+)"',s)
        if m:names[m.group(1)]=m.group(2)
    start=next(i for i,s in enumerate(lines) if s.split()[1:2]==['Function'])
    LIT={'Load':3,'Store':2,'CopyMemorySized':3,'CopyMemory':2,'CompositeExtract':3,'CompositeInsert':4,'VectorShuffle':4,'Variable':2,'LoopMerge':2,'SelectionMerge':1,'GenericCastToPtrExplicit':3,'LifetimeStart':1,'LifetimeStop':1}
    m={};out=[];ops=[]
    for s in lines[start:]:
        toks=s.split();new=toks[:2];op=toks[1];ops.append(op);lit=LIT.get(op,10**9)
        for j,t in enumerate(toks[2:]):
            literal=j>=lit or (op=='ExtInst' and j==3) or (op=='Switch' and j>=2 and (j-2)%2==0)
            if re.fullmatch(r'\d+',t) and not literal:
                if t in names:new.append('@'+names[t]);continue
                if t not in m:m[t]=str(len(m))
                new.append(m[t])
            else:new.append(t)
        out.append(' '.join(new))
    pre=[s for s in lines[:start] if s.split()[1:2] in (['Capability'],['Extension'],['MemoryModel'],['ExecutionMode'])]
    return out,ops,pre
def images(binary,d):
    run([T/'clang-offload-extract','--output='+str(d/'image'),binary]);out={}
    for f in sorted(d.glob('image.*'),key=lambda p:int(p.suffix[1:])):
        txt=d/(f.name+'.spt');run([T/'llvm-spirv','--to-text',f,'-o',txt])
        names=re.findall(r'EntryPoint \d+ \d+ "([^"]+)"',txt.read_text())
        assert f.read_bytes()[:4]==b'\x03\x02\x23\x07','not a SPIR-V image: '+f.name
        out[f.name]=dict(sha256=hashlib.sha256(f.read_bytes()).hexdigest(),bytes=f.stat().st_size,kernels=sorted(names))
    return out
def main():
    limits()
    build=json.loads((P/'evidence/build.json').read_text())
    assert sha(NEW)==build['artifacts']['build/device/p58ag_submit.o'] and sha(DIET)==build['artifacts']['build/device/p58ag_diet_submit.o'] and sha(ENGINE)==build['artifacts']['build/device/own-rt-iq3'],'objects/engine differ from the build receipt'
    parent_build=json.loads((PARENT/'evidence/build.json').read_text())
    assert sha(PARENT_ENGINE)==parent_build['artifacts']['build/device/own-rt-iq3']==RECORD_ENGINE_SHA,'record engine changed'
    pinned_row=next(r for r in json.loads((P/'replaced-objects.json').read_text())['records'] if r['destination']=='build/device/p58ag_submit.o')
    PINNED=Path(pinned_row['original']);assert sha(PINNED)==pinned_row['digest'],'pinned parent object changed'
    work=Path(tempfile.mkdtemp(prefix='p58de-kid-',dir=B))
    try:
        # A. final device images
        (work/'old').mkdir();(work/'new').mkdir()
        old_images=images(PARENT_ENGINE,work/'old');new_images=images(ENGINE,work/'new')
        by_old={tuple(v['kernels']):k for k,v in old_images.items()};by_new={tuple(v['kernels']):k for k,v in new_images.items()}
        assert len(by_old)==len(old_images) and len(by_new)==len(new_images),'ambiguous kernel sets'
        identical=[];differing=[];missing=[]
        for s,k in by_old.items():
            if s not in by_new:missing.append(dict(image=k,kernels=list(s)));continue
            (identical if old_images[k]['sha256']==new_images[by_new[s]]['sha256'] else differing).append(dict(old=k,new=by_new[s],kernels=list(s),bytes=old_images[k]['bytes']))
        added=[dict(image=k,kernels=list(s),bytes=new_images[k]['bytes']) for s,k in by_new.items() if s not in by_old]
        assert not missing and not differing,dict(missing=missing,differing=differing)
        assert len(added)==1 and len(added[0]['kernels'])==1 and added[0]['kernels'][0].startswith(DIET_KERNEL),added
        record_image=next(r for r in identical if any(k.startswith(RECORD_KERNELS['gateup_halfcache']) for k in r['kernels']))
        assert any(k.startswith(RECORD_KERNELS['gateup_direct_decode']) for k in record_image['kernels'])
        # B. record TU object, per kernel
        for name,obj in (('pinned',PINNED),('rebuilt',NEW),('diet',DIET)):
            d=work/name;d.mkdir();run([T/'clang-offload-bundler','--unbundle','--type=o','--targets=sycl-spir64-unknown-unknown','--input',obj,'--output',d/'device.bc'])
            run([T/'sycl-post-link','-split=kernel','-O0',d/'device.bc','-o',d/'out.table'])
        old,new,diet=kernels(work/'pinned'),kernels(work/'rebuilt'),kernels(work/'diet')
        obj_missing=[k for k in old if k not in new];obj_added=[k for k in new if k not in old]
        assert not obj_missing and not obj_added,dict(missing=obj_missing,added=obj_added)
        report=[];canonical=0;opcode=0
        for k,f in old.items():
            a,oa,pa=canon(text(f));b,ob,pb=canon(text(new[k]))
            same_ops=oa==ob and pa==pb;same_canon=a==b and pa==pb;opcode+=same_ops;canonical+=same_canon
            first=[dict(line=i,pinned=x,rebuilt=y) for i,(x,y) in enumerate(zip(a,b)) if x!=y][:3]
            report.append(dict(kernel=k,function_lines=len(a),rebuilt_function_lines=len(b),opcode_identical=same_ops,canonical_identical=same_canon,first_differences=first))
        save(P/'evidence/kernel-identity-object-level.json',dict(passed=opcode==canonical==len(old),kernels=report))
        assert opcode==canonical==len(old),'an inherited kernel of the record TU is not identical at object level (see evidence/kernel-identity-object-level.json)'
        diet_names=sorted(diet);assert any(DIET_KERNEL in k for k in diet_names) and all(k in old or DIET_KERNEL in k for k in diet_names),diet_names
        save(P/'evidence/kernel-identity.json',dict(passed=True,device_executed=False,
            final_image=dict(record_engine=str(PARENT_ENGINE.relative_to(ROOT)),record_engine_sha256=RECORD_ENGINE_SHA,new_engine=str(ENGINE.relative_to(ROOT)),new_engine_sha256=sha(ENGINE),
                record_images=len(old_images),new_images=len(new_images),byte_identical_images=len(identical),differing_images=0,missing_images=0,added_images=added,
                record_gateup_image=record_image,method='clang-offload-extract (sycl-spir64 images) -> images matched by EntryPoint kernel-name sets (llvm-spirv --to-text) -> SPIR-V bytes compared',
                statement='the production path device code is byte-for-byte the record engine\'s; the diet is exactly one added kernel image'),
            record_tu_object=dict(pinned_object=str(PINNED.relative_to(ROOT)),pinned_sha256=sha(PINNED),rebuilt_object=str(NEW.relative_to(ROOT)),rebuilt_sha256=sha(NEW),
                inherited_kernels=len(old),opcode_identical=opcode,canonical_identical=canonical,added_kernels=obj_added,kernels=report,
                record_kernels={r:next(x['kernel'] for x in report if x['kernel'].startswith(n)) for r,n in RECORD_KERNELS.items()},
                method='clang-offload-bundler unbundle -> sycl-post-link -split=kernel -O0 -> llvm-spirv --spirv-text; function sections compared by opcode sequence and by canonical form (globals/entry points by name, ids renumbered by first appearance)'),
            diet_tu_object=dict(object=str(DIET.relative_to(ROOT)),sha256=sha(DIET),kernels=diet_names,
                note='p58ag_diet::GateUp plus vtable-instantiated copies of production kernels (the pinned header binds through Production::bind); linkonce_odr duplicates resolve to the record TU definitions at the device link (final-image proof A)'),
            first_build_diagnostic='co-compiling the diet inside the record TU changed the shared decode_tile inlining and with it both inherited p58ag_exp kernels (attempt 1, build/kernel-identity-attempt1-cotu*.out); the diet therefore lives in its own TU',
            caveat='whole-object and whole-module bytes differ by the include paths embedded as source metadata; the final SPIR-V images carry none and are compared as bytes',
            sources={str(f.relative_to(ROOT)):sha(f) for f in (P/'kernel_identity.py',NEW,DIET,PINNED,ENGINE,PARENT_ENGINE,P/'native/generated/p58ag_submit.cpp',P/'native/generated/p58ag_diet_submit.cpp',P/'native/generated/p58ag_diet.hpp')}))
        print('kernel identity PASS: final images',len(identical),'byte-identical of',len(old_images),'; added',added[0]['image'],'; record TU',len(old),'kernels opcode/canonically identical; diet TU kernels',len(diet_names))
    finally:shutil.rmtree(work,ignore_errors=True)
if __name__=='__main__':resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
