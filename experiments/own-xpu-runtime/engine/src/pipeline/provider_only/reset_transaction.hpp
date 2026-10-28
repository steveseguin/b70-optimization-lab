#pragma once
#include "pipeline/provider_only/request_suite.hpp"
namespace ownrt::provider_only {
struct BulkResetEvidence {
 int command=0;uint64_t epoch=0;ring_next::Digest request{},prompt_sha{};
 std::string allocation_before,allocation_after;
 size_t invalidated_bytes=0;
};
// Caller must have stopped all target publishers before invoking this component.
// It owns only the provider map, never writes the read-only target peer maps.
// Runtime integration must ACK only on return, and controller must wait ALL ACKs.
// ColdCheck must compare actual device/host cold bytes, not return a constant.
// Inventory must describe live allocation IDs/pointers/extents, not a count.
// Receipt must durably seal that evidence or throw. No boolean cold assertion.
template<class Draft,class ZeroPrivate,class Inventory,class ColdCheck,class Receipt>
void reset_bulk_owner(Owner<Draft>& owner,suite::Prepared& prepared,
 std::unique_ptr<bulk::Prompt>& prompt,std::span<uint8_t> shared,
 ZeroPrivate zero_private,Inventory inventory,ColdCheck cold_check,Receipt receipt,
 bool capability=false){
 const auto& d=prepared.descriptor;const auto& next=prepared.next;
 ring_next::need(capability&&d.stage==-1&&d.next_epoch==next.epoch&&
  d.next_request==bulk::hex(next.request)&&shared.size()==wire::shared_bytes&&
  prompt&&prepared.prompt,"provider transaction admission");
 prompt->stable();prepared.prompt->stable();
 // Keep original map pointer/extent; never remap/replace shared allocations.
 const auto before=inventory();ring_next::need(!before.empty(),"provider allocation inventory absent");
 owner.reset_bulk_transaction(d.sequence,next.epoch,next.request,d.destination,
  zero_private,[&](const auto& actual){
   ring_next::need(cold_check(),"provider reset actual cold bytes differ");
   const auto after=inventory();ring_next::need(after==before,"provider reset physical allocation identity");
   auto replacement=prepared.release_after_owner_reset(actual);
   prompt=std::move(replacement);
   // Quiescent all-owner barrier is mandatory: no peer may be reading this map.
   // This clears Reset/Capture/Proposal/Ack and all reserved/unused publication
   // bytes too. Header is published only after the receipt succeeds.
   std::fill(shared.begin(),shared.end(),uint8_t(0));
   BulkResetEvidence evidence{d.sequence,actual.epoch,actual.request,prompt->sha,before,after,shared.size()};
   receipt(evidence);
   wire::Header header;header.stream_bytes=actual.stream_bytes;
   header.target_stages=actual.stages;header.depth=actual.depth;
   header.epoch=actual.epoch;header.request=actual.request;
   std::memcpy(shared.data(),&header,sizeof header);
  },true);
}
} // namespace ownrt::provider_only
