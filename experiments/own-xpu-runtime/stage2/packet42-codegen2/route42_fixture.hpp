#pragma once
#include "route42.hpp"
#include <fstream>
#include <filesystem>
#include <cstring>
#include <set>
namespace route42fixture {using namespace integrated;
struct Buffer {Scalar type;size_t n;std::vector<uint8_t> data;};
struct Site {Spec spec;std::vector<int> ids;};
struct Case {
 Geometry g;std::vector<Buffer> buffers;std::vector<Site> sites,new_sites;std::set<int> outputs;int error,position,active,rope;bool rank=false;int rank_ids=-1,rank_prob=-1,rank_gate=-1,rank_down=-1;
 Case(){g.context=128;g.budget=2048;error=add(1,Scalar::u32,0,0);position=add(1,Scalar::u32,0,0);active=add(1,Scalar::u32,0,0);*reinterpret_cast<uint32_t*>(buffers[active].data.data())=1;
  std::ifstream in(std::filesystem::path("/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet29-merged/rope.bf16"),std::ios::binary);Buffer b{Scalar::bf16,262144,{}};b.data.assign(std::istreambuf_iterator<char>(in),{});if(b.data.size()!=b.n*2)throw std::runtime_error("adapter fixture RoPE bytes");rope=buffers.size();buffers.push_back(std::move(b));}
 int add(size_t n,Scalar type=Scalar::bf16,float base=0,float scale=0.03125f){Buffer b{type,n,std::vector<uint8_t>(n*flash::scalar_bytes(type))};View view{b.data.data(),n,type};unsigned salt=buffers.size();for(size_t i=0;i<n;++i)view.put(i,base+scale*float(int((i*13+salt*7)%31)-15));int id=buffers.size();buffers.push_back(std::move(b));return id;}
 Site site(Op op,std::vector<int> inputs,std::vector<int> outs,std::vector<int> weights={},std::initializer_list<int> shape={}){Site r;r.spec.g=g;r.spec.packed_heads=true;r.spec.op=op;r.spec.ni=inputs.size();r.spec.no=outs.size();r.spec.nw=weights.size();r.ids=inputs;r.ids.insert(r.ids.end(),outs.begin(),outs.end());r.ids.insert(r.ids.end(),weights.begin(),weights.end());unsigned j=0;for(auto id:r.ids){r.spec.sizes[j]=buffers[id].n;r.spec.types[j++]=buffers[id].type;}j=0;for(auto id:weights){r.spec.grids[j]=buffers[id].type==Scalar::f32?iq3::Type::F32:iq3::Type::BF16;r.spec.weight_elements[j++]=buffers[id].n;}j=0;for(int v:shape)r.spec.site.shape[j++]=v;outputs.insert(outs.begin(),outs.end());return r;}
};
Case make_case(unsigned kind){Case c;auto add=[&](size_t n,Scalar type=Scalar::bf16,float base=0,float scale=0.03125f){return c.add(n,type,base,scale);};
 if(kind==0){int streams=add(10240),branch=add(2560),inject=add(4),combined=add(10240,Scalar::bf16,0,0),normed=add(10240,Scalar::bf16,0,0),gain=add(10240,Scalar::f32,1),gates=add(10240),mix=add(2560,Scalar::bf16,0,0);
  c.sites={c.site(Op::hc_combine,{streams,branch,inject},{combined},{},{4,2560}),c.site(Op::norm,{combined},{normed},{gain},{4,2560}),c.site(Op::hc_mix,{normed,gates},{mix},{},{4,2560})};
 }else if(kind==1){int input=add(10240),hist=add(30720),convw=add(40960,Scalar::f32,0,0.01f),qkv=add(10240,Scalar::bf16,0,0),a=add(48),b=add(48),decay=add(48,Scalar::f32,-1,0.01f),dt=add(48,Scalar::f32,0,0.01f),state=add(48*128*128),y=add(6144,Scalar::bf16,0,0),gate=add(6144),gain=add(128,Scalar::f32,1),out=add(6144,Scalar::bf16,0,0);
  auto conv=c.site(Op::conv,{input,hist},{qkv,hist},{convw},{10240});conv.spec.site.parameter=1;
  c.sites={conv,c.site(Op::gdn,{qkv,a,b,state},{y,state},{decay,dt},{16,48,128}),c.site(Op::gdn_norm_gate,{y,gate},{out},{gain},{48,128})};
 }else if(kind==2){int qgate=add(12288),k=add(512),iq=add(512),qw=add(256,Scalar::f32,1),kw=add(256,Scalar::f32,1),iw=add(128,Scalar::f32,1),qout=add(6144,Scalar::bf16,0,0),gate=add(6144,Scalar::bf16,0,0),kout=add(512,Scalar::bf16,0,0),iout=add(512,Scalar::bf16,0,0),value=add(512),raw=add(128),pw=add(128,Scalar::f32,1),kc=add(128*512),vc=add(128*512),rc=add(128*128),pool=add(32*128,Scalar::bf16,0,0),indices=add(2051,Scalar::i32,-1,0),out=add(6144,Scalar::bf16,0,0);
  c.sites={c.site(Op::qsa_prepare,{qgate,k,iq},{qout,gate,kout,iout},{qw,kw,iw}),c.site(Op::qsa_append_pool,{kout,value,raw},{kc,vc,rc,pool},{pw}),c.site(Op::qsa_select,{iout,pool},{indices}),c.site(Op::qsa_attention,{qout,gate,kc,vc,indices},{out})};
 }else{c.rank=true;int logits=add(512);c.rank_ids=add(10,Scalar::i32,0,0);c.rank_prob=add(10,Scalar::f32,0,0);c.rank_gate=add(30,Scalar::i32,0,0);c.rank_down=add(30,Scalar::i32,0,0);int input=add(2560),repeated=add(25600,Scalar::bf16,0,0);c.sites={c.site(Op::route,{logits},{c.rank_ids,c.rank_prob},{},{512,10}),c.site(Op::expert_gather,{c.rank_ids,input},{c.rank_gate,c.rank_down,repeated})};c.outputs.erase(repeated);}
 c.outputs.insert(c.error);return c;
}
Case make_flat(bool broadcast){Case c;int a=c.add(broadcast?2560:10240),out=c.add(10240,Scalar::bf16,0,0);
 if(broadcast){auto site=c.site(Op::norm,{a},{out});site.spec.special=Special::broadcast;c.sites={site};}
 else{int b=c.add(10240),d=c.add(10240);c.sites={c.site(Op::ple_add,{a,b,d},{out})};}
 c.outputs.insert(c.error);return c;}
// These fixtures exercise exactly the plan-time folded producer ABI, rather
// than timing an equivalent ng fixture under the production class name.
void fold_pair(Case& c){
 if(c.sites.size()<2)throw std::runtime_error("folded fixture requires two sites");
 const auto first=c.sites[0],second=c.sites[1];
 if(first.spec.op==Op::hc_combine&&second.spec.op==Op::norm){
  Site folded=c.site(Op::hc_combine,
   {first.ids[0],first.ids[1],first.ids[2]},
   {first.ids[first.spec.ni],second.ids[second.spec.ni]},
   {second.ids[second.spec.ni+second.spec.no]},
   {first.spec.site.shape[0],first.spec.site.shape[1]});
  folded.spec.fused_combine_norm=true;
  folded.spec.site.parameter=second.spec.site.parameter;
  c.new_sites={folded};
 }else if(first.spec.op==Op::route&&second.spec.op==Op::expert_gather){
  Site folded=c.site(Op::route,{first.ids[0]},
   {first.ids[first.spec.ni],first.ids[first.spec.ni+1],second.ids[second.spec.ni],second.ids[second.spec.ni+1]},
   {},{first.spec.site.shape[0],first.spec.site.shape[1]});
  c.new_sites={folded};
  // The removed repeated row is no longer a model output or binding. Its
  // consumer reads the original input row; model oracle gates cover that path.
  c.outputs.erase(second.ids[second.spec.ni+2]);
 }else throw std::runtime_error("unsupported folded fixture pair");
 for(size_t i=2;i<c.sites.size();++i)c.new_sites.push_back(c.sites[i]);
}

}
