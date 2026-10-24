#!/usr/bin/env python3
"""Materialize an additive P195-derived generic Engine; never compile or run it."""
import difflib, hashlib, importlib.util, json, re
from pathlib import Path
P=Path(__file__).resolve().parent; R=P.parents[3]; L=P.parent
S=R/'experiments/own-xpu-runtime/stage2'; OLD=S/'packet194-expert-diet-engine'; P195=S/'packet195-record-bundle-diet'
BIND=R/'experiments/own-xpu-runtime/ops/packet195-orchestration/inputs/packet194-native.json'
OUT=P/'build/private'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def replace(t,a,b,n=1):
    if t.count(a)!=n:raise ValueError('nonunique transform '+repr(a[:100])+': '+str(t.count(a)))
    return t.replace(a,b)
def module(p,name):
    spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def transform_main(t):
    t=replace(t,'struct Options {','struct Options {\n  bool gsq_packed=false;')
    t=replace(t,'if (k == "--retain-steps")','if(k=="--gsq-packed") a.gsq_packed=true;\n    else if (k == "--retain-steps")')
    t=replace(t,'  return a;\n}\nstruct Weights {','''  if(a.gsq_packed){
    require(a.dispatch.empty()&&a.selection.empty()&&a.selection_sha256.empty(),"GSQ mode refuses inherited selections");
    require(a.memory=="resident"&&a.rank>=0&&!a.first&&!a.record&&!a.priority_probe&&a.draft_capture.empty(),"GSQ resident rank mode only");
    require(!a.legacy&&!a.audit_prepare_each&&!a.argument_audit,"GSQ prepared mode only");
    require(a.mini||a.context==4096,"GSQ initial real context4096 only");
  }
  return a;
}
struct Weights {''')
    t=replace(t,'    std::ifstream identity(a.auth);','''    if(a.gsq_packed)gsq_integration::verify_admission(a.plan,a.auth,a.model);
    iq3::Admission admitted;
    std::ifstream identity(a.auth);''')
    t=replace(t,'      paths.push_back(p);','      paths.push_back(p);\n      if(a.gsq_packed)admitted.shards.push_back({name,bytes,dev,ino,mtime,ctime});')
    t=replace(t,'identity.eof() && paths.size() == 3','identity.eof() && paths.size() == (a.gsq_packed?2:3)')
    t=replace(t,'    model = std::make_unique<iq3::Model>(paths, iq3::read_plan(a.plan));','''    if(a.gsq_packed){admitted.expected=iq3::read_plan(gsq_integration::placement_path);model=std::make_unique<iq3::Model>(paths,iq3::read_plan(a.plan),admitted);}
    else model = std::make_unique<iq3::Model>(paths, iq3::read_plan(a.plan));''')
    # Return the actual primitive Builder plan after original rank placement.
    t=replace(t,'  std::vector<flash::Launch> fused;','  if(a.gsq_packed)return p; // Preserve original gather, status and primitive consumers.\n  std::vector<flash::Launch> fused;')
    anchor='static unsigned selected_variant(const Weights& w,const Options& a,const flash::Plan& p,const flash::Launch& l,size_t projection=0) {'
    t=replace(t,anchor,anchor+'\n  if(a.gsq_packed)return !a.mini&&l.weights.at(projection)=="output.weight"?6:0;')
    t=replace(t,'gemv_choices.emplace(&l,std::make_pair(packet26::dispatch.gemv_for(l.label),variants));','gemv_choices.emplace(&l,std::make_pair(a.gsq_packed?(l.weights[0]=="output.weight"&&!a.mini?std::string("p33.dense.segment"):std::string("gsq.packed")):packet26::dispatch.gemv_for(l.label),variants));')
    t=replace(t,'auto enabled=[&](const std::string& key){','auto enabled=[&](const std::string& key){if(a.gsq_packed)return false;')
    t=replace(t,'  unsigned weight_variant(const std::string& name)const {','  unsigned weight_variant(const std::string& name)const {\n    if(a.gsq_packed)return name=="output.weight"&&!a.mini?6:0;')
    t=replace(t,'  bool packed_weight(const std::string& name)const {','  bool packed_weight(const std::string& name)const {\n    if(a.gsq_packed)return false;')
    t=replace(t,'  bool p90_expert_weight(const std::string&name)const {','  bool p90_expert_weight(const std::string&name)const {\n    if(a.gsq_packed)return false;')
    t=replace(t,'  bool p90_hc_weight(const std::string&name)const {','  bool p90_hc_weight(const std::string&name)const {\n    if(a.gsq_packed)return false;')
    t=replace(t,'    auto &t = w.directory.at(name);\n    require(t.component != "embedding"', '''    if(a.gsq_packed&&(name!="output.weight"||a.mini)){gsq_load(c,name);return;}
    auto &t = w.directory.at(name);
    require(t.component != "embedding"''')
    t=replace(t,'const bool planes=!packed&&p49b_weight(w,a,p,name);','const bool planes=!a.gsq_packed&&!packed&&p49b_weight(w,a,p,name);')
    t=replace(t,'  void linear(const flash::Launch& l) {','  void linear(const flash::Launch& l) {\n    if(a.gsq_packed){gsq_linear(l);return;}')
    t=replace(t,'s.grids[s.nw] = flash::grid_type(t.grid);','s.grids[s.nw] = a.gsq_packed&&gsq_control(name)?iq3::Type::F32:flash::grid_type(t.grid);')
    t=replace(t,'auto submit=!a.mini&&a.memory=="resident"?sealed_selection.site(s):packet18::submit_parallel;','auto submit=!a.gsq_packed&&!a.mini&&a.memory=="resident"?sealed_selection.site(s):packet18::submit_parallel;')
    t=replace(t,'if(other_fused_site(l))','if(!a.gsq_packed&&other_fused_site(l))')
    t=replace(t,'if(fused_hc(l))','if(!a.gsq_packed&&fused_hc(l))')
    # Retain original MoE weighting/BF16 boundary; only selected epilogues disabled.
    t=replace(t,'iq3::element(type, row.data(), k)','gsq::element(unsigned(type),row,t.shape.back(),k)')
    t=replace(t,'if(a.memory=="resident")w->warm_lookups();','if(a.memory=="resident"&&!a.gsq_packed)w->warm_lookups();')
    # Helpers are inserted after all actual runtime definitions/includes, before Options.
    pos=t.index('struct Options {')
    additions='\n#define GSQN_RUNTIME_HEADERS_PROVIDED\n#include "'+str(OUT/'additive/packed.hpp')+'"\n#include "'+str(OUT/'additive/upload.hpp')+'"\n#include "'+str(OUT/'additive/generic_host.hpp')+'"\n#include "'+str(OUT/'additive/admission.hpp')+'"\n'
    t=t[:pos]+additions+t[pos:]
    anchor='  unsigned variant(const flash::Launch& l,size_t projection=0)const'
    t=replace(t,anchor,'#include "'+str(OUT/'additive/generic_engine.hpp')+'"\n'+anchor)
    return t

def prepare():
    if OUT.exists():raise FileExistsError('exclusive private output exists; preserve before regeneration')
    binding=json.loads(BIND.read_text()); source_pins={str(BIND.relative_to(R)):sha(BIND)}; mapping={}
    for name,want in binding['sources'].items():
        if not name.startswith('diet-native/') or not name.endswith(('.hpp','.cpp','.h')):continue
        source=P195/name
        if sha(source)!=want:raise ValueError('P195 source changed '+name)
        if '/native-base/' in name:original=R/name.split('/native-base/',1)[1]
        elif '/native-src/' in name:original=OLD/'v5/native-src'/name.split('/native-src/',1)[1]
        elif '/native/' in name:original=OLD/'v5/native'/name.split('/native/',1)[1]
        else:continue
        mapping[original]=source
        if '/native-base/' in name:mapping[OLD/'build/checked'/original.relative_to(R)]=source
    # One canonical destination per authenticated snapshot source, even when
    # both checked and original include spellings name it.
    destinations={source:OUT/'source'/source.relative_to(P195) for source in set(mapping.values())}
    external={}; originals={}; generated={}; patches=[]
    loader=module(L/'loader/prepare_overlay.py','gsq_loader_transform')
    source_pins[str((L/'loader/prepare_overlay.py').relative_to(R))]=sha(L/'loader/prepare_overlay.py')
    seen=set()
    def visit(original):
        original=original.resolve();source=mapping.get(original,original)
        if not source.is_file():raise FileNotFoundError(str(original))
        target=destinations.get(source)
        if target is None:
            if not source.is_relative_to(R):raise ValueError('unadmitted quoted include '+str(source))
            target=OUT/'external'/source.relative_to(R);destinations[source]=target;external[str(source.relative_to(R))]=sha(source)
        if source in seen:return target
        seen.add(source);source_pins[str(source.relative_to(R))]=sha(source)
        text=source.read_text();originals[target]=text
        def inc(m):
            included=Path(m.group(1));included=included if included.is_absolute() else original.parent/included
            return '#include "'+str(visit(included))+'"'
        updated=re.sub(r'^#include "([^"\n]+)"',inc,text,flags=re.M)
        if '/packet2/loader/' in str(source):updated=loader.transform(source.name,updated)
        if str(source).endswith('/packet2/kernels/math.hpp'):
            updated=replace(updated,'Q3_K=11,Q6_K=14,','Q3_K=11,Q4_K=12,Q5_K=13,Q6_K=14,')
            updated=replace(updated,'IQ2_S=22,BF16=30','IQ2_S=22,IQ4_XS=23,BF16=30,Q2_0=42')
            updated=replace(updated,'case Type::Q6_K:return {256,210};','case Type::Q4_K:return {256,144};case Type::Q5_K:return {256,176};case Type::IQ4_XS:return {256,136};case Type::Q2_0:return {64,18};\n    case Type::Q6_K:return {256,210};')
        if str(source).endswith('/packet3/model/directory.hpp'):
            extra=('F16','IQ3_XXS','Q4_K','Q5_K','IQ4_XS','Q2_0')
            updated=updated.replace('  default:\n',''.join('  case Type::'+n+':return "'+n+'";\n' for n in extra)+'  default:\n',1)
            updated=replace(updated,'Type::IQ3_S, Type::IQ4_NL})','Type::IQ3_S, Type::IQ4_NL, '+', '.join('Type::'+n for n in extra)+'})')
        if source==P195/'diet-native/native-src/main.cpp':updated=transform_main(updated)
        if source==P195/'diet-native/native-src/mtp.hpp':
            updated=replace(updated,'head_candidate=packet26::dispatch.gemv_for(head->label);','head_candidate=e.a.gsq_packed?"p33.dense.segment":packet26::dispatch.gemv_for(head->label);')
            updated=replace(updated,'return p83::rows(p.g.vocab,e.a.mini,e.sealed_selection.draft.at("head_prefix"));','return e.a.gsq_packed?p.g.vocab:p83::rows(p.g.vocab,e.a.mini,e.sealed_selection.draft.at("head_prefix"));')
            # Draft shares the new token embedding via the same bounded row decoder.
            updated=updated.replace('iq3::element(type,raw.data(),k)','gsq::element(unsigned(type),raw,p.g.h,k)')
        target.parent.mkdir(parents=True,exist_ok=True);target.write_text(updated);generated[str(target.relative_to(R))]=sha(target)
        if updated!=text:patches.extend(difflib.unified_diff(text.splitlines(True),updated.splitlines(True),fromfile=str(source.relative_to(R)),tofile=str(target.relative_to(R))))
        return target
    entry=visit(OLD/'v5/native-src/entry-main.cpp')
    # Materialize actual source TUs, not just the entry's headers, for later
    # reviewed rebuilds; no compiler or model is invoked here.
    for name in ('packet2/loader/gguf.cpp','packet194-expert-diet-engine/performance.cpp','packet194-expert-diet-engine/runtime_kernels.cpp','packet194-expert-diet-engine/adapter.cpp','packet6-kopt/kernels.cpp'):
        visit(S/name)
    add=OUT/'additive';add.mkdir(parents=True,exist_ok=True)
    for source in (P/'generic_engine.hpp',P/'generic_host.hpp',L/'native-formats/packed.hpp',L/'native-formats/device_formats.hpp',L/'controls/upload.hpp'):
        text=source.read_text();source_pins[str(source.relative_to(R))]=sha(source)
        if source.name=='upload.hpp':text=replace(text,'#include "../../stage2/packet2/kernels/math.hpp"','// Consistent private iq3 definitions supplied by Engine.')
        target=add/source.name;target.write_text(text);generated[str(target.relative_to(R))]=sha(target)
    manifest=json.loads((L/'controls/manifest.json').read_text())
    for source in (L/'controls/manifest.json',L/'loader/placement.tsv',L/'loader/shard-auth.tsv',L/'loader/inputs.json'):source_pins[str(source.relative_to(R))]=sha(source)
    controls=',\n'.join(json.dumps(x['name']) for x in manifest['rows'])
    placement=L/'loader/placement.tsv';auth=L/'loader/shard-auth.tsv'
    # Exact paths + complete bounded file hashes; the expected tensor list is
    # never inferred from untrusted candidate GGUF headers or descriptors.
    header='''#pragma once
#include <set>
namespace gsq_integration {
inline const std::set<std::string> control_names={CONTROLS};
inline const fs::path placement_path=PLACEMENT;
inline void verify_file(const fs::path&p,const fs::path&expected,const char*digest){
 require(p==expected,"GSQ fixed admission path");std::ifstream in(p,std::ios::binary);require(bool(in),"GSQ admission open");
 std::vector<uint8_t>bytes;char block[4096];while(in){in.read(block,sizeof block);bytes.insert(bytes.end(),block,block+in.gcount());require(bytes.size()<=2*1024*1024,"GSQ admission size");}
 require(in.eof()&&hash(bytes)==digest,"GSQ admission SHA256");
}
inline void verify_admission(const fs::path&plan,const fs::path&auth,const fs::path&model){
 verify_file(plan,placement_path,PLACEMENT_HASH);verify_file(auth,AUTH,AUTH_HASH);
 require(!model.empty(),"GSQ model root required");
}
}
'''.replace('CONTROLS',controls).replace('PLACEMENT_HASH',json.dumps(sha(placement))).replace('AUTH_HASH',json.dumps(sha(auth))).replace('PLACEMENT',json.dumps(str(placement))).replace('AUTH',json.dumps(str(auth)))
    (add/'admission.hpp').write_text(header);generated[str((add/'admission.hpp').relative_to(R))]=sha(add/'admission.hpp')
    # Reject escaped physical includes. #line labels are historical only.
    for name in generated:
        for inc in re.findall(r'^#include "([^"\n]+)"',(R/name).read_text(),re.M):
            dest=Path(inc) if Path(inc).is_absolute() else (R/name).parent/inc
            if not dest.resolve().is_relative_to(OUT):raise ValueError('escaped include '+inc)
            if not dest.is_file():raise FileNotFoundError(str(dest))
    (P/'overlay.patch').write_text(''.join(patches))
    receipt={'schema':'ownrt.gsq.native-integration-preparation.v1','source_sha256':source_pins,'private_sha256':generated,'additional_source_sha256':external,'entry':str(entry),'compiled':False,'device_executed':False,'native_admitted':False,'head':'full-expanded-Q6-only','source_mode':'explicit --gsq-packed; unfused Builder; packed weights','patch_sha256':sha(P/'overlay.patch')}
    (P/'preparation.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({'files':len(generated),'entry':str(entry),'compiled':False}))
if __name__=='__main__':prepare()
