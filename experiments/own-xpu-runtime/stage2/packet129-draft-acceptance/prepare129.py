"""One-shot source derivation from frozen lab sources; never runs a device."""
from pathlib import Path
import json, shutil
P=Path(__file__).resolve().parent
BASE=P.with_name('packet124c-record-bundle')

def change(text,old,new):
    assert old in text,old
    return text.replace(old,new)

def main():
    # The same eight-values-per-lane reduction as the production INT8 experts.
    text=(BASE/'mtp_kernels.cpp').read_text().split('template<unsigned Width,int Stage>')[0]
    text='#pragma once\n'+text+'}\n'
    text=text.replace('namespace mtp36 {','namespace p129 {\nusing Linear=mtp36::Linear;')
    start=text.index('template<unsigned K,bool Int8> inline float lane')
    end=text.index('template<unsigned K,bool Int8,bool Pair>',start)
    text=text[:start]+'''inline float decode(uint8_t b) {
 unsigned e=(b>>3)&15,m=b&7;
 float value=e?iq3::bits_float(((e+120)<<23)|(m<<20)):float(m)*(1.f/512.f);
 return b&128?-value:value;
}
template<unsigned K,bool Int8> inline float lane(const uint8_t* w,const uint16_t* x,unsigned l){
 if constexpr(!Int8)return p28::dense_lane<iq3::Type::BF16,K>(w,x,0,K,l);
 else {float sum=0;for(unsigned tile=l*8;tile<K;tile+=256)for(unsigned k=tile;k<std::min(tile+8,K);++k){
  const auto* s=w+K+(k/128)*2;
  float scale=iq3::bits_float((uint32_t(s[0])|(uint32_t(s[1])<<8))<<16);
  float value=decode(w[k])*scale;
  float product=value*iq3::bits_float(uint32_t(x[k])<<16);sum=sum+product;
 }return sum;}
}
'''+text[end:]
    text=text.replace('K+4*((K+15)/16)','K+2*((K+127)/128)').replace('a.columns+4*((a.columns+15)/16)','a.columns+2*((a.columns+127)/128)')
    text=text.replace('Launch linear(', 'inline Launch linear(')
    (P/'p129_fp8.hpp').write_text(text)
    text=(BASE/'mtp.hpp').read_text().replace('#include "mtp_kernels.hpp"','#include "mtp_kernels.hpp"\n#include "p129_fp8.hpp"')
    text=change(text,' bool captured=false;', '''
 Allocation shadow_gate{},shadow_up{},shadow_down{};
 std::vector<uint8_t> before_experts;
 std::ofstream shadow_trace;
 bool shadow_enabled()const{return e.a.acceptance_shadow;}
 // Keep original FP8 codes. Repeat each publisher 128x128 BF16 scale per row.
 std::vector<uint8_t> faithful(const std::string& kind,unsigned expert,unsigned rows,unsigned cols){
  auto prefix="mtp.layers.0.mlp.experts."+std::to_string(expert)+"."+kind+"_proj";
  auto raw=store->read(prefix+".weight"),sc=store->read(prefix+".weight_scale_inv");
  require(raw.size()==size_t(rows)*cols&&rows%128==0&&cols%128==0&&sc.size()==size_t(rows/128)*(cols/128)*2,"FP8 shadow shape");
  size_t rb=cols+cols/128*2;std::vector<uint8_t> out(rows*rb);
  for(unsigned row=0;row<rows;++row){
   std::memcpy(out.data()+row*rb,raw.data()+size_t(row)*cols,cols);
   for(unsigned col=0;col<cols;++col)require((raw[size_t(row)*cols+col]&127)!=127,"nonfinite FP8 code");
   auto* scales=sc.data()+size_t(row/128)*(cols/128)*2;
   for(unsigned b=0;b<cols/128;++b){uint16_t bits;std::memcpy(&bits,scales+2*b,2);float value=iq3::bits_float(uint32_t(bits)<<16);require(std::isfinite(value)&&value>=0,"FP8 shadow scale");}
   std::memcpy(out.data()+row*rb+cols,scales,cols/128*2);
  }return out;
 }
 void shadow_matrix(const flash::Launch& l){
  if(e.a.mini){matrix_production(l);return;}
  auto route_bytes=e.readback(0,id(l.inputs[1]),p.g.top*sizeof(iq3::Route));
  std::vector<iq3::Route> routes(p.g.top);std::memcpy(routes.data(),route_bytes.data(),route_bytes.size());
  bool pair=l.op=="expert_gate_up";unsigned rows=l.shape[1],cols=l.shape[2];size_t bytes=size_t(rows)*(cols+cols/128*2);
  for(unsigned slot=0;slot<routes.size();++slot){auto& r=routes[slot];require(iq3::valid_route(r,p.g.experts,rows,rows)&&r.row_begin==0&&r.row_count==rows,"shadow full route required");
   auto raw=faithful(pair?"gate":"down",r.expert_id,rows,cols);e.upload(0,pair?shadow_gate:shadow_down,slot*bytes,raw.data(),raw.size());
   if(pair){raw=faithful("up",r.expert_id,rows,cols);e.upload(0,shadow_up,slot*bytes,raw.data(),raw.size());}r.expert_id=slot;
  }
  e.upload(0,id(l.inputs[1]),0,routes.data(),route_bytes.size());
  mtp36::Linear a;a.w=pair?shadow_gate:shadow_down;a.x=id(l.inputs[0]);a.y=id(l.outputs[0]);a.routes=id(l.inputs[1]);a.status=id(l.outputs[1]);a.rows=rows;a.columns=cols;a.batch=p.g.top;a.experts=p.g.top;a.int8=true;a.paired=pair;
  if(pair){a.peer=shadow_up;a.py=id(l.outputs[2]);a.ps=id(l.outputs[3]);}
  e.finish(0,p129::linear(e.dev(0),a),true);e.drain();
  e.upload(0,id(l.inputs[1]),0,route_bytes.data(),route_bytes.size());
 }
 void shadow_suffix(int confirmed){
  e.drain();require(before_experts.size()==size_t(4*p.g.h)*2,"missing same-input shadow streams");
  std::map<Allocation,std::vector<uint8_t>> saved;
  for(auto allocation:mutable_ids)saved.emplace(allocation,e.readback(0,allocation,e.dev(0).arena.row(allocation).bytes));
  int production=-1,candidate=-1,status=-1;std::memcpy(&production,saved.at(id("next_token")).data(),4);
  e.upload(0,id("streams"),0,before_experts.data(),before_experts.size());
  bool started=false;
  for(const auto& l:p.launches){
   if(l.label=="blk.0.expsgate")started=true;
   if(!started||l.op=="commit")continue;
   e.guard();
   if(l.op=="routed_gemv"||l.op=="expert_gate_up")shadow_matrix(l);else direct(l);
  }
  auto token=e.readback(0,id("next_token"),4),error=e.readback(0,id("error"),4);
  std::memcpy(&candidate,token.data(),4);std::memcpy(&status,error.data(),4);
  require(started&&!status&&candidate>=0&&candidate<p.g.vocab,"invalid shadow result");
  for(auto&[allocation,raw]:saved)e.upload(0,allocation,0,raw.data(),raw.size());
  e.drain();
  for(auto&[allocation,raw]:saved)require(e.readback(0,allocation,raw.size())==raw,"shadow modified production draft state");
  shadow_trace<<"{\\"draft_position\\":"<<position<<",\\"confirmed_token\\":"<<confirmed<<",\\"production\\":"<<production<<",\\"candidate\\":"<<candidate<<",\\"restored_exact\\":true}\\n";shadow_trace.flush();
 }
 bool captured=false;''')
    text=change(text,'  prepare_commands();\n  save(e.a.output/"draft-memory.json"', '''  if(shadow_enabled()){
   shadow_trace.open(e.a.output/"shadow-rows.jsonl");require(bool(shadow_trace),"shadow trace");
   if(!e.a.mini){size_t bytes=size_t(p.g.top)*p.g.mid*(p.g.h+p.g.h/128*2);shadow_gate=alloc("shadow-gate",bytes);shadow_up=alloc("shadow-up",bytes);shadow_down=alloc("shadow-down",size_t(p.g.top)*p.g.h*(p.g.mid+p.g.mid/128*2));
    mutable_ids.erase(shadow_gate);mutable_ids.erase(shadow_up);mutable_ids.erase(shadow_down);}
  }
  prepare_commands();
  save(e.a.output/"draft-memory.json"''')
    text=change(text,'   for(const auto& site:issue_sites){if(!head&&site.head)continue;', '''   size_t site_index=0;
   for(const auto& site:issue_sites){auto index=site_index++;if(!head&&site.head)continue;
    if(shadow_enabled()&&head&&index>=merge_plan.size()&&p.launches[index-merge_plan.size()].label=="blk.0.expsgate")before_experts=e.readback(0,id("streams"),4*p.g.h*2);''')
    text=change(text,'    e.guard();if(e.a.timing=="class")e.set_class("draft."+l.label);direct(l);', '''    if(shadow_enabled()&&head&&l.label=="blk.0.expsgate")before_experts=e.readback(0,id("streams"),4*p.g.h*2);
    e.guard();if(e.a.timing=="class")e.set_class("draft."+l.label);direct(l);''')
    text=change(text,'  if(asynchronous) {','  if(shadow_enabled()&&head)shadow_suffix(confirmed);\n  if(asynchronous) {')
    text=change(text,'  trace.close();trace.open(output/"draft-rows.jsonl");', '  if(shadow_enabled()){shadow_trace.close();shadow_trace.open(output/"shadow-rows.jsonl");require(bool(shadow_trace),"shadow reset trace");before_experts.clear();}\n  trace.close();trace.open(output/"draft-rows.jsonl");')
    (P/'mtp.hpp').write_text(text)
    text=(BASE/'main.cpp').read_text()
    text=change(text,'  int draft_rank=0,target_split=0;', '  bool acceptance_shadow=false;\n  int draft_rank=0,target_split=0;')
    text=change(text,'    else if (k == "--draft-mtp")', '    else if (k == "--acceptance-shadow") a.acceptance_shadow=true;\n    else if (k == "--draft-mtp")')
    text=change(text,'  require(a.draft_rank==0||a.draft_rank==1,', '  require(!a.acceptance_shadow||(a.mtp&&a.draft_rank==1&&(a.mini||a.context==4096)),"shadow requires rank1 MTP and admitted context");\n  require(a.draft_rank==0||a.draft_rank==1,')
    (P/'main.cpp').write_text(text)
    text=(P/'build_engine.py').read_text().replace("packet124b-record-bundle","packet124c-record-bundle").replace('250_000_000','300_000_000')
    (P/'build_engine.py').write_text(text)
    # Reuse unchanged arithmetic objects; bind every dependency in the new receipt.
    shutil.copyfile(BASE/'engine-commands.json',P/'engine-commands.json')
    # Existing arena admission is unchanged. Add actual private shadow banks.
    ledger=json.loads((BASE/'memory-plan.json').read_text());extra=3*10*640*(2560+40)
    for config in ledger['placements']['1']['capacities'].values():
     r=config['ranks'][1]
     for key in ('draft_total_bytes','total_with_mtp_bytes','arena_device_bytes'):r[key]+=extra
     for key in ('free_with_mtp_bytes','arena_headroom_bytes'):r[key]-=extra
    ledger['packet129_shadow_bytes']=extra
    (P/'memory-plan.json').write_text(json.dumps(ledger,indent=2)+'\n')
    (P/'memory_plans.py').write_text('import json\nfrom build_engine import P\ndef plan(v):return json.loads((P/"memory-plan.json").read_text())\n')
    text=(P/'full_shape.py').read_text().replace('a.mtp=true;', 'a.mtp=true;a.acceptance_shadow=true;')
    (P/'full_shape.py').write_text(text)

if __name__=='__main__':main()
