#pragma once
#include "pipeline/recursive_provider/final_event.hpp"
namespace ownrt::recursive_provider {
// An independently published stage0 ACCEPT, not a controller assertion. The
// stage0 ACCEPT fence keeps this record stable until provider completion.
constexpr size_t seed_record_offset=2*ring_next::wire::slot+3072;
constexpr uint32_t seed_record_magic=0x52534331;
struct SeedRecord {
 uint32_t magic=seed_record_magic,version=1,bytes=256,stage=0;
 uint64_t published_sequence=0;
 int32_t physical=0,committed=0;
 ring_next::wire::RowMeta row;
};
static_assert(sizeof(SeedRecord)==256&&offsetof(SeedRecord,published_sequence)==16&&offsetof(SeedRecord,row)==32);
static_assert(final_record_offset+sizeof(FinalRecord)<=seed_record_offset&&seed_record_offset+sizeof(SeedRecord)<=live_draft::hidden_offset);
inline ring_next::Row seed_row(const SeedRecord& r,const ring_next::wire::Context& provider){
 namespace w=ring_next::wire;using ring_next::need;w::context(provider);
 need(r.magic==seed_record_magic&&r.version==1&&r.bytes==sizeof r&&r.stage==0&&r.published_sequence>0&&r.published_sequence<=INT32_MAX,"seed journal header/owner/marker");
 need(r.row.publication_ticket>0&&uint64_t(r.row.publication_ticket)<r.published_sequence,"seed journal original ROW/ACCEPT tickets");
 auto c=provider;c.stage=0;auto m=r.row;const int ticket=m.publication_ticket;m.publication_ticket=0;
 w::Command accept{w::accept_op,m.token,m.position,m.fixture,ticket,int(r.published_sequence),0,0};
 const auto row=w::resolution(m,accept,c);
 need(r.committed==row.position+1&&r.physical>=r.committed&&r.physical-r.committed<=2,"seed journal accepted target frontier");
 return row;
}
inline uint64_t seed_published(const uint8_t* shared){auto* p=reinterpret_cast<const uint64_t*>(shared+seed_record_offset+offsetof(SeedRecord,published_sequence));return __atomic_load_n(p,__ATOMIC_ACQUIRE);}
inline void publish_seed(uint8_t* shared,const SeedRecord& record){
 ring_next::need(record.published_sequence>0,"seed journal publication sequence");
 auto* marker=reinterpret_cast<uint64_t*>(shared+seed_record_offset+offsetof(SeedRecord,published_sequence));
 __atomic_store_n(marker,uint64_t(0),__ATOMIC_RELEASE);auto owned=record;owned.published_sequence=0;
 std::memcpy(shared+seed_record_offset,&owned,sizeof owned);__atomic_store_n(marker,record.published_sequence,__ATOMIC_RELEASE);
}
}
