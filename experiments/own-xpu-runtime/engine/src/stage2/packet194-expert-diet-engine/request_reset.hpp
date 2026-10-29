#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#pragma once
#include "stage2/packet194-expert-diet-engine/request_state_inventory.hpp"
#ifndef OWN_RT_HOST_ONLY
namespace reset_zero {
// Zero bytes for one device allocation: 16-byte stores (USM device allocations are at least 16-byte aligned), the
// last partial word byte by byte.
struct Fill:ownrt::SyclOperation {
 size_t bytes=0;
 sycl::event submit(sycl::queue& q,std::span<void* const> p,const std::vector<sycl::event>& deps) const override {
  auto* d=static_cast<uint8_t*>(p[0]);const size_t words=bytes/16,tail=bytes%16,n=words+(tail?1:0);
  return ownrt::prepared_submit(q,[=,range=sycl::range<1>(n)](sycl::handler& h){h.parallel_for(range,packet26::checked([=](sycl::id<1> i){
   const size_t k=i[0];if(k<words)reinterpret_cast<sycl::uint4*>(d)[k]=sycl::uint4(0u,0u,0u,0u);else for(size_t j=words*16;j<words*16+tail;++j)d[j]=0;}));});
 }
};
}
#endif
// Request boundary only: no allocation release or prepared-command invalidation.
namespace pipeline {
static void request_reset(Engine& e,Candidate& candidate,mtp36::DraftRuntime* provider,
                          const fs::path& metadata,int accepted,
                          const std::optional<std::pair<fs::path,std::string>>& admitted={}) {
 require(!candidate.pending,"reset with unresolved candidate");
 e.drain();require(!e.poisoned && !e.integer(0,"error"),"reset cannot clear target failure");
 // A deferred diagnostic still owns the previous draft state. Flush before
 // any allocation (including its backup) is zeroed, even with reset_dump off.
 if(provider)provider->flush_depth_probe();
 std::string output,oracle;
 if(admitted){output=admitted->first.string();oracle=admitted->second;}
 else {std::ifstream input(metadata);require(bool(std::getline(input,output))&&bool(std::getline(input,oracle)),"reset metadata");}
 fs::path destination(output);require(destination.is_absolute()&&!output.empty(),"reset output absolute");
 // Keep all boundary/drain/reset actions; only optional evidence readbacks disappear.
 if(e.a.reset_dump){state_dump(e,2147483647);request_state_inventory(e);if(provider)provider->dump_all_state(e.a.output/"draft-final-state");}
 e.dump_classes(e.a.output/"class-times.json",accepted);
 if(e.bank_parity)e.swap_state_banks();
 // Covers plan allocations, both recurrent banks, QSA unused tails, snapshots,
 // scratch and draft mutable allocations. Immutable weights and slab stay live.
 std::vector<uint8_t> zero(4*1024*1024,0);
 size_t reset_bytes=0,reset_allocations=0;
#ifndef OWN_RT_HOST_ONLY
 // OWNRT_RESET_DEVICE_ZERO=1: the same allocations receive the same zero bytes from one device store kernel each,
 // submitted back to back and drained once, instead of 4 MiB host uploads that each drain, copy over PCIe and wait.
 static const bool device_zero=[]{const char* v=std::getenv("OWNRT_RESET_DEVICE_ZERO");return v&&v[0]=='1';}();
#else
 constexpr bool device_zero=false;
#endif
 if(device_zero)e.drain();
 for(const auto& [id,owner]:e.allocations){const auto& row=e.dev(owner.first).arena.row(id);
  if(e.immutable_snapshot_tables.contains(id)){require(row.label=="card0:speculative-static-copy-table"||(e.a.tp_replicate&&row.label=="card1:speculative-static-copy-table"),"immutable snapshot registration");continue;}
  if(!row.live||row.category==Category::weights||row.category==Category::pinned_slab)continue;
#ifndef OWN_RT_HOST_ONLY
  if(device_zero&&row.memory==Memory::device){if(row.bytes){reset_zero::Fill op;op.bytes=row.bytes;std::array<Allocation,1> ids{id};
    e.track(owner.first,e.dev(owner.first).compute(op,ids,{}));}reset_bytes+=row.bytes;++reset_allocations;continue;}
#endif
  for(size_t off=0;off<row.bytes;off+=zero.size())e.upload(owner.first,id,off,zero.data(),std::min(zero.size(),row.bytes-off));
  reset_bytes+=row.bytes;++reset_allocations;
 }
 if(device_zero)e.drain();
 for(int card=0;card<e.a.cards;++card){
  float unit=1;e.upload(card,e.one[card],0,&unit,4);uint32_t active=1;e.put(card,"active",&active,4);
  if(e.buffers[card].count("token_history")){int64_t history[2]={e.p.g.eos,e.p.g.eos};
   e.put(card,"token_history",history,sizeof history);e.put(card,"ple_metadata",e.metadata.data(),e.metadata.size()*8);}
 }
 e.prefill_bank_parity_bias=0;
 e.history0=e.history1=e.p.g.eos;e.lookup_ids.clear();
 for(auto& selected:e.selected)selected.clear();
 std::fill(e.fp32_sources.begin(),e.fp32_sources.end(),0);std::fill(e.fp32_extents.begin(),e.fp32_extents.end(),0);
 e.logical=0;e.drain();e.submission_card=-1;e.current_cls=0;e.host_waits=0;e.parity_argument_checks=0;
 e.wait_ms=e.prepare_ms=e.enqueue_ms=e.enqueue_including_wait_ms=0;
 e.gemv_ms=e.nongemv_ms=e.transfer_ms=0;e.submitted=e.max_submission_ns=0;e.family_ms.fill(0);
 std::fill(e.class_ms.begin(),e.class_ms.end(),0);std::fill(e.class_launches.begin(),e.class_launches.end(),0);std::fill(e.class_groups.begin(),e.class_groups.end(),0);
 fs::create_directories(destination);e.a.output=destination;e.a.oracle=oracle;
 auto reopen=[&](std::ofstream& stream,const char* name){stream.close();stream.clear();stream.open(destination/name);require(bool(stream),std::string("reset stream ")+name);};
 reopen(e.timings,"timings.jsonl");reopen(e.prefill_timings,"prefill-timings.jsonl");reopen(e.site_timings,"sites.jsonl");reopen(e.progress,"progress.jsonl");
 if(e.a.argument_audit)reopen(e.argument_log,"argument-equivalence.jsonl");
 if(provider)provider->reset_request(destination);
 // Reset maintenance transfers are outside the next request counters.
 e.drain();e.host_waits=0;e.wait_ms=e.prepare_ms=e.enqueue_ms=e.enqueue_including_wait_ms=0;
 e.gemv_ms=e.nongemv_ms=e.transfer_ms=0;e.submitted=e.max_submission_ns=0;
 candidate={};
 save(destination/"reset.json","{\"passed\":true,\"allocation_ids_preserved\":true,\"allocations\":"+std::to_string(reset_allocations)+",\"bytes\":"+std::to_string(reset_bytes)+"}");
}
// Conversation continuation boundary (command 16): the next request continues this state (the service has checked
// that its prompt extends the processed tokens). Only the output directory and its log streams change; no allocation,
// bank, history, counter or draft state is touched.
static void request_redirect(Engine& e,mtp36::DraftRuntime* provider,const fs::path& metadata) {
 e.drain();require(!e.poisoned && !e.integer(0,"error"),"redirect after target failure");
 if(provider)provider->flush_depth_probe();
 std::ifstream input(metadata);std::string output;
 require(bool(std::getline(input,output)),"redirect metadata");
 fs::path destination(output);require(destination.is_absolute()&&!output.empty(),"redirect output absolute");
 fs::create_directories(destination);e.a.output=destination;
 auto reopen=[&](std::ofstream& stream,const char* name){stream.close();stream.clear();stream.open(destination/name);require(bool(stream),std::string("redirect stream ")+name);};
 reopen(e.timings,"timings.jsonl");reopen(e.prefill_timings,"prefill-timings.jsonl");reopen(e.site_timings,"sites.jsonl");reopen(e.progress,"progress.jsonl");
 if(e.a.argument_audit)reopen(e.argument_log,"argument-equivalence.jsonl");
 if(provider)provider->redirect(destination);
 save(destination/"redirect.json","{\"passed\":true,\"state_kept\":true}");
}
}
