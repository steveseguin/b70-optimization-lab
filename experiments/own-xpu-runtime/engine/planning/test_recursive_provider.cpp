#include "pipeline/recursive_provider/batch.hpp"
#include <cassert>
#include <iostream>
using namespace ownrt;using namespace recursive_provider_next;
template<class F>void refusal(F f){bool failed=false;try{f();}catch(const std::exception&){failed=true;}assert(failed);}
struct Provider {
 struct State {int position=0,extent=32;int pending=0;uint64_t event=0;std::vector<uint8_t> hidden;std::vector<std::vector<uint8_t>> allocations;bool operator==(const State&)const=default;} state,saved;
 int limit=64;bool error=false,fail_branch=false,fail_restore=false;int captures=0,restores=0,full_reads=0,canonical_calls=0,recursive_calls=0;
 Provider(){for(size_t i=0;i<73;++i)state.allocations.emplace_back(1+i%17,uint8_t(i));}
 void idle(){}bool healthy()const{return !error;}int position()const{return state.position;}int context()const{return limit;}int vocab()const{return 97;}
 void update(int token){++state.position;state.extent=((state.position+31)/32)*32;for(size_t i=0;i<state.allocations.size();++i)for(auto& x:state.allocations[i])x=uint8_t(x+token+state.position+i);state.pending+=token;state.event+=state.position;state.hidden.assign(16,uint8_t(token));}
 int canonical(int token,int position,bool head,const std::vector<uint8_t>& hidden){assert(position==state.position+1&&hidden.size()==16);++canonical_calls;update(token);return head?(token+position*7)%97:-1;}
 void capture(){saved=state;++captures;}size_t snapshot_bytes()const{size_t n=0;for(auto& a:state.allocations)n+=a.size();return n;}
 int recursive(int first){++recursive_calls;update(first);if(fail_branch){error=true;throw std::runtime_error("partial provider branch");}return (first+state.position*7)%97;}
 void restore(bool verify){assert(!error);++restores;state=saved;if(fail_restore)state.allocations.back()[0]^=1;if(verify){full_reads+=int(state.allocations.size());assert(state.allocations.size()==73);need(state==saved,"all canonical/pinned/host bytes restored");}}
};
std::string hex(const ring_next::Digest& bytes){const char*d="0123456789abcdef";std::string out;for(auto b:bytes){out+=d[b>>4];out+=d[b&15];}return out;}
struct Fixture {
 ring_next::wire::Context context{0,{},0,4,16,97};Sequence sequence{context};Provider provider;Row last;int ticket=0;
 Input next(bool head=true){Input in;auto& r=in.seed;r.epoch=0;r.request=context.request;r.parent=last.id?last.id:1;r.id=r.parent+1;r.position=provider.position()+1;r.token=(r.position*3+4)%97;r.fixture=head?std::max(1,last.fixture+1):0;r.ticket=100+r.position;r.tentative=true;
  const int parent_token=last.id?last.token:7;r.before=last.id?last.after:ring_next::extend(ring_next::request_prefix(context.request,0),0,parent_token);r.after=ring_next::extend(r.before,r.position,r.token);
  in.sequence=++ticket;in.head=head;in.hidden.assign(16,uint8_t(r.position));auto& h=in.parent;h.bytes=16;h.position=r.position-1;h.final_stage=3;h.stages=4;h.row_ticket=2*r.position;h.commit_sequence=h.row_ticket+1;h.input_token=parent_token;h.head=last.fixture>0;h.next_token=h.head?r.token:-1;const auto sha=hex(ring_next::wire::digest(in.hidden));std::copy(sha.begin(),sha.end(),h.hidden_sha256.begin());return in;
 }
 ExpectedPair expected(const Input& in){return {in.seed,in.parent,sequence.serial()+1};}
 auto run(Input in,bool verify){auto out=sequence.run(provider,in,expected(in),verify);last=in.seed;return out;}
};
int main(){
 {bool callback=true;int drains=0;refusal([&]{quiesce([&]{return !callback;},[&]{++drains;});});assert(!drains);callback=false;quiesce([&]{return !callback;},[&]{++drains;});assert(drains==1);refusal([&]{quiesce([&]{return !callback;},[&]{++drains;callback=true;});});assert(drains==2);}

 for(bool verify:{false,true}){Fixture f;Provider reference;for(int position=1;position<=64;++position){auto input=f.next(position>=3);auto expected=f.expected(input);auto before=f.provider.state;const int canonical=reference.canonical(input.seed.token,position,input.head,input.hidden);auto out=f.sequence.run(f.provider,input,expected,verify);f.last=input.seed;
  assert(f.provider.state==reference.state&&f.provider.position()==position&&out.restored_position==position&&out.guess0==canonical&&out.provider_serial==uint64_t(position));
  assert(out.available_depth==(!input.head?0:position<64?2:1));assert(f.sequence.last_result().byte_verified==(verify&&input.head&&position<64));assert(bool(f.sequence.last_result().snapshot_bytes)==(input.head&&position<64));if(position==31||position==32||position==33)assert(f.provider.state.extent==reference.state.extent);
 }
 assert(f.provider.captures==61&&f.provider.restores==61&&f.provider.recursive_calls==61&&f.provider.full_reads==(verify?61*73:0));}
 for(int mutation=0;mutation<10;++mutation){Fixture f;auto in=f.next();auto expected=f.expected(in);switch(mutation){case 0:++in.seed.id;break;case 1:++in.seed.parent;break;case 2:++in.parent.row_ticket;break;case 3:++in.parent.commit_sequence;break;case 4:++expected.provider_serial;break;case 5:in.hidden[0]^=1;break;case 6:in.seed.after[0]^=1;break;case 7:in.head=false;break;case 8:in.seed.epoch=1;break;case 9:in.seed.request[0]=1;break;}refusal([&]{f.sequence.run(f.provider,in,expected,false);});assert(!f.provider.canonical_calls&&!f.sequence.poisoned());}
 {Fixture f;auto first=f.next();f.run(first,false);auto second=f.next();auto wrong=f.expected(second);wrong.seed.parent=77;second.seed=wrong.seed;refusal([&]{f.sequence.run(f.provider,second,wrong,false);});assert(f.provider.canonical_calls==1);}
 for(bool restore_failure:{false,true}){Fixture f;auto in=f.next();auto expected=f.expected(in);f.provider.fail_branch=!restore_failure;f.provider.fail_restore=restore_failure;refusal([&]{f.sequence.run(f.provider,in,expected,true);});assert(f.sequence.poisoned()&&f.sequence.serial()==0&&f.provider.canonical_calls==1&&f.provider.restores==int(restore_failure));refusal([&]{f.sequence.run(f.provider,in,expected,true);});assert(f.provider.canonical_calls==1);}
 std::cout<<"PASS post-canonical depth2 restore of 73 synthetic mutable allocations/host state, 31/32/33 extents, no-head/capacity censoring, default no full readback, exact lineage/commit/serial/head binding and no recovery after partial failure; CPU only\n";
}
