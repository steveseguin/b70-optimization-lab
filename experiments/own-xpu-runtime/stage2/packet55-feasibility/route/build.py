#!/usr/bin/env python3
"""Independent diagnostic overlay of the immutable packet49c checked sources.

Copies source only. Does not invoke parent generators or mutate sealed trees.
Exactly one compiler runs at a time; no executable is run by this script.
"""
import argparse, hashlib, json, os, re, shlex, subprocess
from pathlib import Path
P=Path(__file__).resolve().parent
BASE=P.parents[1]/'packet49c-round2'
ROOT=P.parents[4]
B=P/'build'

def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def replace(s,old,new,count=1):
    if s.count(old)!=count:raise ValueError(f'overlay anchor occurrence {s.count(old)} expected {count}: {old[:90]}')
    return s.replace(old,new)
def overlay(name,s):
    if name=='main.cpp':
        s=replace(s,'a.tokens > 0 && a.tokens <= 128','a.tokens > 0 && a.tokens <= 256')
        s=replace(s,'  flash::Event issue_site(size_t index,flash::Event dep) {',(P/'route_hook.inc').read_text()+'\n  flash::Event issue_site(size_t index,flash::Event dep) {')
        s=replace(s,'    if(class_timing)family_ms[site.family]+=ms(started)-(wait_ms-waited);','    if(class_timing)family_ms[site.family]+=ms(started)-(wait_ms-waited);\n    p55_target_route(p.launches[index]);')
        s=replace(s,'    execute_site(l);\n    // Bring-up','    execute_site(l);\n    p55_target_route(l);\n    // Bring-up')
        # The sparse mirror lives elsewhere; default manifest must stay explicit.
        s=replace(s,'fs::path(__FILE__).parent_path()/"mtp-manifest.tsv"','fs::path('+json.dumps(str(BASE/'mtp-manifest.tsv'))+')')
    elif name=='mtp.hpp':
        s=replace(s,'bool gemv=false; int cls=0; bool head=false;','bool gemv=false; int cls=0; bool head=false; bool route=false; Allocation route_ids{},route_probability{};')
        s=replace(s,'   e.set_class("draft."+l.label);site.cls=e.current_cls;','   site.route=l.op=="route";if(site.route){site.route_ids=id(l.outputs[0]);site.route_probability=id(l.outputs[1]);}\n   e.set_class("draft."+l.label);site.cls=e.current_cls;')
        s=replace(s,'    for(const auto& cmd:site.commands){auto event=e.dev(0).issue(cmd);e.finish(0,{event,event,1},site.gemv);}','    for(const auto& cmd:site.commands){auto event=e.dev(0).issue(cmd);e.finish(0,{event,event,1},site.gemv);}\n    if(site.route)e.p55_route(0,position,0,true,site.route_ids,site.route_probability,p.g.top);')
        s=replace(s,'    e.guard();if(e.a.timing=="class")e.set_class("draft."+l.label);direct(l);','    e.guard();if(e.a.timing=="class")e.set_class("draft."+l.label);direct(l);\n    if(l.op=="route")e.p55_route(0,position,0,true,id(l.outputs[0]),id(l.outputs[1]),p.g.top);')
    elif name=='single_device.cpp':
        s=replace(s,'    auto d=found[card];','''    auto d=found[card];
    if(card!=2&&card!=3)throw std::runtime_error("p55 route admits cards2+3 only");
    ze_pci_ext_properties_t pci{};pci.stype=ZE_STRUCTURE_TYPE_PCI_EXT_PROPERTIES;
    if(zeDevicePciGetPropertiesExt(sycl::get_native<sycl::backend::ext_oneapi_level_zero>(d),&pci)!=ZE_RESULT_SUCCESS ||
       pci.address.domain!=0 || pci.address.bus!=(card==2?0x43u:0x47u) || pci.address.device!=0 || pci.address.function!=0)
      throw std::runtime_error("p55 selected physical PCI identity mismatch");''')
    elif name=='rank.hpp':
        s=replace(s,'   bool completing_redo=image.before_command','   ++engine->p55_command;engine->p55_speculative=r.speculative;engine->p55_fixture=r.fixture;\n   bool completing_redo=image.before_command')
    return s

def prepare():
    B.mkdir(exist_ok=True)
    original=BASE/'build/checked';mirror=B/'checked'
    sources={}
    for f in sorted(original.rglob('*')):
        if not f.is_file():continue
        rel=f.relative_to(original);target=mirror/rel;target.parent.mkdir(parents=True,exist_ok=True)
        data=f.read_text();sources[str(f.relative_to(ROOT))]=sha(f)
        if f.parent==original/BASE.relative_to(ROOT):data=overlay(f.name,data)
        data=data.replace(str(original),str(mirror))
        if not target.exists() or target.read_text()!=data:target.write_text(data)
    for name in ('entry-main.cpp','own-rt-iq3-entry.cpp'):
        s=(BASE/'build/device'/name).read_text().replace(str(original),str(mirror))
        (B/name).write_text(s)
    record=dict(schema='packet55.route-overlay.v1',base=str(BASE.relative_to(ROOT)),base_checked_sha256=sources,
                overlay_sha256={n:sha(P/n) for n in ('build.py','route_hook.inc')},
                arithmetic='iq3-p49-split32-v1',device_executed=False)
    (B/'overlay-receipt.json').write_text(json.dumps(record,indent=2)+'\n')
    return record

def build(mode):
    record=prepare();out=B/mode;out.mkdir(exist_ok=True)
    commands=json.loads((BASE/'build'/mode/'compile_commands.json').read_text());objects=[];actual=[]
    for row in commands:
        argv=shlex.split(row['command']);source=Path(row['file'])
        if not ('CMakeFiles/programs.dir/' in row['output'] or source.name=='own-rt-iq3-entry.cpp'):continue
        if source.name in ('entry-nongemv_fixture.cpp','entry-k2_fixture.cpp'):continue
        # Inherited source include closure stays identical except the three hooks.
        argv=[x.replace(str(BASE/'build/checked'),str(B/'checked')) for x in argv]
        if source.name in ('entry-main.cpp','own-rt-iq3-entry.cpp'):
            argv[-1]=str(B/source.name)
        obj=out/(str(len(objects))+'.o');argv[argv.index('-o')+1]=str(obj)
        print('compile',source.name,flush=True)
        with (out/(source.name+'.log')).open('w') as log:
            subprocess.run(argv,stdout=log,stderr=subprocess.STDOUT,check=True)
        objects.append(obj);actual.append(argv)
        if sum(f.stat().st_size for f in B.rglob('*') if f.is_file())>650_000_000:raise RuntimeError('route build exceeded650MB budget')
    compiler=shlex.split(commands[0]['command'])[0]
    args=[compiler,'-fno-fast-math','-ffp-contract=off']
    args+=['-fsycl','-fdenormal-fp-math=ieee','-foffload-fp32-prec-div','-foffload-fp32-prec-sqrt'] if mode=='device' else ['-fopenmp']
    binary=out/'own-rt-iq3'
    args += list(map(str,objects))+['-o',str(binary),'-lcrypto']
    if mode=='device':args+=['-lze_loader','-Wl,-rpath,/opt/intel/oneapi/compiler/2026.0/lib']
    with (out/'link.log').open('w') as log:subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,check=True)
    record.update(mode=mode,commands=actual,link=args,binary_sha256=sha(binary))
    (out/'build-receipt.json').write_text(json.dumps(record,indent=2)+'\n')
    print(binary,sha(binary),flush=True)

def refresh_main(mode='device'):
    receipt=B/mode/'build-receipt.json';record=json.loads(receipt.read_text())
    before={str(p.relative_to(B/'checked')):sha(p) for p in (B/'checked').rglob('*') if p.is_file()}
    updated=prepare()
    after={str(p.relative_to(B/'checked')):sha(p) for p in (B/'checked').rglob('*') if p.is_file()}
    changed=[n for n in set(before)|set(after) if before.get(n)!=after.get(n)]
    allowed={str(BASE.relative_to(ROOT)/n) for n in ('main.cpp','rank.hpp','mtp.hpp','request_reset.hpp')}
    if not set(changed)<=allowed:raise ValueError('refresh-main cannot reuse objects with changed non-main dependencies:'+str(changed))
    # Traverse every compiled TU's quoted-include closure. No assumption that a
    # changed header belongs only to main: recompile all actual dependents.
    def closure(source):
        pending=[Path(source)];seen=set()
        while pending:
            path=pending.pop().resolve()
            if path in seen:continue
            seen.add(path)
            for name in re.findall(r'^\s*#include\s*"([^"\n]+)"',path.read_text(),re.M):
                candidate=Path(name) if Path(name).is_absolute() else path.parent/name
                if candidate.is_file():pending.append(candidate)
        return seen
    changed_paths={(B/'checked'/n).resolve() for n in changed};rebuilt=[]
    for command in record['commands']:
        affected=sorted(str(p) for p in closure(command[-1])&changed_paths)
        if not affected:continue
        with (B/mode/(Path(command[-1]).name+'-refresh.log')).open('w') as log:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True)
        rebuilt.append(dict(command=command,changed_dependencies=affected))
    if not rebuilt:raise ValueError('no changed source dependent object found')
    with (B/mode/'link-refresh.log').open('w') as log:subprocess.run(record['link'],stdout=log,stderr=subprocess.STDOUT,check=True)
    prior=sha(receipt);(B/mode/'initial-build-receipt.json').write_bytes(receipt.read_bytes())
    record.update(updated);record.update(binary_sha256=sha(B/mode/'own-rt-iq3'),compiled_mirror_sha256=after,
        refresh_main=dict(changed_sources=changed,recompiled=rebuilt,prior_receipt_sha256=prior,before_mirror_sha256=before))
    receipt.write_text(json.dumps(record,indent=2)+'\n')
    print('refreshed',record['binary_sha256'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=('prepare','gnu-host','device','refresh-main'));a=p.parse_args()
    if os.getpriority(os.PRIO_PROCESS,0)!=19:raise SystemExit('nice19 required')
    if not os.sched_getaffinity(0)<=set(range(4,16))|set(range(20,32)):raise SystemExit('preparation affinity required')
    prepare() if a.mode=='prepare' else refresh_main() if a.mode=='refresh-main' else build(a.mode)
