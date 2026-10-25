#pragma once
// Opt-in canonical draft advancement and restored recursive proposal transaction.
#include "pipeline/ring/wire.hpp"
#include "pipeline/live_draft.hpp"
#include <span>
#include <chrono>
namespace ownrt::recursive_provider_next {
using ring_next::Digest;using ring_next::Row;using ring_next::need;
template<class Admitted,class Drain> void quiesce(Admitted admitted,Drain drain){
 need(admitted(),"depth2 exclusive owner before drain");drain();need(admitted(),"depth2 owner changed while draining");
}
struct Input {
 Row seed;live_draft::Handoff parent;int sequence=0;bool head=false;
 std::vector<uint8_t> hidden;
};
// Construct this from the independently retained verified seed and final COMMIT
// record, not by decoding the Input a second time. The seed is a verified INPUT;
// its own target row need not have executed. The coordinator owns these input
// identities and parent final tickets; native admission checks the causal chain.
struct ExpectedPair {Row seed;live_draft::Handoff parent;uint64_t provider_serial=0;};
struct Result {int position=0;std::vector<int> guesses;bool byte_verified=false;size_t snapshot_bytes=0;double canonical_ms=0,capture_ms=0,recursive_ms=0,restore_ms=0;};
// Provider owns a complete post-canonical checkpoint. No exception path submits
// recovery copies: an invalid/failed branch poisons this owner and publishes none.
template<class Provider> Result depth2(Provider& p,const Input& input,bool verify){
 p.idle();need(p.healthy()&&p.position()+1==input.seed.position,"depth2 canonical position");
 need(input.seed.token>=0&&input.seed.token<p.vocab(),"depth2 confirmed token");
 const auto now=[](){return std::chrono::steady_clock::now();};const auto elapsed=[&](auto start){return std::chrono::duration<double,std::milli>(now()-start).count();};
 const auto canonical_start=now();const int first=p.canonical(input.seed.token,input.seed.position,input.head,input.hidden);
 p.idle();need(p.healthy()&&p.position()==input.seed.position,"depth2 canonical advancement");
 need(input.head?(first>=0&&first<p.vocab()):first==-1,"depth2 canonical proposal bound");
 Result result;result.canonical_ms=elapsed(canonical_start);result.position=p.position();if(input.head)result.guesses.push_back(first);
 if(!input.head||p.position()>=p.context())return result;
 const auto capture_start=now();p.capture();result.capture_ms=elapsed(capture_start);result.snapshot_bytes=p.snapshot_bytes();
 const auto recursive_start=now();const int second=p.recursive(first);
 p.idle();need(p.healthy()&&p.position()==input.seed.position+1&&second>=0&&second<p.vocab(),"depth2 hypothetical branch failure");
 result.recursive_ms=elapsed(recursive_start);const auto restore_start=now();p.restore(verify);p.idle();need(p.healthy()&&p.position()==result.position,"depth2 post-canonical restore");
 result.restore_ms=elapsed(restore_start);result.guesses.push_back(second);result.byte_verified=verify;return result;
}
class Sequence {
 ring_next::wire::Context context_;int next_position_=1,last_sequence_=0,last_commit_=0;
 uint64_t serial_=0;Row last_seed_{};bool poisoned_=false;Result last_result_{};
 static std::string hex(const Digest& value){constexpr char digits[]="0123456789abcdef";std::string out;for(auto v:value){out+=digits[v>>4];out+=digits[v&15];}return out;}
public:
 explicit Sequence(ring_next::wire::Context context):context_(context){ring_next::wire::context(context);need(context.stage==0,"depth2 provider must belong to first stage");}
 const Result& last_result()const{return last_result_;}
 uint64_t serial()const{return serial_;}bool poisoned()const{return poisoned_;}
 void admit(const Input& in,const ExpectedPair& expected)const{
  need(!poisoned_&&in.sequence>last_sequence_&&serial_!=UINT64_MAX,"depth2 stale/failed command");
  const auto& row=in.seed;const auto& h=in.parent;
  need(row==expected.seed&&std::memcmp(&h,&expected.parent,sizeof h)==0&&expected.provider_serial==serial_+1,"depth2 retained verified seed/final commit binding");
  need(row.fixture>=0&&in.head==(row.fixture>0),"depth2 canonical seed head mask");
  live_draft::validate(h,context_.stream_bytes,context_.stages,context_.vocab);
  need(in.hidden.size()==size_t(context_.stream_bytes)&&hex(ring_next::wire::digest(in.hidden))==std::string(h.hidden_sha256.data(),h.hidden_sha256.size()),"depth2 owned raw hidden SHA");
  need(row.epoch==context_.epoch&&row.request==context_.request&&row.id>row.parent&&row.parent>0&&row.position==next_position_&&row.token>=0&&row.token<context_.vocab,"depth2 request/seed identity");
  need(h.position==row.position-1&&h.commit_sequence>last_commit_&&(!h.head||h.next_token==row.token),"depth2 final canonical parent");
  need(row.after==ring_next::extend(row.before,uint32_t(row.position),uint32_t(row.token)),"depth2 seed prefix");
  if(serial_)need(row.parent==last_seed_.id&&row.before==last_seed_.after&&h.input_token==last_seed_.token,"depth2 exact canonical ancestry");
  else need(row.position==1&&row.before==ring_next::extend(ring_next::request_prefix(context_.request,context_.epoch),0,uint32_t(h.input_token)),"depth2 first canonical parent prefix");
 }
 template<class Provider> ring_next::wire::ProposalMeta run(Provider& provider,const Input& input,const ExpectedPair& expected,bool verify){
  admit(input,expected);last_sequence_=input.sequence;
  try{
   const auto result=depth2(provider,input,verify);need(result.guesses.size()<=2&&result.position==input.seed.position,"depth2 result extent");
   ring_next::wire::ProposalMeta out;out.flags=(input.head?1u:0u)|2u;out.epoch=context_.epoch;out.ticket=input.sequence;out.seed_row=input.seed.id;out.parent_row=input.seed.parent;out.final_commit=input.parent.commit_sequence;out.provider_serial=serial_+1;
   out.seed_position=out.restored_position=result.position;out.available_depth=int32_t(result.guesses.size());out.guess0=result.guesses.empty()?-1:result.guesses[0];out.guess1=result.guesses.size()<2?-1:result.guesses[1];out.restored=1;
   out.request=context_.request;out.seed_prefix=input.seed.after;out.hidden_sha=ring_next::wire::digest(input.hidden);
   ring_next::wire::validate_batch(out,context_,input.sequence,input.seed.position,input.seed.after,out.hidden_sha,{input.seed.id,input.seed.parent,uint64_t(input.parent.commit_sequence),serial_+1});
   last_result_=result;++serial_;last_seed_=input.seed;last_commit_=input.parent.commit_sequence;++next_position_;return out;
  }catch(...){poisoned_=true;throw;}
 }
};
}
