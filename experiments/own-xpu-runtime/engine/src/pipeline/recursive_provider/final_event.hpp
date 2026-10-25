#pragma once
#include "pipeline/ring/wire.hpp"
#include "pipeline/live_draft.hpp"
namespace ownrt::recursive_provider {
constexpr size_t final_record_offset=2*ring_next::wire::slot+2560;
constexpr uint32_t final_record_magic=0x52464331;
struct FinalRecord {
 uint32_t magic=final_record_magic,version=1,bytes=360,stage=0;
 uint64_t published_sequence=0;
 ring_next::wire::RowMeta row;
 live_draft::Handoff hidden;
};
static_assert(sizeof(FinalRecord)==360&&offsetof(FinalRecord,published_sequence)==16&&offsetof(FinalRecord,row)==24&&offsetof(FinalRecord,hidden)==248);
static_assert(final_record_offset+sizeof(FinalRecord)<=live_draft::hidden_offset);
inline void validate_final_record(const FinalRecord& r,const ring_next::wire::Context& c,std::span<const uint8_t> raw){
 using ring_next::need;namespace w=ring_next::wire;w::context(c);
 need(r.magic==final_record_magic&&r.version==1&&r.bytes==sizeof r&&r.stage==uint32_t(c.stages-1)&&r.published_sequence>0&&r.published_sequence<=INT32_MAX,"recursive final record header/stage");
 const auto& row=r.row;const auto& h=r.hidden;live_draft::validate(h,c.stream_bytes,c.stages,c.vocab);
 need(row.magic==0x52494e47&&row.version==1&&row.bytes==sizeof row&&row.flags==0&&row.dtype==1&&std::all_of(row.reserved.begin(),row.reserved.end(),[](auto b){return !b;}),"recursive final row header");
 need(row.epoch==c.epoch&&row.request==c.request&&row.id>row.parent&&row.id>0&&row.owner==c.stages-1&&row.final==1&&row.source==-1&&!row.source_ticket&&!row.payload_bytes&&row.payload_sha==w::digest({}),"recursive final row ownership");
 need(row.position==h.position&&row.token==h.input_token&&row.fixture>=0&&bool(row.fixture)==bool(h.head)&&row.publication_ticket==h.row_ticket&&r.published_sequence==uint64_t(h.commit_sequence),"recursive final committed identity");
 need(row.after==ring_next::extend(row.before,uint32_t(row.position),uint32_t(row.token)),"recursive final prefix");
 need(raw.size()==size_t(c.stream_bytes),"recursive final full hidden extent");const auto sha=w::digest(raw);constexpr char digits[]="0123456789abcdef";
 for(size_t i=0;i<sha.size();++i)need(h.hidden_sha256[2*i]==digits[sha[i]>>4]&&h.hidden_sha256[2*i+1]==digits[sha[i]&15],"recursive final hidden SHA");
}
inline uint64_t published(const uint8_t* shared){auto* p=reinterpret_cast<const uint64_t*>(shared+final_record_offset+offsetof(FinalRecord,published_sequence));return __atomic_load_n(p,__ATOMIC_ACQUIRE);}
inline void invalidate(uint8_t* shared){auto* p=reinterpret_cast<uint64_t*>(shared+final_record_offset+offsetof(FinalRecord,published_sequence));__atomic_store_n(p,uint64_t(0),__ATOMIC_RELEASE);}
inline void publish(uint8_t* shared,const FinalRecord& record){
 ring_next::need(record.published_sequence>0,"recursive final publication sequence");invalidate(shared);auto copy=record;copy.published_sequence=0;std::memcpy(shared+final_record_offset,&copy,sizeof copy);
 auto* p=reinterpret_cast<uint64_t*>(shared+final_record_offset+offsetof(FinalRecord,published_sequence));__atomic_store_n(p,record.published_sequence,__ATOMIC_RELEASE);
}
}
