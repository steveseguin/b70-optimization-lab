#pragma once
#include "../packet19-depcheck/depcheck.hpp"
#include "performance.hpp"
#include "kernels.hpp"
namespace depcheck {
inline int position=-1;
inline std::vector<Access> describe_spec(ownrt::Device& d,const integrated::Spec& s,std::span<const ownrt::Allocation> ids,int mode){
 using integrated::Special;using integrated::Op;std::vector<Access> out;
 auto add=[&](int i,bool r,bool w,bool idx=false,size_t off=0,size_t bytes=0){auto& a=d.arena.row(ids[i]);out.push_back({static_cast<char*>(a.pointer)+off,bytes?bytes:a.bytes-off,r,w,idx});};
 int tail=s.ni+s.no+s.nw;
#ifdef DEPCHECK_PACKET18
 if(s.special==Special::normal&&(s.op==Op::qsa_prepare||s.op==Op::qsa_append_pool))add(tail+4,true,false);
#endif
 if(mode==1){add(tail+1,true,false);add(tail+2,true,false,true);add(tail+3,true,false);add(tail+4,false,true);return out;}
 if(mode==2){add(tail+4,true,false,false,8,4);add(tail+1,true,true);return out;}
 add(tail+1,true,true);add(tail+2,true,s.special==Special::commit,true);add(tail+3,true,false);
 if(s.special==Special::begin||s.special==Special::commit)return out;
 for(int i=0;i<s.ni;++i)add(i,true,s.special==Special::ple_hash&&i==1,
  s.special==Special::ple_hash||s.op==Op::expert_gather||(s.op==Op::qsa_attention&&i==4));
 // The scalar interpreter copies every output through its scratch arena.
 // Parallel append kernels write only the current position and completed pool.
 if(mode!=-1&&s.op==Op::qsa_append_pool){
  const auto& g=s.g;const size_t scalar=2; // all KV/raw/pool state is BF16
  for(int i=0;i<3;++i){size_t width=i<2?g.kvh*g.ad:g.id;add(s.ni+i,false,true,false,size_t(position)*width*scalar,width*scalar);}
  if((position+1)%4==0){add(s.ni+2,true,false,false,size_t(position/4)*4*g.id*scalar,3*g.id*scalar);add(s.ni+3,false,true,false,size_t(position/4)*g.id*scalar,g.id*scalar);}
 }else{
  for(int i=0;i<s.no;++i)add(s.ni+i,mode==-1,false);
  for(int i=0;i<s.no;++i)add(s.ni+i,false,true);
 }
 for(int i=0;i<s.nw;++i)add(s.ni+s.no+i,true,false);
 // Interpreter scratch is internally produced/consumed within one submission.
 if(mode==-1)add(tail,false,true);
 return out;
}
inline std::vector<Access> describe_ng(ownrt::Device& d,ng::Shape s,std::span<const ownrt::Allocation> ids){
 std::vector<Access> out;auto n=ng::required_bytes(s);
 auto add=[&](int i,bool r,bool w,bool idx=false,size_t off=0,size_t bytes=0){auto& a=d.arena.row(ids[i]);out.push_back({static_cast<char*>(a.pointer)+off,bytes?bytes:n[i],r,w,idx});};
#ifdef DEPCHECK_PACKET18
 if(ids.size()!=19)throw std::logic_error("packet18 ng binding count");
 add(15,true,true,false,0,4);add(17,true,false,true,0,4);add(18,true,false,false,0,4);
 if(s.op==ng::prepare||s.op==ng::pool)add(16,true,false);
#else
 if(ids.size()!=16)throw std::logic_error("packet16 ng binding count");
 add(15,true,true,true,0,12);
#endif
 auto rw=[&](std::initializer_list<int> r,std::initializer_list<int>w){for(int i:r)add(i,true,false);for(int i:w)add(i,false,true);};
 switch(s.op){
 case ng::norm:rw({0,1},{2});break;
 case ng::activation:rw({0},{2});if(s.extra)add(1,true,false);break;
 case ng::mix:rw({0,1},{2});break;
 case ng::conv:rw({0,1,2},{3,4});break;
 case ng::gdn:rw({0,1,2,3,4,5},{6,7});break;
 case ng::gated_norm:rw({0,1,2},{3});break;
 case ng::moe_combine:rw({0,1,2,3},{4});break;
 case ng::prepare:rw({0,1,2,3,4,5},{6,7,8,9});break;
 case ng::pool:{
  rw({0,1,2},{});
  for(int i:{4,5})add(i,false,true,false,size_t(position)*512*2,size_t(s.tokens)*512*2);
  add(6,false,true,false,size_t(position)*128*2,size_t(s.tokens)*128*2);
  int first=position/4,last=(position+s.tokens)/4;
  if(last>first){add(3,true,false);if(position%4)add(6,true,false,false,size_t(first)*4*128*2,size_t(position%4)*128*2);add(7,false,true,false,size_t(first)*128*2,size_t(last-first)*128*2);}
  break;
 }
 case ng::select:{
  int pools=(position+s.tokens)/4;if(pools){add(0,true,false);add(1,true,false,false,0,size_t(pools)*128*2);}add(2,false,true);break;
 }
 case ng::attention_score:
  rw({0,2},{});add(4,true,false,true);
  for(int h=0;h<24;++h)add(6,false,true,false,h*(s.budget+3)*4,std::min(s.capacity,s.budget+3)*4);break;
 case ng::attention_softmax:case ng::attention_value:{
  add(4,true,false,true);int count=std::min((position+1)/4,s.budget/4)*4+(position+1)%4;
  count=std::max(1,count);
  if(s.op==ng::attention_value)rw({1,3},{5});
  for(int h=0;h<24;++h){if(s.op==ng::attention_softmax){add(6,true,false,false,h*(s.budget+3)*4,count*4);add(7,false,true,false,h*(s.budget+3)*4,count*4);}else add(7,true,false,false,h*(s.budget+3)*4,count*4);}
  break;}
 default:throw std::logic_error("unregistered ng access contract");
 }
 return out;
}
// Compose ordered internal phases into a single external submission contract.
// Only prior-phase writes discharge a read; writes in the SAME phase do not.
// Thus read/modify/write inputs and all external WAR/WAW edges are retained.
inline std::vector<Access> sequential_contract(const std::vector<std::vector<Access>>& phases) {
 std::vector<Access> result;std::vector<std::pair<uintptr_t,uintptr_t>> produced;
 for(const auto& phase:phases){
  for(auto x:phase){
   auto begin=reinterpret_cast<uintptr_t>(x.p),end=begin+x.bytes;
   if(end<begin)throw std::logic_error("fusion access range overflow");
   if(x.read){std::vector<std::pair<uintptr_t,uintptr_t>> needed{{begin,end}};
    for(auto [lo,hi]:produced){std::vector<std::pair<uintptr_t,uintptr_t>> next;
     for(auto [a,b]:needed){if(hi<=a||lo>=b)next.push_back({a,b});else{if(a<lo)next.push_back({a,lo});if(hi<b)next.push_back({hi,b});}}needed=std::move(next);}
    for(auto [a,b]:needed)if(a<b)result.push_back({reinterpret_cast<void*>(a),b-a,true,false,x.index});
   }
   if(x.write)result.push_back({x.p,x.bytes,false,true,x.index});
  }
  for(auto x:phase)if(x.write)produced.push_back({reinterpret_cast<uintptr_t>(x.p),reinterpret_cast<uintptr_t>(x.p)+x.bytes});
 }
 return result;
}
template<class Chain> std::vector<Access> describe_chain(ownrt::Device& d,const Chain& op,std::span<const ownrt::Allocation> ids){
 std::vector<std::vector<Access>> phases;
 for(const auto& item:op.chain_items){
  if(item.offset<0||item.count<0||size_t(item.offset)>ids.size()||size_t(item.count)>ids.size()-size_t(item.offset))throw std::logic_error("chain access binding range");
  auto sub=ids.subspan(item.offset,item.count);
  if(item.mode==4){
   phases.push_back(describe_ng(d,item.shape,sub));
   if(item.shape.op==ng::attention_score){auto shape=item.shape;shape.op=ng::attention_softmax;phases.push_back(describe_ng(d,shape,sub));shape.op=ng::attention_value;phases.push_back(describe_ng(d,shape,sub));}
  }else if(item.mode==0||item.mode==3)phases.push_back(describe_spec(d,item.spec,sub,item.mode));
  else throw std::logic_error("unregistered fused chain mode");
 }
 return sequential_contract(phases);
}
template<class Op> ownrt::Event submit(ownrt::Device& d,const Op& op,std::span<const ownrt::Allocation> ids,std::span<const Event> deps){
 std::vector<Access> a;
 auto add=[&](int i,bool r,bool w,bool idx=false){auto& row=d.arena.row(ids[i]);a.push_back({row.pointer,row.bytes,r,w,idx});};
 if constexpr(requires{op.chain_items;})a=describe_chain(d,op,ids);
 else if constexpr(requires{op.rank_spec;})a=describe_spec(d,op.rank_spec,ids,0);
 else if constexpr(requires{op.batch_access;}){
  if(ids.size()!=op.batch_access.size()+1)throw std::logic_error("batch access binding count");
  add(0,true,false,true);
  for(size_t i=0;i<op.batch_access.size();++i){unsigned flags=op.batch_access[i];if(!(flags&3)||(flags&~7u))throw std::logic_error("unregistered batch access flags");add(i+1,flags&1,flags&2,flags&4);}
 }
 else if constexpr(requires{op.s;op.mode;})a=describe_spec(d,op.s,ids,op.mode);
 else if constexpr(requires{op.spec;})a=describe_spec(d,op.spec,ids,-1);
 else if constexpr(requires{op.shape;})a=describe_ng(d,op.shape,ids);
 else if constexpr(requires{op.split_matrix;op.split_final;}){
  if(ids.size()!=6)throw std::logic_error("split4 access binding count");
  auto& workspace=d.arena.row(ids[5]);size_t bytes=size_t(op.split_matrix.count)*op.split_matrix.rows*4*sizeof(float);
  if(bytes>workspace.bytes)throw std::logic_error("split4 workspace access extent");
  a.push_back({workspace.pointer,bytes,op.split_final,!op.split_final,false});
  if(op.split_final){add(2,false,true);if(op.split_matrix.routes)add(3,true,false,true);}
  else{add(0,true,false);add(1,true,false);if(op.split_matrix.routes){add(3,true,false,true);add(4,false,true);}}
 }
 else if constexpr(requires{op.matrices;}){for(size_t i=0;i<op.matrices.size();++i){add(i*5,true,false);add(i*5+1,true,false);add(i*5+2,false,true);if(op.matrices[i].routes){add(i*5+3,true,false,true);add(i*5+4,false,true);}}}
 else if constexpr(requires{op.rows;}){add(0,true,false);add(1,true,false);add(2,false,true);}
 else static_assert(sizeof(Op)==0,"missing access contract");
 // Capture the concrete object by value. Packet16 stack-local operation wrappers
 // expire at submit return; retaining their addresses would introduce a mock bug.
 closure=[op](std::span<void*const> p){op.run(p);};accesses=std::move(a);return d.compute(op,ids,deps);
}
}
