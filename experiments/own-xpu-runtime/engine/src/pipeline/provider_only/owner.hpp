#pragma once
// Experimental dedicated MTP owner. No target StageRing, target-layer plan or
// synthetic target stage. The wire Context describes the independently witnessed
// target seed/final owners; it does NOT assign this process a target stage.
#include "pipeline/recursive_provider/batch.hpp"
#include "pipeline/recursive_provider/seed_peer.hpp"
#include <optional>

namespace ownrt::provider_only {
struct Topology {
 std::vector<std::string> target_bdfs;
 std::string provider_bdf;
 void validate(const ring_next::wire::Context& context)const {
  ring_next::need(target_bdfs.size()>=2&&target_bdfs.size()<=6&&
    int(target_bdfs.size())==context.stages&&context.stage==0&&!provider_bdf.empty(),
    "dedicated MTP role/target topology");
  for(size_t i=0;i<target_bdfs.size();++i){
   ring_next::need(!target_bdfs[i].empty()&&target_bdfs[i]!=provider_bdf,"dedicated MTP device overlaps target");
   for(size_t j=0;j<i;++j)ring_next::need(target_bdfs[i]!=target_bdfs[j],"duplicate target device");
  }
 }
};
// Draft is the actual mtp36::DraftRuntime at native integration. CPU tests supply
// an adapter over the existing synthetic recursive-provider fixture, not a GPU
// arithmetic implementation. Peers must be read-only inode-pinned snapshots;
// callers may not replace target journals with controller-asserted seed rows.
template<class Draft> class Owner {
 Draft& draft;
 Topology topology_;
 ring_next::wire::Context context_;
 std::optional<recursive_provider_next::Sequence> sequence_;
 int last_command_=0,last_final_commit_=0;
 bool failed_=false;
public:
 static constexpr const char* role="dedicated-mtp";
 Owner(Draft& runtime,Topology topology,ring_next::wire::Context context)
  :draft(runtime),topology_(std::move(topology)),context_(context),sequence_(context){
  topology_.validate(context_);boundary();
 }
 const Topology& topology()const{return topology_;}
 uint64_t serial()const{return sequence_->serial();}
 bool failed()const{return failed_;}
 const recursive_provider_next::Result& last_result()const{return sequence_->last_result();}
 void boundary(){
  ring_next::need(!failed_&&!sequence_->poisoned(),"dedicated MTP failed owner");
  draft.recursive_idle();
  ring_next::need(draft.recursive_healthy()&&!draft.recursive_active&&
    uint64_t(draft.live_position())==serial(),"dedicated MTP canonical boundary");
 }
 ring_next::wire::ProposalMeta run(int command,const recursive_provider::SeedRecord& seed,
     const recursive_provider::FinalRecord& final,const std::vector<uint8_t>& hidden,bool verify){
  ring_next::need(!failed_&&command>last_command_,"dedicated MTP stale/failed command");
  try{
   boundary();
   recursive_provider::validate_final_record(final,context_,hidden);
   ring_next::need(final.hidden.commit_sequence>last_final_commit_,"dedicated MTP stale final commit");
   const auto row=recursive_provider::seed_row(seed,context_);
   ring_next::need(row.parent==final.row.id&&row.before==final.row.after&&
      row.position==final.row.position+1,"dedicated MTP independent target ancestry");
   recursive_provider_next::Input input{row,final.hidden,command,row.fixture>0,hidden};
   const recursive_provider_next::ExpectedPair expected{row,final.hidden,serial()+1};
   sequence_->admit(input,expected); // refuse before any canonical arithmetic
   last_command_=command;
   auto result=draft.live_recursive_depth2(*sequence_,input,expected,verify);
   last_final_commit_=final.hidden.commit_sequence;boundary();
   return result;
  }catch(...){failed_=true;throw;} // no automatic reset/retry/recovery copies
 }
 // OP9 is only a no-head canonical prefix replay, authenticated by the same
 // independent source journals. Recursive proposals still use run()/Sequence.
 void canonical(int command,const recursive_provider::SeedRecord& seed,
     const recursive_provider::FinalRecord& final,const std::vector<uint8_t>& hidden){
  ring_next::need(!failed_&&command>last_command_,"dedicated MTP stale/failed command");
  try{
   boundary();recursive_provider::validate_final_record(final,context_,hidden);
   const auto row=recursive_provider::seed_row(seed,context_);
   ring_next::need(!row.fixture&&final.hidden.commit_sequence>last_final_commit_&&
     row.parent==final.row.id&&row.before==final.row.after&&row.position==final.row.position+1,
     "dedicated MTP canonical replay ancestry/head");
   recursive_provider_next::Input input{row,final.hidden,command,false,hidden};
   const recursive_provider_next::ExpectedPair expected{row,final.hidden,serial()+1};
   sequence_->admit(input,expected);last_command_=command;
   auto result=draft.live_recursive_depth2(*sequence_,input,expected,false);
   ring_next::need(!result.available_depth&&result.guess0==-1,"dedicated MTP no-head completion");
   last_final_commit_=final.hidden.commit_sequence;boundary();
  }catch(...){failed_=true;throw;}
 }
 // Outer lifecycle attests the old request, then barriers every target owner.
 // This operation owns only draft canonical/pinned/private allocations. The
 // zero_private callback must zero its retained recursive backup, never targets.
 template<class Path,class ZeroPrivate> void reset(int command,uint64_t epoch,
      ring_next::Digest request,const Path& destination,ZeroPrivate zero_private){
  ring_next::need(!failed_&&command>last_command_&&epoch==context_.epoch+1&&
       request!=context_.request,"dedicated MTP reset identity/command");
  try{
   boundary();draft.live_reset_admission();
   draft.reset_request(destination);zero_private(draft);
   draft.recursive_reset_after_owner_zero();
   context_.epoch=epoch;context_.request=request;
   sequence_.emplace(context_);last_command_=command;last_final_commit_=0;boundary();
  }catch(...){failed_=true;throw;}
 }
};
} // namespace ownrt::provider_only
