#pragma once
#include "request_state_inventory.hpp"
// Request boundary only: no allocation release or prepared-command invalidation.
namespace pipeline {
static void request_reset(Engine& e,Candidate& candidate,mtp36::DraftRuntime* provider,
                          const fs::path& metadata,int accepted) {
 require(!candidate.pending,"reset with unresolved candidate");
 e.drain();require(!e.poisoned && !e.integer(0,"error"),"reset cannot clear target failure");
 std::ifstream input(metadata);std::string output,oracle;
 require(bool(std::getline(input,output))&&bool(std::getline(input,oracle)),"reset metadata");
 fs::path destination(output);require(destination.is_absolute()&&!output.empty(),"reset output absolute");
 // Retain the complete completed state before resetting, including warm-up.
 state_dump(e,2147483647);request_state_inventory(e);if(provider)provider->dump_all_state(e.a.output/"draft-final-state");
 e.dump_classes(e.a.output/"class-times.json",accepted);
 if(e.bank_parity)e.swap_state_banks();
 // Covers plan allocations, both recurrent banks, QSA unused tails, snapshots,
 // scratch and draft mutable allocations. Immutable weights and slab stay live.
 std::vector<uint8_t> zero(4*1024*1024,0);
 size_t reset_bytes=0,reset_allocations=0;
 for(const auto& [id,owner]:e.allocations){const auto& row=e.dev(owner.first).arena.row(id);
  if(!row.live||row.category==Category::weights||row.category==Category::pinned_slab)continue;
  for(size_t off=0;off<row.bytes;off+=zero.size())e.upload(owner.first,id,off,zero.data(),std::min(zero.size(),row.bytes-off));
  reset_bytes+=row.bytes;++reset_allocations;
 }
 for(int card=0;card<e.a.cards;++card){
  float unit=1;e.upload(card,e.one[card],0,&unit,4);uint32_t active=1;e.put(card,"active",&active,4);
  if(e.buffers[card].count("token_history")){int64_t history[2]={e.p.g.eos,e.p.g.eos};
   e.put(card,"token_history",history,sizeof history);e.put(card,"ple_metadata",e.metadata.data(),e.metadata.size()*8);}
 }
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
}
