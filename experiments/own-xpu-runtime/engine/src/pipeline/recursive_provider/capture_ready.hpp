#pragma once
#include "pipeline/recursive_provider/final_event.hpp"
namespace ownrt::recursive_provider {
// Nonterminal socket event. It releases only the final hidden-buffer lease;
// stage0 remains occupied until the ordinary provider completion reply.
constexpr int capture_ready_status=2;
struct CaptureReady {
 uint64_t magic=0x315950414352574full;uint32_t version=1,bytes=128;
 uint64_t epoch=0,sequence=0,seed=0,parent=0,final_commit=0,provider_serial=0;
 ring_next::Digest request{},final_record_sha{};
};
static_assert(sizeof(CaptureReady)==128&&offsetof(CaptureReady,epoch)==16&&offsetof(CaptureReady,request)==64);
inline CaptureReady captured(const ring_next::wire::Context& context,const ring_next::Row& seed,const FinalRecord& record,int sequence,uint64_t serial){
 ring_next::need(context.stage>=0&&context.stage<context.stages-1&&sequence>0&&serial>0&&seed.parent==record.row.id&&seed.epoch==context.epoch&&seed.request==context.request,"capture-ready owned identities");
 CaptureReady out;out.epoch=context.epoch;out.sequence=sequence;out.seed=seed.id;out.parent=seed.parent;out.final_commit=record.published_sequence;out.provider_serial=serial;out.request=context.request;
 out.final_record_sha=ring_next::wire::digest(std::span<const uint8_t>(reinterpret_cast<const uint8_t*>(&record),sizeof record));return out;
}
}
