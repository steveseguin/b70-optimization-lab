#pragma once
// Isolated CPU prototype. No enabled-by-default path and no model arithmetic.
#include <algorithm>
#include <array>
#include <cstdint>
#include <cstring>
#include <limits>
#include <memory>
#include <span>
#include <stdexcept>
#include <vector>

namespace ownrt {
class SparseRows {
 public:
  struct Key { uint64_t row; uint32_t table; };
  struct Entry { uint64_t row; uint32_t offset, table; };
  static_assert(sizeof(Entry)==16);
  struct Table { uint64_t rows; uint32_t row_bytes; };
 private:
  // Source authority is external: the admitted Weights/Model and held views.
  std::array<Table,2> tables_;
  std::unique_ptr<Entry[]> index_;
  std::unique_ptr<uint8_t[]> payload_;
  size_t slots_, payload_capacity_, count_=0, used_=0;
  bool published_=false;
  static void need(bool ok,const char* why) {if(!ok)throw std::runtime_error(why);}
  static bool less(const Entry&a,const Entry&b) {
    return a.table<b.table || (a.table==b.table && a.row<b.row);
  }
 public:
  SparseRows(std::array<Table,2> tables,size_t total_bound,size_t max_entries)
    :tables_(tables),slots_(max_entries) {
    need(max_entries && total_bound>sizeof(*this),"sparse total bound");
    need(max_entries<=(total_bound-sizeof(*this))/sizeof(Entry),"sparse index bound");
    payload_capacity_=total_bound-sizeof(*this)-max_entries*sizeof(Entry);
    need(payload_capacity_ && payload_capacity_<=UINT32_MAX,"sparse payload bound");
    for(auto t:tables_)need(t.rows && t.row_bytes && t.rows<=UINT64_MAX/t.row_bytes,"sparse table shape");
    index_=std::make_unique<Entry[]>(slots_);
    payload_=std::make_unique<uint8_t[]>(payload_capacity_);
  }
  size_t owned_bytes() const {return sizeof(*this)+slots_*sizeof(Entry)+payload_capacity_;}
  size_t entries() const {return published_?count_:0;}
  size_t packed_bytes() const {return published_?used_:0;}
  void clear() {published_=false;count_=used_=0;}
  // keys is caller-owned bounded lookahead, never retained. No shadow index,
  // growing map, staging scratch, or simultaneous old/new payload allocation.
  // read_into(table, offset, bytes, destination) must use admitted source.
  template<class Verify,class ReadInto>
  void stage(std::span<const Key> keys,Verify verify,ReadInto read_into) {
    clear();verify();
    // Deliberately refuse overlarge submitted lists even if duplicate-heavy.
    need(keys.size()<=slots_,"sparse submitted-key bound");
    for(auto k:keys) {
      need(k.table<tables_.size() && k.row<tables_[k.table].rows,"sparse unknown row/table");
      index_[count_++]={k.row,0,k.table};
    }
    std::sort(index_.get(),index_.get()+count_,less);
    count_=std::unique(index_.get(),index_.get()+count_,[](auto a,auto b){return a.table==b.table&&a.row==b.row;})-index_.get();
    for(size_t i=0;i<count_;++i) {
      const auto rb=tables_[index_[i].table].row_bytes;
      need(rb<=payload_capacity_-used_,"sparse packed bound");
      index_[i].offset=uint32_t(used_);used_+=rb;
    }
    // Contiguous rows coalesce without reading gaps or allocating scratch.
    for(size_t i=0;i<count_;) {
      size_t end=i+1;auto t=index_[i].table;size_t bytes=tables_[t].row_bytes;
      while(end<count_ && index_[end].table==t && index_[end].row==index_[end-1].row+1 &&
            bytes+tables_[t].row_bytes<=4u*1024*1024) {bytes+=tables_[t].row_bytes;++end;}
      read_into(t,index_[i].row*tables_[t].row_bytes,bytes,payload_.get()+index_[i].offset);
      i=end;
    }
    verify();published_=true;
  }
  // Exactly the existing Weights::read bytes interface; a request partly
  // crossing a missing row falls back in full, never returns partial data.
  template<class Verify,class Fallback>
  std::vector<uint8_t> read(uint32_t table,size_t off,size_t n,Verify verify,Fallback fallback) const {
    need(table<tables_.size() && n && n<=4u*1024*1024,"sparse bounded read/table");
    auto shape=tables_[table];uint64_t bytes=shape.rows*shape.row_bytes;
    need(off<=bytes && n<=bytes-off,"sparse read bounds");verify();
    if(!published_) {auto result=fallback();verify();return result;}
    const auto first=off/shape.row_bytes,last=(off+n-1)/shape.row_bytes;
    auto begin=std::lower_bound(index_.get(),index_.get()+count_,Entry{first,0,table},less);
    auto end=begin;
    for(uint64_t row=first;row<=last;++row) {
      if(end==index_.get()+count_ || end->table!=table || end->row!=row) {
        auto result=fallback();verify();return result;
      }
      ++end;
    }
    const uint8_t* src=payload_.get()+begin->offset+off%shape.row_bytes;
    std::vector<uint8_t> result(src,src+n);verify();return result;
  }
};
} // namespace ownrt
