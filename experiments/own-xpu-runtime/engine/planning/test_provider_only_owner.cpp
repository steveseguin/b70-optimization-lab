// Reuse the real Sequence and its existing CPU arithmetic/state fixture.
// This is owner/control validation; it does not establish GPU arithmetic parity.
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wreturn-type"
#define main recursive_fixture_old_main
#include "test_recursive_provider.cpp"
#undef main
#pragma GCC diagnostic pop
#include "pipeline/provider_only/owner.hpp"
struct Runtime : Provider {
 bool recursive_active=false;int private_zeroes=0;
 void recursive_idle(){idle();}bool recursive_healthy()const{return healthy();}
 int live_position()const{return position();}
 auto live_recursive_depth2(Sequence& sequence,const Input& input,const ExpectedPair& expected,bool verify){return sequence.run(*this,input,expected,verify);}
 void live_reset_admission(){need(!error,"failed runtime reset refused");}
 void reset_request(const std::string&){state={};}
 void recursive_reset_after_owner_zero(){need(private_zeroes>0&&position()==0,"cold retained image reset");}
};
struct Witness {
 recursive_provider::SeedRecord seed;
 recursive_provider::FinalRecord final;
 std::vector<uint8_t> hidden;
};
Witness witness(Fixture& fixture,int targets,bool head=true){
 auto in=fixture.next(head);in.parent.stages=targets;in.parent.final_stage=targets-1;
 Witness out;out.hidden=in.hidden;
 const auto& row=in.seed;
 auto& s=out.seed;s.published_sequence=row.ticket+1;s.physical=s.committed=row.position+1;
 auto& m=s.row;m.epoch=row.epoch;m.request=row.request;m.id=row.id;m.parent=row.parent;
 m.position=row.position;m.token=row.token;m.fixture=row.fixture;m.flags=ring_next::wire::tentative;
 m.payload_sha=ring_next::wire::digest({});m.before=row.before;m.after=row.after;m.owner=0;m.publication_ticket=row.ticket;
 auto& f=out.final;f.stage=targets-1;f.published_sequence=in.parent.commit_sequence;f.hidden=in.parent;
 auto& p=f.row;p.epoch=row.epoch;p.request=row.request;p.id=row.parent;p.parent=row.parent-1;
 p.position=row.position-1;p.token=in.parent.input_token;p.fixture=in.parent.head?1:0;
 p.owner=targets-1;p.final=1;p.publication_ticket=in.parent.row_ticket;
 p.payload_sha=ring_next::wire::digest({});p.before=ring_next::request_prefix(row.request,row.epoch);p.after=ring_next::extend(p.before,p.position,p.token);
 // Tests below use the initial true pair; fixture ancestry is independently set
 // by its canonical request-prefix derivation, never copied from final metadata.
 assert(p.after==row.before);
 return out;
}
 #ifndef PROVIDER_OWNER_FIXTURE_ONLY
int main(){
 using Dedicated=provider_only::Owner<Runtime>;
 for(int targets:{2,3}){
  Fixture fixture;Runtime runtime;auto context=fixture.context;context.stages=targets;context.depth=3;
  provider_only::Topology topology;for(int i=0;i<targets;++i)topology.target_bdfs.push_back("target"+std::to_string(i));topology.provider_bdf="draft";
  Dedicated owner(runtime,topology,context);auto input=witness(fixture,targets);
  const auto proposal=owner.run(1,input.seed,input.final,input.hidden,true);
  assert(proposal.provider_serial==1&&proposal.available_depth==3&&runtime.position()==1&&runtime.captures==1&&runtime.restores==1);
  auto expected=runtime.state;owner.boundary();assert(runtime.state==expected);
  auto next=context.request;next[0]=1;
  owner.reset(2,1,next,std::string("unused-cpu-output"),[](Runtime& d){++d.private_zeroes;});
  assert(owner.serial()==0&&runtime.position()==0&&runtime.private_zeroes==1&&!owner.failed());
  refusal([&]{owner.run(3,input.seed,input.final,input.hidden,true);});assert(owner.failed());
 }
 for(int mutation=0;mutation<4;++mutation){
  Fixture fixture;Runtime runtime;auto context=fixture.context;context.stages=3;context.depth=3;
  Dedicated owner(runtime,{{"a","b","c"},"d"},context);auto input=witness(fixture,3);
  if(mutation==0)input.hidden[0]^=1;
  if(mutation==1)++input.seed.row.parent;
  if(mutation==2)input.seed.row.epoch=1;
  if(mutation==3)input.final.stage=3;
  refusal([&]{owner.run(1,input.seed,input.final,input.hidden,true);});assert(!runtime.canonical_calls&&owner.failed());
  refusal([&]{owner.reset(2,1,ring_next::Digest{},std::string("unused"),[](Runtime&){});});
 }

 for(bool head:{false,true}){
  Fixture fixture;Runtime runtime;runtime.limit=1;auto context=fixture.context;context.stages=3;context.depth=3;
  Dedicated owner(runtime,{{"a","b","c"},"d"},context);auto input=witness(fixture,3,head);
  auto proposal=owner.run(1,input.seed,input.final,input.hidden,true);
  assert(proposal.available_depth==(head?1:0)&&!runtime.captures&&!runtime.restores&&owner.serial()==1);
  refusal([&]{owner.run(2,input.seed,input.final,input.hidden,true);});
  assert(owner.failed()&&runtime.canonical_calls==1); // no duplicate canonical work
 }
 {Fixture fixture;Runtime runtime;runtime.fail_branch=true;auto context=fixture.context;context.stages=3;context.depth=3;
  Dedicated owner(runtime,{{"a","b","c"},"d"},context);auto input=witness(fixture,3);
  refusal([&]{owner.run(1,input.seed,input.final,input.hidden,true);});
  assert(owner.failed()&&runtime.canonical_calls==1&&runtime.captures==1&&!runtime.restores);
  auto next=context.request;next[0]=1;refusal([&]{owner.reset(2,1,next,std::string("unused"),[](Runtime&){});});
 }
 {Fixture fixture;Runtime runtime;auto c=fixture.context;refusal([&]{Dedicated owner(runtime,{{"a","b","c","d"},"a"},c);});}
 std::cout<<"PASS dedicated provider role for2/3 targets, actual Sequence recursive rollback, target journal/SHA/epoch admission, retained reset and fail-closed owner; synthetic CPU arithmetic only\n";
}

#endif
