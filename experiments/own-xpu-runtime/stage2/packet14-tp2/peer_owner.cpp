#include "owner.hpp"
namespace ownrt {
// Single-threaded, bounded, synchronous bridge. Both Arena rows remain live
// for the entire call. Source and destination must have drained producers.
// The destination ledger owns the copy event and is waited before returning;
// callers cannot retire/free either endpoint while this function executes.
void Device::peer_from(Device& source, Allocation dst,size_t dst_offset,
                       Allocation src,size_t src_offset,size_t bytes) {
  admit();source.admit();
  if(this==&source || in_flight() || source.in_flight() || !graphs_.empty() || !source.graphs_.empty())
    throw std::logic_error("peer bridge requires two drained eager owners");
  const auto& d=arena.row(dst);const auto& s=source.arena.row(src);
  if(!d.live || !s.live || d.memory!=Memory::device || s.memory!=Memory::device ||
     !bytes || dst_offset>d.bytes || bytes>d.bytes-dst_offset || src_offset>s.bytes || bytes>s.bytes-src_offset)
    throw std::invalid_argument("peer bridge extent/lifetime");
  events_.reserve(events_.size()+1);
  try {
    auto e=backend_->copy(static_cast<char*>(d.pointer)+dst_offset,
                          static_cast<const char*>(s.pointer)+src_offset,bytes,{});
    events_.push_back(e);
    if(!wait(e,std::chrono::seconds(60))) {
      fault_=source.fault_="peer bridge timeout; retain both endpoints";
      throw std::runtime_error(fault_);
    }
  } catch(const std::exception& error) {
    fault_=source.fault_=error.what();throw;
  }
}
}
