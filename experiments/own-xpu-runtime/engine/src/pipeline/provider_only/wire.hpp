#pragma once
#include "pipeline/provider_only/owner.hpp"
#include <array>
#include <cstdint>
namespace ownrt::provider_only::wire {
constexpr int32_t magic=0x50525631,version=1;
constexpr size_t shared_bytes=4*65536+4096+64,proposal_offset=4096,reset_offset=512,capture_offset=768;
constexpr int canonical_op=9,batch_op=27,reset_op=11,dump_op=4,finish_op=5;
struct Request {int32_t op=0,token=0,position=0,fixture=0,depth=0,sequence=0,role=magic,version_=version;};
struct Reply {int32_t status=0,token=-1,error=0,bytes=0,sequence=0,rank=-1,role=magic,version_=version;double busy_ms=0,gpu_ms=0,redo_ms=0,reserved_ms=0;};
static_assert(sizeof(Request)==32&&sizeof(Reply)==64);
struct Header {
 uint32_t magic_=magic,version_=version,bytes=128,source_mode=0;
 uint32_t stream_bytes=0,target_stages=0,depth=0,reserved=0;
 uint64_t epoch=0;
 ring_next::Digest request{};
 std::array<uint8_t,56> zero{};
};
static_assert(sizeof(Header)==128);
struct Reset {
 uint32_t magic_=magic,version_=version,bytes=64,sequence=0;
 uint64_t epoch=0;
 ring_next::Digest request{};
 std::array<uint8_t,8> zero{};
};
static_assert(sizeof(Reset)==64);
inline void command(const Request& request,int next){
 ring_next::need(request.role==magic&&request.version_==version&&request.sequence==next&&next>0,
   "dedicated MTP command role/version/sequence");
 ring_next::need(request.op==28||request.op==canonical_op||request.op==batch_op||request.op==reset_op||
   request.op==dump_op||request.op==finish_op,"dedicated MTP operation refused");
}
} // namespace ownrt::provider_only::wire
