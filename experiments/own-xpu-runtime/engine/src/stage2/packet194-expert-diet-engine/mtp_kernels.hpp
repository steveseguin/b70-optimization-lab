#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#pragma once
#include "stage2/packet194-expert-diet-engine/performance.hpp"
namespace mtp36 {
// Draft-only requantisation of the official draft head; cannot change output.
struct Linear {
 ownrt::Allocation w{},peer{},x{},y{},py{},routes{},status{},ps{};
 unsigned rows{},columns{},batch=1,experts=1;bool int8=false,paired=false,fp8=false;
};
integrated::Launch elementwise(ownrt::Device&,const integrated::Spec&,std::span<const ownrt::Allocation>);
integrated::Launch linear(ownrt::Device&,const Linear&);
integrated::Launch norm_hidden(ownrt::Device&,ownrt::Allocation x,ownrt::Allocation gain,ownrt::Allocation y,ownrt::Allocation scratch,unsigned width);
integrated::Launch merge(ownrt::Device&,ownrt::Allocation hidden,ownrt::Allocation embedding,ownrt::Allocation streams,unsigned width);
// OWNRT_DRAFT_HEAD_SPLIT (lab 2026-10-29, draft_head_split.hpp): one card's draft-head rows -> its Best record in
// `words` (slot = card), with the logits of global rows [offset, offset + rows); card 0's merge of both records.
integrated::Launch head_shard(ownrt::Device&,ownrt::Allocation logits,ownrt::Allocation words,ownrt::Allocation active,ownrt::Allocation error,unsigned rows,unsigned offset,unsigned slot);
integrated::Launch head_merge(ownrt::Device&,ownrt::Allocation words,ownrt::Allocation token,ownrt::Allocation active,ownrt::Allocation error);
}
