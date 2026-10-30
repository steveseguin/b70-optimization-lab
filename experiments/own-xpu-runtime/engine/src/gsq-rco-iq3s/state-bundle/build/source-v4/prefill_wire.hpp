#pragma once
// Batched-prefill transport between the two ranks: a separate, versioned shared map (--prefill-shared). The original
// fixed shared map (slots, MTP publication, reverse slot, probe) is unchanged.
//
// Layout: one 4096-byte header page, then four row regions of `rows` stream rows each:
//   forward[0], forward[1]  rank 0's layer-23 output rows for even/odd chunks (double-buffered: rank 0 writes
//                           chunk k+1 while rank 1 reads chunk k);
//   reverse[0], reverse[1]  rank 1's final-layer rows for even/odd chunks, which rank 0 feeds to the MTP draft.
// The service creates the file at its exact size and writes the header. Ranks verify every field before use.
#include <cstddef>
#include <cstdint>
#include <cstdlib>
namespace pipeline::prefill {
constexpr uint32_t magic=0x31465050u; // "PPF1"
constexpr uint32_t version=1;
constexpr int32_t op=15;              // rank command: token = rows, position = first position, fixture = buffer index
constexpr size_t header_bytes=4096;
constexpr int max_rows=256;            // header tokens fit the 4096-byte page (16 + 4*256 bytes); the row regions follow it
struct Header {uint32_t magic,version,rows,stream_bytes;int32_t tokens[max_rows];};
static_assert(sizeof(Header)<=header_bytes);
// V2 changes host transport capacity only; operator rows and device shadows are unchanged.
struct HeaderV2 {uint32_t magic,version,rows,stream_bytes,header_bytes,slots,reserved0,reserved1;int32_t tokens[max_rows];};
constexpr size_t header_bytes_v2=8192;
static_assert(sizeof(HeaderV2)<1536);
inline bool valid_slots(int slots){return slots==2||slots==4;}
inline size_t header_size(int slots){return slots==4?header_bytes_v2:header_bytes;}
inline uint32_t transport_version(int slots){return slots==4?2:version;}
inline bool valid_header(const uint8_t* base,size_t rows,size_t stream,int slots){
 if(!valid_slots(slots)||(slots==4&&rows!=256))return false;
 const auto& h=*reinterpret_cast<const Header*>(base);
 if(h.magic!=magic||h.version!=transport_version(slots)||h.rows!=rows||h.stream_bytes!=stream)return false;
 if(slots==4){const auto& v=*reinterpret_cast<const HeaderV2*>(base);return v.header_bytes==header_bytes_v2&&v.slots==4&&!v.reserved0&&!v.reserved1;}
 return true;
}
inline const int32_t* tokens(const uint8_t* base,int slots){return slots==4?reinterpret_cast<const HeaderV2*>(base)->tokens:reinterpret_cast<const Header*>(base)->tokens;}
inline size_t bytes(size_t rows,size_t stream,int slots=2){return header_size(slots)+2*size_t(slots)*rows*stream;}
inline uint8_t* forward(uint8_t* base,int index,size_t rows,size_t stream,int slots=2){return base+header_size(slots)+size_t(index)*rows*stream;}
inline uint8_t* reverse(uint8_t* base,int index,size_t rows,size_t stream,int slots=2){return base+header_size(slots)+size_t(slots+index)*rows*stream;}
// Draft chunk replay (OWNRT_DRAFT_CHUNK_REPLAY=1, 2026-10-29, research/tp/prefill-speed-2026-10-29; default off): rank 0's
// MTP draft consumes one prefill chunk's confirmed rows in one command instead of one DRAFT command per row. Command
// draft_chunk_op: token = rows n, position = the chunk's first target position q0 (draft rows q0+1 .. q0+n, head off),
// fixture = the reverse buffer holding rank 1's final rows of positions q0 .. q0+n-1. The n confirmed tokens (of
// positions q0+1 .. q0+n) travel in the header page's unused tail (draft_tokens_offset), which no other reader uses.
constexpr int32_t draft_chunk_op=29;
constexpr size_t draft_tokens_offset=2048;
static_assert(sizeof(Header)<=draft_tokens_offset&&sizeof(HeaderV2)<=draft_tokens_offset&&draft_tokens_offset+4*size_t(max_rows)<=header_bytes);
inline int32_t* draft_tokens(uint8_t* base){return reinterpret_cast<int32_t*>(base+draft_tokens_offset);}
inline bool draft_chunk_replay(){static const bool on=[]{const char* e=std::getenv("OWNRT_DRAFT_CHUNK_REPLAY");return e&&e[0]=='1';}();return on;}
}
