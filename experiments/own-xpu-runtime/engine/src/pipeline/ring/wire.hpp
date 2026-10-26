#pragma once
#include "stage_ring.hpp"
#include <bit>
#include <cstddef>
#include <cstring>
#include <span>
namespace ownrt::ring_next::wire {
static_assert(std::endian::native==std::endian::little,"ring wire requires admitted little-endian host");
constexpr size_t slot=65536,row_offset=2*slot+1024,proposal_offset=2*slot+1536,ack_offset=2*slot+2048;
constexpr int row_op=24,accept_op=25,abort_op=26,batch_op=27;
constexpr uint32_t tentative=1,published=2;
struct RowMeta {
 uint32_t magic=0x52494e47,version=1,bytes=224,flags=0;
 uint64_t epoch=0,id=0,parent=0;
 int32_t position=0,token=0,fixture=0,owner=0,final=0,source=-1,source_ticket=0,publication_ticket=0,payload_bytes=0,dtype=1;
 Digest request{},before{},after{},payload_sha{};std::array<uint8_t,16> reserved{};
};
struct Ack {
 uint32_t magic=0x5241434b,version=1,bytes=128,flags=0;
 uint64_t epoch=0,id=0,discarded0=0,discarded1=0;
 int32_t owner=0,sequence=0,row_ticket=0,physical=0,committed=0,discard_count=0,pending=0,error=0;
 std::array<uint8_t,48> reserved{};
};
struct ProposalMeta {
 uint32_t magic=0x44525032,version=1,bytes=192,flags=0;
 uint64_t epoch=0,ticket=0,seed_row=0,parent_row=0,final_commit=0,provider_serial=0;
 int32_t seed_position=0,restored_position=0,requested_depth=2,available_depth=0,guess0=-1,guess1=-1,error=0,restored=0;
 Digest request{},seed_prefix{},hidden_sha{};
};
static_assert(sizeof(RowMeta)==224&&offsetof(RowMeta,epoch)==16&&offsetof(RowMeta,position)==40&&offsetof(RowMeta,request)==80&&offsetof(RowMeta,payload_sha)==176);
static_assert(sizeof(Ack)==128&&offsetof(Ack,epoch)==16&&offsetof(Ack,owner)==48);
static_assert(sizeof(ProposalMeta)==192&&offsetof(ProposalMeta,epoch)==16&&offsetof(ProposalMeta,seed_position)==64&&offsetof(ProposalMeta,request)==96);
static_assert(row_offset+sizeof(RowMeta)<=proposal_offset&&proposal_offset+sizeof(ProposalMeta)<=ack_offset&&ack_offset+sizeof(Ack)<2*slot+4096);
struct ProposalMetaV2 {ProposalMeta base;int32_t guess2=-1;std::array<uint8_t,28> reserved{};};
static_assert(sizeof(ProposalMetaV2)==224&&offsetof(ProposalMetaV2,guess2)==192&&proposal_offset+sizeof(ProposalMetaV2)<=ack_offset);
struct Command {int op=0,token=0,position=0,fixture=0,speculative=0,sequence=0,stage=0,final=0;};
struct Context {uint64_t epoch=0;Digest request{};int stage=0,stages=0,stream_bytes=0,vocab=0,depth=2;};
inline Digest digest(std::span<const uint8_t> bytes){Digest out{};SHA256(bytes.data(),bytes.size(),out.data());return out;}
template<class T>T read(std::span<const uint8_t> bytes){need(bytes.size()==sizeof(T),"ring exact wire extent");T out;std::memcpy(&out,bytes.data(),sizeof out);return out;}
template<class T>void write(std::span<uint8_t> bytes,const T& value){need(bytes.size()==sizeof(T),"ring exact publication extent");std::memcpy(bytes.data(),&value,sizeof value);}
inline void context(const Context& c){need((c.depth==2||c.depth==3)&&c.stages>0&&c.stage>=0&&c.stage<c.stages&&c.stream_bytes>0&&c.stream_bytes<=int(slot)&&c.stream_bytes%4==0&&c.vocab>0,"ring wire context");}
inline void base(const RowMeta& m,const Command& command,const Context& c){
 context(c);need(m.magic==0x52494e47&&m.version==1&&m.bytes==sizeof m&&(m.flags&~tentative)==0&&m.dtype==1,"ring wire header version/flags/type");
 need(std::all_of(m.reserved.begin(),m.reserved.end(),[](auto x){return x==0;}),"ring wire reserved padding");
 need(m.epoch==c.epoch&&m.request==c.request&&m.id>0&&m.id>m.parent,"ring wire request/global lineage");
 need(command.sequence>0&&command.stage==c.stage&&command.final==int(c.stage==c.stages-1)&&m.owner==c.stage&&m.final==command.final,"ring wire stage/sequence identity");
 need(m.position==command.position&&m.position>=0&&m.token==command.token&&m.token>=0&&m.token<c.vocab&&m.fixture==command.fixture&&m.fixture>=0&&m.publication_ticket==0,"ring wire row identity");
 need(m.after==extend(m.before,uint32_t(m.position),uint32_t(m.token)),"ring wire token prefix hash");
}
inline Row row(const RowMeta& m,const Command& command,const Context& c,std::span<const uint8_t> payload){
 base(m,command,c);need(command.op==row_op&&(command.speculative==0||command.speculative==1)&&m.flags==uint32_t(command.speculative),"ring row operation/tentative flag");
 if(c.stage==0)need(m.source==-1&&m.source_ticket==0&&m.payload_bytes==0&&payload.empty(),"ring first-stage input ownership");
 else need(m.source==c.stage-1&&m.source_ticket>0&&m.payload_bytes==c.stream_bytes&&payload.size()==size_t(c.stream_bytes),"ring full upstream stream ownership");
 need(m.payload_sha==digest(payload),"ring input stream SHA256");
 return {m.epoch,m.id,m.parent,command.sequence,m.position,m.token,m.fixture,bool(m.flags&tentative),m.request,m.before,m.after};
}
inline Row resolution(const RowMeta& m,const Command& command,const Context& c){
 base(m,command,c);need((command.op==accept_op||command.op==abort_op)&&command.speculative>0&&command.speculative<command.sequence,"ring resolution original ROW ticket");
 need(m.source==-1&&m.source_ticket==0&&m.payload_bytes==0&&m.payload_sha==digest({}),"ring resolution has no input payload");
 return {m.epoch,m.id,m.parent,command.speculative,m.position,m.token,m.fixture,bool(m.flags&tentative),m.request,m.before,m.after};
}
inline RowMeta publication(RowMeta input,int sequence,std::span<const uint8_t> output){need(sequence>0&&output.size()<=slot,"ring publication bound");input.flags|=published;input.publication_ticket=sequence;input.payload_bytes=int32_t(output.size());input.payload_sha=digest(output);return input;}
inline void validate_publication(const RowMeta& actual,const RowMeta& submitted,int sequence,const Context& c,std::span<const uint8_t> output){
 context(c);need(output.size()==size_t(c.stage==c.stages-1?0:c.stream_bytes),"ring complete publication extent");
 const auto expected=publication(submitted,sequence,output);
 need(std::memcmp(&actual,&expected,sizeof actual)==0,"ring exact output publication owner/lineage/ticket/SHA");
}
inline Ack acknowledgment(const Context& c,int sequence,const Row& row,const Resolution& r,bool byte_checked){
 context(c);need(sequence>row.ticket&&r.discarded.size()<=size_t(c.depth)&&r.pending>=0&&r.pending<=c.depth&&r.physical>=r.committed,"ring resolution acknowledgment bounds");
 Ack a;a.version=c.depth==3?2:1;a.epoch=c.epoch;a.id=row.id;a.owner=c.stage;a.sequence=sequence;a.row_ticket=row.ticket;a.physical=r.physical;a.committed=r.committed;a.pending=r.pending;
 a.discard_count=int32_t(r.discarded.size());if(a.discard_count)a.discarded0=r.discarded[0];if(a.discard_count>=2)a.discarded1=r.discarded[1];if(a.discard_count==3)std::memcpy(a.reserved.data(),&r.discarded[2],8);a.flags=byte_checked?1:0;
 if(a.discard_count)need(a.discarded0==row.id&&a.physical==a.committed&&a.pending==0,"ring suffix acknowledgment identity");return a;
}
inline uint64_t third_discard(const Ack& a){uint64_t out=0;std::memcpy(&out,a.reserved.data(),8);return out;}
inline void validate_ack(const Ack& a,const Context& c,int sequence,const Row& row,const std::vector<uint64_t>& expected_discarded){
 context(c);need(a.magic==0x5241434b&&a.version==uint32_t(c.depth==3?2:1)&&a.bytes==sizeof a&&(a.flags&~1u)==0&&std::all_of(a.reserved.begin()+(c.depth==3?8:0),a.reserved.end(),[](auto x){return !x;}),"ring ACK header");
 need(a.epoch==c.epoch&&a.id==row.id&&a.owner==c.stage&&a.sequence==sequence&&a.row_ticket==row.ticket&&a.sequence>row.ticket&&!a.error,"ring ACK owner/ticket");
 need(a.discard_count>=0&&a.discard_count<=c.depth&&size_t(a.discard_count)==expected_discarded.size()&&a.pending>=0&&a.pending<=c.depth&&a.committed>=0&&a.physical>=a.committed,"ring ACK cursors/count");
 need(a.discarded0==(expected_discarded.empty()?0:expected_discarded[0])&&a.discarded1==(expected_discarded.size()<2?0:expected_discarded[1]),"ring ACK exact suffix IDs");
 need(third_discard(a)==(expected_discarded.size()<3?0:expected_discarded[2]),"ring ACK exact third suffix ID");
 need(a.discard_count||a.flags==0,"ring ACCEPT cannot claim a restore check");
 if(!a.discard_count)need(a.committed==row.position+1&&a.pending<c.depth&&a.physical==a.committed+a.pending,"ring ACK exact accept cursors");
 else need(expected_discarded[0]==row.id&&(expected_discarded.size()<2||expected_discarded[1]>row.id)&&(expected_discarded.size()<3||expected_discarded[2]>expected_discarded[1]),"ring ACK expected suffix lineage");
 if(c.stage==c.stages-1)need(!a.discard_count&&!a.pending,"ring final ACK cannot restore or retain suffix");
 if(a.discard_count)need(a.physical==row.position&&a.committed==row.position&&a.pending==0,"ring ACK restored frontier");
}
struct BatchIdentity {uint64_t seed_row=0,parent_row=0,final_commit=0,provider_serial=0;};
inline void validate_batch_base(const ProposalMeta& b,const Context& c,int expected_ticket,int seed_position,const Digest& seed,const Digest& hidden,const BatchIdentity& expected){
 context(c);need(b.magic==0x44525032&&b.version==uint32_t(c.depth==3?2:1)&&b.bytes==uint32_t(c.depth==3?sizeof(ProposalMetaV2):sizeof(ProposalMeta))&&(b.flags&~3u)==0,"ring proposal header");
 need(b.epoch==c.epoch&&b.request==c.request&&b.ticket==uint64_t(expected_ticket)&&expected_ticket>0&&b.seed_row>b.parent_row&&b.parent_row>0&&b.final_commit>0&&b.provider_serial>0,"ring proposal owner/seed identity");
 need(b.seed_row==expected.seed_row&&b.parent_row==expected.parent_row&&b.final_commit==expected.final_commit&&b.provider_serial==expected.provider_serial,"ring proposal exact canonical handoff/provider identity");
 need(b.seed_position==seed_position&&seed_position>0&&b.restored_position==seed_position&&b.seed_prefix==seed&&b.hidden_sha==hidden,"ring proposal canonical seed");
 need(b.requested_depth==c.depth&&b.available_depth>=0&&b.available_depth<=c.depth&&!b.error&&b.restored==1&&(b.flags&2),"ring proposal restoration/depth");
 need((b.flags&1)?b.available_depth>=1:b.available_depth==0,"ring proposal head mask");
 need(b.available_depth>0?(b.guess0>=0&&b.guess0<c.vocab):b.guess0==-1,"ring first guess bounds");
 need(b.available_depth>1?(b.guess1>=0&&b.guess1<c.vocab):b.guess1==-1,"ring second guess bounds");
}
inline void validate_batch(const ProposalMeta& b,const Context& c,int ticket,int position,const Digest& seed,const Digest& hidden,const BatchIdentity& expected){
 need(c.depth==2,"v1 batch validator requires depth2");validate_batch_base(b,c,ticket,position,seed,hidden,expected);
}
inline void validate_batch(const ProposalMetaV2& b,const Context& c,int ticket,int position,const Digest& seed,const Digest& hidden,const BatchIdentity& expected){
 need(c.depth==3&&std::all_of(b.reserved.begin(),b.reserved.end(),[](auto x){return x==0;}),"v2 batch depth/reserved");validate_batch_base(b.base,c,ticket,position,seed,hidden,expected);
 need(b.base.available_depth>2?(b.guess2>=0&&b.guess2<c.vocab):b.guess2==-1,"ring third guess bounds");
}

}
