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
namespace pipeline::prefill {
constexpr uint32_t magic=0x31465050u; // "PPF1"
constexpr uint32_t version=1;
constexpr int32_t op=15;              // rank command: token = rows, position = first position, fixture = buffer index
constexpr size_t header_bytes=4096;
constexpr int max_rows=256;            // header tokens fit the 4096-byte page (16 + 4*256 bytes); the row regions follow it
struct Header {uint32_t magic,version,rows,stream_bytes;int32_t tokens[max_rows];};
static_assert(sizeof(Header)<=header_bytes);
inline size_t bytes(size_t rows,size_t stream){return header_bytes+4*rows*stream;}
inline uint8_t* forward(uint8_t* base,int index,size_t rows,size_t stream){return base+header_bytes+size_t(index)*rows*stream;}
inline uint8_t* reverse(uint8_t* base,int index,size_t rows,size_t stream){return base+header_bytes+size_t(2+index)*rows*stream;}
}
