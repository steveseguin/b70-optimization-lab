#pragma once
#include <array>
#include <cstdint>
#include <cstring>
#include <stdexcept>
#include <string>
// Shared-map transport only. Arithmetic and draft cache advancement stay in
// the qualified mtp36::DraftRuntime. No architecture dimensions in this ABI.
namespace ownrt::live_draft {
constexpr int32_t step_op=23,magic=0x4d545031,version=1;
constexpr size_t slot_bytes=65536,header_offset=2*slot_bytes+512,hidden_offset=2*slot_bytes+4096;
struct Handoff {
 int32_t magic_value=magic,version_value=version,bytes=0,position=-1,final_stage=-1,stages=0;
 int32_t row_ticket=0,commit_sequence=0,input_token=-1,next_token=-1,head=0,reserved=0;
 std::array<char,64> hidden_sha256{};
};
static_assert(sizeof(Handoff)==112);
inline void check(bool yes,const char* message){if(!yes)throw std::runtime_error(message);}
inline void validate(const Handoff& h,int expected_bytes,int stage_count,int vocabulary){
 check(h.magic_value==magic&&h.version_value==version&&h.reserved==0,"live draft handoff version");
 check(expected_bytes>0&&expected_bytes<=int(slot_bytes)&&expected_bytes%4==0&&h.bytes==expected_bytes,"live draft hidden extent");
 check(stage_count>0&&h.stages==stage_count&&h.final_stage==stage_count-1,"live draft final-stage identity");
 check(h.position>=0&&h.row_ticket>0&&h.commit_sequence>h.row_ticket,"live draft committed ticket identity");
 check(h.input_token>=0&&h.input_token<vocabulary&&(h.head==0||h.head==1),"live draft input identity");
 check(h.head?(h.next_token>=0&&h.next_token<vocabulary):h.next_token==-1,"live draft target output identity");
 for(char c:h.hidden_sha256)check((c>='0'&&c<='9')||(c>='a'&&c<='f'),"live draft hidden SHA256 encoding");
}
class Sequence {
 int next_position_=1,last_commit_=0;
public:
 int next_position()const{return next_position_;}
 void admit(const Handoff& h,int position,int token,int head,int vocabulary)const{
  check(position==next_position_&&h.position==position-1&&h.commit_sequence>last_commit_,"live draft stale/noncontiguous parent");
  check((head==0||head==1)&&token>=0&&token<vocabulary&&(!h.head||token==h.next_token),"live draft confirmed token/head mismatch");
 }
 void complete(const Handoff& h,int actual_position){
  check(actual_position==next_position_&&h.position==next_position_-1,"live draft canonical advancement");
  last_commit_=h.commit_sequence;++next_position_;
 }
};
}
