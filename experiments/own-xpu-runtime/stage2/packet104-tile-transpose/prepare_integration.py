"""Prepare selected load/dispatch views; expensive gates still require micro.

Frozen packet100 source bytes are verified, copied, then patched locally.
No source seal or runnable screen is created by this script.
"""
import json,copy
from build_engine import P,ROOT,limits,sha,save
BASE=P.parent/'packet100-down-locality'
def main():
 limits();origin=json.loads((P/'source-origin.json').read_text())
 def source(name):
  path=BASE/name;assert sha(path)==origin[str(path.relative_to(ROOT))],name
  return path.read_text()
 def rep(s,a,b):
  assert a in s,a
  return s.replace(a,b)
 s=source('p49d_expert_submit.cpp').replace('#include "p100_down.hpp"','#include "p100_down.hpp"\n#include "p104iq2.hpp"\n#include "p104iq2hc.hpp"')
 s=rep(s,'using Candidate=std::conditional_t<(Arm==20','using PriorCandidate=std::conditional_t<(Arm==20')
 s=rep(s,'OldCandidate>>;Candidate k;', 'OldCandidate>>;using Candidate=std::conditional_t<Arm==22,p104iq2::Kernel<T,K,64,false,true>,std::conditional_t<Arm==23,p104iq2hc::Kernel<T,K,64,false,true>,PriorCandidate>>;Candidate k;')
 s=s.replace('Arm==10||Arm==12||','Arm==10||Arm==12||Arm==23||')
 s=rep(s,'if constexpr(Arm==21){','if constexpr(Arm==21||Arm==22||Arm==23){')
 s=rep(s,'uintptr_t(p[0])%16','uintptr_t(p[0])%16||uintptr_t(p[1])%16')
 s=rep(s,' choice=p100::gate_choice(choice);',' choice=p100::gate_choice(choice);\n if(choice=="gate-tile16")return chosen_expert<22>(d,m,kind,b);\n if(choice=="gate-halfcache-tile16")return chosen_expert<23>(d,m,kind,b);')
 (P/'p49d_expert_submit.cpp').write_text(s)
 s=source('p49d_submit.cpp').replace('#include "p49d_small.hpp"','#include "p49d_small.hpp"\n#include "p104_small.hpp"')
 s=rep(s,'choice=="dense-packed"||choice=="combined"','choice=="dense-packed"||choice=="combined"||choice=="small-q6-tile16"||choice=="small-router-tile16"')
 s=rep(s,'std::span<const unsigned>variants){','std::span<const unsigned>variants,bool tileq6,bool tilerouter){')
 s=rep(s,' p49dvirtual::SmallKernel<4>k;std::array<Allocation,12>ids{};',''' auto issue=[&]<class K>(K k){std::array<Allocation,12>ids{};
 if(tileq6||tilerouter)for(unsigned i=0;i<3;++i)if((tileq6&&(i==1||i==2))||(tilerouter&&i==0)){
   if(ms[i].rows%16||uintptr_t(d.arena.row(ms[i].w).pointer)%16)throw std::invalid_argument("p104 small tile alignment/rows");
 }
''')
 s=rep(s,'auto e=d.compute(k,ids,{});return {e,e,1};\n}', '''auto e=d.compute(k,ids,{});return Launch{e,e,1};};
 if(tileq6&&tilerouter)return issue(p104small::SmallKernel<4,true,true>{});
 if(tileq6)return issue(p104small::SmallKernel<4,true,false>{});
 if(tilerouter)return issue(p104small::SmallKernel<4,false,true>{});
 return issue(p49dvirtual::SmallKernel<4>{});
}''')
 s=rep(s,'choice=="production"||choice=="wide"','choice=="production"||choice=="wide"||choice=="wide-tile16"')
 s=rep(s,'  choice=p100::gate_choice(choice);','  choice=p100::gate_choice(choice);\n  if(choice=="gate-tile16"||choice=="gate-halfcache-tile16")return production;')
 (P/'p49d_submit.cpp').write_text(s)
 s=source('p49d_submit.hpp');s=rep(s,'std::span<const unsigned>);','std::span<const unsigned>,bool tileq6=false,bool tilerouter=false);');(P/'p49d_submit.hpp').write_text(s)
 s=source('p59c_select.hpp')
 s=rep(s,'(value!="production"&&value!="packet59")','(value!="production"&&value!="packet59"&&!(value=="tile16"&&(key=="gate_up"||key=="down"||key=="shared_gate"||key=="shared_up"||key=="shared_down")))')
 (P/'p59c_select.hpp').write_text(s)
 s=source('main.cpp').replace('#include "p100_down.hpp"','#include "p100_down.hpp"\n#include "p104_engine.hpp"')
 s=rep(s,'  bool packed_weight(const std::string& name)const {','''  bool small_tiled_group(const SmallGroup&group)const {
    if(a.mini||a.memory!="resident"||group.name!="small.ffn.q6")return false;
    const auto&choice=sealed_selection.choices.at("packed_dense");
    if(choice!="small-q6-tile16"&&choice!="small-router-tile16")return false;
    for(unsigned j=0;j<3;++j)if((choice=="small-router-tile16"&&j==0)||(choice=="small-q6-tile16"&&j!=0)){
      const auto&name=group.members[j]->weights[0];
      for(const auto&site:p.launches)if(std::find(site.weights.begin(),site.weights.end(),name)!=site.weights.end()&&std::find(group.members.begin(),group.members.end(),&site)==group.members.end())return false;
    }return true;
  }
  bool small_tiled_weight(const std::string&name)const {
    const auto&choice=sealed_selection.choices.at("packed_dense");
    for(const auto&[first,group]:small_groups)if(small_tiled_group(group))for(unsigned j=0;j<3;++j)
      if(((choice=="small-router-tile16"&&j==0)||(choice=="small-q6-tile16"&&j!=0))&&group.members[j]->weights[0]==name)return true;
    return false;
  }
  bool packed_weight(const std::string& name)const {''')
 expr='(p100::gate_choice(sealed_selection.choices.at("experts"))=="exp-halfcache"||p100::gate_choice(sealed_selection.choices.at("experts")).ends_with("+halfcache"))'
 s=rep(s,expr,'p104::gate_cached(sealed_selection.choices.at("experts"))')
 s=rep(s,expr.replace('sealed_selection','selected'),'p104::gate_cached(selected.choices.at("experts"))')
 s=rep(s,'    if(planes){','''    if(planes&&p104::gate_tiled(sealed_selection.choices.at("experts"))&&type==iq3::Type::IQ2_S){
      require(t.shape.size()==3&&t.shape.back()==2560&&t.shape[1]==640,"p104 IQ2 tile shape");
      constexpr size_t raw_stride=820;const size_t stride=halfcache?840:820,total=t.bytes/raw_stride,chunk=16*256;
      for(size_t row=0;row<total;row+=chunk){guard();size_t n=std::min(chunk,total-row);auto raw=w.read(name,row*raw_stride,n*raw_stride);std::vector<uint8_t> packed(n*stride);
        for(size_t r=0;r<n;++r){if(halfcache)p90::expert_repack(2560,raw.data()+r*raw_stride,packed.data()+r*stride);else p49bgemv::repack_row(type,2560,raw.data()+r*raw_stride,packed.data()+r*stride);}
        auto tiled=halfcache?p104::iq2<true>(packed.data(),n):p104::iq2<false>(packed.data(),n);upload(c,id,row*stride,tiled.data(),tiled.size());
      }return;
    }
    if(planes){''')
 s=rep(s,'      for(size_t row=0;row<size_t(t.shape[0]);row+=rows_per){','''      const bool hctile=sealed_selection.choices.at("hc_gate")=="wide-tile16"&&name.starts_with("blk.")&&(name.ends_with(".hc_attn_up.weight")||name.ends_with(".hc_ffn_up.weight"));
      if(hctile){require(type==iq3::Type::Q8_0&&t.shape[0]==10240&&t.shape[1]==320&&er==380,"p104 HC layout shape");rows_per=std::max(size_t(16),rows_per/16*16);}
      const bool q6tile=sealed_selection.choices.at("packed_dense")=="small-q6-tile16"&&small_tiled_weight(name);
      if(q6tile){require(a.memory=="resident"&&type==iq3::Type::Q6_K&&t.shape[0]==640&&t.shape[1]==2560&&er==3380,"p104 small Q6 layout shape");rows_per=std::max(size_t(16),rows_per/16*16);}
      for(size_t row=0;row<size_t(t.shape[0]);row+=rows_per){''')
 s=rep(s,'        upload(c,id,row*er,expanded.data(),expanded.size());','        if(hctile)expanded=p104::hc(expanded.data(),nr);\n        if(q6tile)expanded=p104::small_q6(expanded.data(),nr);\n        upload(c,id,row*er,expanded.data(),expanded.size());')
 s=rep(s,'    if(!packed&&arithmetic::is_expanded(v)) {','''    if(sealed_selection.choices.at("packed_dense")=="small-router-tile16"&&small_tiled_weight(name)){
      require(a.memory=="resident"&&type==iq3::Type::F32&&t.shape.size()==2&&t.shape[0]==512&&t.shape[1]==2560,"p104 router shape");
      for(size_t row=0;row<512;row+=128){guard();auto raw=w.read(name,row*10240,128*10240);auto tiled=p104::small_router(raw.data(),128);upload(c,id,row*10240,tiled.data(),tiled.size());}return;
    }
    if(!packed&&arithmetic::is_expanded(v)) {''')
 s=rep(s,'p49d::small(dev(c),name,members,variants)','p49d::small(dev(c),name,members,variants,small_tiled_group(grouped->second)&&sealed_selection.choices.at("packed_dense")=="small-q6-tile16",small_tiled_group(grouped->second)&&sealed_selection.choices.at("packed_dense")=="small-router-tile16")')
 s=rep(s,'sealed_selection.choices.at("hc_norm")=="consumer"),stage!=0);','sealed_selection.choices.at("hc_norm")=="consumer",sealed_selection.choices.at("hc_gate")=="wide-tile16"),stage!=0);')
 (P/'main.cpp').write_text(s)
 s=source('p60_submit.hpp');s=rep(s,'bool fused=false);','bool fused=false,bool tiled=false);');(P/'p60_submit.hpp').write_text(s)
 s=source('p60_submit.cpp').replace('#include "p73_hc.hpp"','#include "p73_hc.hpp"\n#include "p104_hc.hpp"')
 s=s.replace('bool Fused=false>','bool Fused=false,bool Tiled=false>')
 s=rep(s,'Kernel<Stage,Wide,Subgroup,Cached,Fused>','Kernel<Stage,Wide,Subgroup,Cached,Fused,Tiled>')
 s=rep(s,'if constexpr(Stage==2){if constexpr(Cached)p90hc::host(b);','if constexpr(Stage==2){if constexpr(Tiled)p104hc::host(b);else if constexpr(Cached)p90hc::host(b);')
 s=rep(s,'if constexpr(Stage==2){if constexpr(Cached)return p90hc::device(q,b,deps);','if constexpr(Stage==2){if constexpr(Tiled)return p104hc::device(q,b,deps);else if constexpr(Cached)return p90hc::device(q,b,deps);')
 s=rep(s,'bool cached,bool fused) {','bool cached,bool fused,bool tiled) {\n if(tiled&&cached)throw std::invalid_argument("p104 incompatible HC layouts");')
 s=rep(s,'case 2:if(cached)','case 2:if(tiled)return issue<2,false,false,false,false,true>(d,ids,capacity);if(cached)')
 (P/'p60_submit.cpp').write_text(s)
 s=source('mtp.hpp').replace('#include "p59_draft.hpp"','#include "p59_draft.hpp"\n#include "p104_draft_submit.hpp"')
 anchor=' bool selected(const std::string& key)const'
 at=s.index(anchor)
 s=s[:at]+''' bool tiled_weight(const std::string&name)const{
  static const std::map<std::string,std::string>keys{{"blk.0.ffn_gate_exps.weight","gate_up"},{"blk.0.ffn_up_exps.weight","gate_up"},{"blk.0.ffn_down_exps.weight","down"},{"blk.0.ffn_gate_shexp.weight","shared_gate"},{"blk.0.ffn_up_shexp.weight","shared_up"},{"blk.0.ffn_down_shexp.weight","shared_down"}};
  auto i=keys.find(name);return i!=keys.end()&&e.sealed_selection.draft.at(i->second)=="tile16";
 }
 std::vector<uint8_t>tile_bytes(const std::vector<uint8_t>&raw,unsigned rows,unsigned cols,bool int8){
  require(!e.a.mini&&rows%16==0,"p104 full draft layout required");
  if(cols==2560)return int8?p104::draft<2560,true>(raw.data(),rows):p104::draft<2560,false>(raw.data(),rows);
  require(cols==640,"p104 draft columns");return int8?p104::draft<640,true>(raw.data(),rows):p104::draft<640,false>(raw.data(),rows);
 }
'''+s[at:]
 s=rep(s,'e.upload(0,w.id,size_t(expert)*rows*rb,raw.data(),raw.size());','if(tiled_weight(name))raw=tile_bytes(raw,rows,cols,w.int8);e.upload(0,w.id,size_t(expert)*rows*rb,raw.data(),raw.size());')
 s=rep(s,'   e.upload(0,w.id,0,raw.data(),raw.size());','   if(tiled_weight(name))raw=tile_bytes(raw,rows,cols,w.int8);e.upload(0,w.id,0,raw.data(),raw.size());')
 s=rep(s,'  if(!e.a.mini&&l.op=="gemv"&&candidate=="p33.dense.segment") {','  if(!tiled_weight(l.weights[0])&&!e.a.mini&&l.op=="gemv"&&candidate=="p33.dense.segment") {')
 s=rep(s,'  e.finish(0,mtp36::linear(e.dev(0),a),true);','  e.finish(0,tiled_weight(l.weights[0])?p104draftsubmit::linear(e.dev(0),a):mtp36::linear(e.dev(0),a),true);')
 (P/'mtp.hpp').write_text(s)
 baseline=json.loads((P/'baseline-selection.json').read_text())
 from micro_gate import CANDIDATES
 views={};draft_keys={'draft-gate-tile16':['gate_up'],'draft-down-tile16':['down'],'shared-gate-up-tile16':['shared_gate','shared_up'],'shared-down-tile16':['shared_down']}
 for name in ('control',*CANDIDATES):
  v=copy.deepcopy(baseline)
  if name=='target-gate-tile16':v['choices']['experts']='gate-tile16+down-tile16'
  if name=='target-gate-halfcache-tile16':v['choices']['experts']='gate-halfcache-tile16+down-tile16'
  if name=='hc-gate-tile16':v['choices']['hc_gate']='wide-tile16'
  if name=='target-shared-q6-tile16':v['choices']['packed_dense']='small-q6-tile16'
  if name=='target-router-tile16':v['choices']['packed_dense']='small-router-tile16'
  for key in draft_keys.get(name,[]):v['draft'][key]='tile16'
  path=P/'views'/name/'selection.json';save(path,v)
  # KD is a draft-only host reference. Keep the target resident guard intact.
  ref=copy.deepcopy(v);ref['choices']['experts']='wide64';ref['choices']['hc_gate']='wide';ref['choices']['packed_dense']='production'
  save(path.with_name('draft-host-reference.json'),ref)
  views[name]=dict(selection=str(path.relative_to(P)),sha256=sha(path),model_gates_passed=False,screen_admitted=False)
 half=copy.deepcopy(baseline);half['choices']['experts']='exp-halfcache+down-tile16';save(P/'views/half-cache-control/selection.json',half)
 save(P/'integration-plan.json',dict(schema='packet104.integration-plan.v1',passed=False,prepared=True,compiled=False,device_executed=False,views=views,half_cache_control='views/half-cache-control/selection.json',required_arithmetic='iq3-p49-split32-v1',required_startup_windows=['K0','K1a','K1b','K2','W0p','KD','W2m','WS','WSs','WS128x','WS128'],next='micro qualification before compiling/byte gates/full startup/VRAM/seals/B grid/A confirm'))
 print('down-tile16 composition sources and views prepared; no gates or screens admitted')
if __name__=='__main__':main()
