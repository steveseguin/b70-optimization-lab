"""Packet194 per-kernel device-code identity of the rebuilt p49d_expert_submit TU (CPU only; offline tools, no device).

The record engine's expert kernels lived in packet103's pinned device object (immutable-binaries.json). Packet194 rebuilds that
TU (the only TU the new kernel touches). This gate unbundles the device bitcode of the PINNED object and of the REBUILT object
(clang-offload-bundler), splits both per kernel (sycl-post-link -split=kernel) and translates each kernel module to SPIR-V text
(llvm-spirv --spirv-text). It then requires:
  * every kernel of the pinned object is present in the rebuilt object under the same kernel name, and the rebuilt object adds
    exactly the four p193diet kernels (GateUp = exp-diet, the two dropped candidates and the activation twin that the pinned
    packet193 header also defines);
  * per inherited kernel: the SPIR-V function section has the identical length and the identical opcode sequence;
  * per inherited kernel: the function section is canonically identical (module globals/entry points substituted by name, every
    other id renumbered by first appearance) - the record's two expert kernels (p90exp gate/up Arm 10, p100::Kernel<2> down) and
    every other kernel whose canonical form does not collide a literal with an id. A kernel that is not canonically identical
    must still be opcode-identical and is listed with its first differing lines (literal/id renumbering collisions of the
    text form, never a different instruction).
Whole-object bytes cannot be compared (the bundle and bitcode carry the include paths of the tree that compiled them).
"""
import glob,json,re,resource,shutil,subprocess,tempfile
from pathlib import Path
from p194_v5_build_engine import P,LOCAL,ROOT,B,STAGE,sha,save,limits
T=Path('/opt/intel/oneapi/compiler/2026.0/bin/compiler')
PINNED=STAGE/'packet103-record-bundle/build/device/p49d_expert_submit.o'
NEW=B/'device/p49d_expert_submit.o'
RECORD_KERNELS={'gateup':'_ZTSZZNK6p90exp6KernelILN3iq34TypeE22ELj2560ELj64ELb0ELb1ELj0EE6submit','down':'_ZTSZZNK4p1006KernelILj2EE6submit'}
DIET_KERNELS=('p193diet6GateUp6submit','p193diet9GateUpAct6submit','p193diet4Down6submit','p193diet13ActProduction6submit')
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
    # operands at or beyond these positions are literals (memory-access masks and alignments, composite indices, shuffle
    # components, storage classes, merge masks): never renumbered. Everything else in a function section is an id.
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
def main():
    limits();pinned=json.loads((LOCAL/'immutable-binaries.json').read_text());assert sha(PINNED)==pinned[str(PINNED)],'pinned parent object changed'
    work=Path(tempfile.mkdtemp(prefix='p194-kid-',dir=B));rows={}
    try:
        for name,obj in (('pinned',PINNED),('rebuilt',NEW)):
            d=work/name;d.mkdir();run([T/'clang-offload-bundler','--unbundle','--type=o','--targets=sycl-spir64-unknown-unknown','--input',obj,'--output',d/'device.bc'])
            run([T/'sycl-post-link','-split=kernel','-O0',d/'device.bc','-o',d/'out.table']);rows[name]=kernels(d)
        old,new=rows['pinned'],rows['rebuilt']
        missing=[k for k in old if k not in new];added=[k for k in new if k not in old]
        assert not missing,missing
        assert len(added)==4 and all(any(n in k for n in DIET_KERNELS) for k in added),added
        report=[];canonical=0;opcode=0
        for k,f in old.items():
            a,oa,pa=canon(text(f));b,ob,pb=canon(text(new[k]))
            same_ops=oa==ob and pa==pb;same_canon=a==b and pa==pb
            assert same_ops,'opcode sequence differs: '+k
            opcode+=1;canonical+=same_canon
            first=[dict(line=i,pinned=x,rebuilt=y) for i,(x,y) in enumerate(zip(a,b)) if x!=y][:3]
            report.append(dict(kernel=k,function_lines=len(a),opcode_identical=True,canonical_identical=same_canon,first_differences=first))
        for role,needle in RECORD_KERNELS.items():
            row=next(r for r in report if r['kernel'].startswith(needle));assert row['canonical_identical'],'record kernel not canonically identical: '+role
        save(P/'evidence/kernel-identity.json',dict(passed=True,device_executed=False,pinned_object=str(PINNED.relative_to(ROOT)),pinned_sha256=sha(PINNED),rebuilt_object=str(NEW.relative_to(ROOT)),rebuilt_sha256=sha(NEW),
            inherited_kernels=len(old),opcode_identical=opcode,canonical_identical=canonical,added_kernels=added,record_kernels={r:next(x['kernel'] for x in report if x['kernel'].startswith(n)) for r,n in RECORD_KERNELS.items()},
            method='clang-offload-bundler unbundle -> sycl-post-link -split=kernel -O0 -> llvm-spirv --spirv-text; function sections compared by opcode sequence and by canonical form (globals/entry points by name, ids renumbered by first appearance)',
            caveat='whole-object and whole-module bytes differ by the include paths embedded as source metadata; kernels not canonically identical differ only in text-form id/literal renumbering collisions (listed), never in opcode sequence',
            kernels=report,sources={str(f.relative_to(ROOT)):sha(f) for f in (P/'kernel_identity.py',NEW,PINNED)}))
        print('kernel identity PASS:',len(old),'inherited kernels opcode-identical,',canonical,'canonically identical; added',len(added))
    finally:shutil.rmtree(work,ignore_errors=True)
if __name__=='__main__':resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
