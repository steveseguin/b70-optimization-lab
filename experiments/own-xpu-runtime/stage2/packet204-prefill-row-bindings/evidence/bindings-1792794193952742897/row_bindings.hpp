#pragma once
// Metadata contract only. No allocation, native submission, wait, or pointer mutation.
#include "../packet202-prefill-chunk-prep/chunk_plan.hpp"
#include <array>
#include <bit>
#include <cstdint>
#include <map>
#include <span>
#include <string>
#include <vector>

namespace p204 {
inline void require(bool v, const char* why) { if(!v) throw std::invalid_argument(why); }
enum class Scalar { bf16, i32, u32, i64, opaque };
enum class Lifetime { persistent, shared_scratch, immutable, global_control };
struct Region {
  uint64_t allocation; size_t offset, bytes, allocation_bytes;
  Scalar scalar;
  bool operator==(const Region&) const = default;
};
inline void valid(const Region& r) {
  require(r.allocation && r.bytes && r.offset<=r.allocation_bytes &&
          r.bytes<=r.allocation_bytes-r.offset,"invalid arena region extent");
  size_t alignment = r.scalar==Scalar::i64?8:r.scalar==Scalar::bf16?2:
                     r.scalar==Scalar::opaque?1:4;
  require(r.offset%alignment==0 && r.bytes%alignment==0,"typed region alignment");
}
inline bool overlaps(const Region& a,const Region& b) {
  valid(a); valid(b);
  return a.allocation==b.allocation && a.offset<b.offset+b.bytes && b.offset<a.offset+a.bytes;
}
struct Shared { Region region; Lifetime lifetime; };
struct History { int64_t old0,old1; bool operator==(const History&) const=default; };
struct Row {
  uint32_t position; int32_t token;
  History before,after;
  Region streams, token_control, position_control, embedding, ple_lookup, ple_ids, routes;
};
// Existing native history sentinel is EOS only; im_end is not the sentinel.
inline std::array<int64_t,16> ple_ids(int32_t token,History h,int64_t eos,
                                     const std::array<int64_t,35>& metadata) {
  require(token>=0 && token<248320,"token vocabulary bound");
  if(h.old1==eos)h.old0=eos;
  std::array<int64_t,16> out{};
  for(int n=2;n<=3;++n) {
    uint64_t bits=uint64_t(token)*uint64_t(metadata[0]);
    bits^=uint64_t(h.old1)*uint64_t(metadata[1]);
    if(n==3)bits^=uint64_t(h.old0)*uint64_t(metadata[2]);
    auto value=std::bit_cast<int64_t>(bits);
    for(int j=0;j<8;++j) {
      const int i=(n-2)*8+j; const auto size=metadata[3+i],offset=metadata[19+i];
      // Avoid signed-overflow UB while retaining native mathematical remainder.
      require(size>0 && size<=INT64_MAX/2 && offset>=0 && offset<=INT64_MAX-size,
              "PLE metadata range");
      out[i]=(value%size+size)%size+offset;
    }
  }
  return out;
}
struct Required { size_t bytes; Scalar scalar; Lifetime lifetime; };
inline std::map<std::string,Required> persistent_requirements(size_t context) {
  require(context>0 && context<=4096,"context bound");
  std::map<std::string,Required> out;
  auto add=[&](std::string n,size_t b,Scalar t=Scalar::bf16){out.emplace(n,Required{b,t,Lifetime::persistent});};
  add("token_history",16,Scalar::i64); add("blk.1.ple.history",4*2560*9*2);
  for(int l=0;l<48;++l) {
    auto n="blk."+std::to_string(l)+".";
    if(l%4==3) {
      add(n+"qsa.keys",context*1024); add(n+"qsa.values",context*1024);
      add(n+"qsa.raw",context*256); add(n+"qsa.pooled",((context+3)/4)*256);
    } else {add(n+"gdn.history",10240*3*2);add(n+"gdn.state",48*128*128*2);}
  }
  return out;
}
class Bindings {
  std::vector<Row> rows_;
  std::map<std::string,Shared> shared_;
  size_t context_,visible_;
public:
  // Caller must supply complete named Engine inventory and attest that distinct
  // allocation IDs refer to disjoint arena storage. This class cannot inspect an Engine.
  Bindings(std::vector<Row> rows,std::map<std::string,Shared> shared,
           size_t context,size_t visible):rows_(std::move(rows)),shared_(std::move(shared)),context_(context),visible_(visible) {
    require(!rows_.empty() && rows_.size()<=2,"one/two rows only");
    auto plan=p202::make_plan(rows_[0].position,visible,context,rows_.size());
    require(!plan.spans.empty() && plan.spans[0].count==rows_.size(),"nonfinal chunk/capacity boundary");
    auto required=persistent_requirements(context);
    required.emplace("active",Required{4,Scalar::u32,Lifetime::global_control});
    required.emplace("error",Required{4,Scalar::u32,Lifetime::global_control});
    required.emplace("global_position",Required{4,Scalar::u32,Lifetime::global_control});
    required.emplace("ple_metadata",Required{280,Scalar::i64,Lifetime::immutable});
    for(const auto& [n,r]:required) {
      auto it=shared_.find(n);require(it!=shared_.end(),"missing shared binding");
      require(it->second.region.bytes==r.bytes && it->second.region.scalar==r.scalar && it->second.lifetime==r.lifetime,"shared binding type/extent/lifetime");
    }
    std::vector<Region> occupied;
    std::map<uint64_t,size_t> allocation_extents;
    auto add=[&](const Region& r) {
      valid(r);auto [i,new_id]=allocation_extents.emplace(r.allocation,r.allocation_bytes);
      require(new_id || i->second==r.allocation_bytes,"inconsistent allocation extent");
      for(const auto& old:occupied)require(!overlaps(old,r),"live region alias");
      occupied.push_back(r);
    };
    for(const auto& [name,s]:shared_) {
      require(s.lifetime!=Lifetime::persistent || required.count(name),"unclassified/duplicated persistent state");
      add(s.region);
    }
    for(size_t i=0;i<rows_.size();++i) {
      const auto& r=rows_[i];require(r.position==rows_[0].position+i && r.token>=0 && r.token<248320,"row position/token");
      require(r.after==History{r.before.old1,r.token},"row history transition");
      if(i)require(r.before==rows_[i-1].after,"row history chain");
      auto exact=[&](const Region& x,size_t bytes,Scalar scalar){require(x.bytes==bytes && x.scalar==scalar,"row binding type/extent");add(x);};
      exact(r.streams,20480,Scalar::bf16);exact(r.token_control,4,Scalar::i32);
      exact(r.position_control,4,Scalar::u32);exact(r.embedding,5120,Scalar::bf16);
      exact(r.ple_lookup,5120,Scalar::bf16);exact(r.ple_ids,128,Scalar::i64);
      exact(r.routes,5760,Scalar::opaque);
    }
  }
  const Row& row(size_t i)const{return rows_.at(i);}
  const Shared& shared(const std::string& name)const{return shared_.at(name);}
  size_t count()const{return rows_.size();}
  size_t context()const{return context_;}
  size_t context_extent()const{return std::min(context_,size_t((rows_[0].position/32+1)*32));}
};
struct Commit { uint32_t position; History history; size_t streams_row; };
// Queue-event ordinals below are supplied by the future native adapter. Their
// ordering is checked; these integers do NOT establish actual completion.
class Schedule {
  const Bindings& b_; size_t next_=0; uint64_t last_=0,dependency_=0; bool leased_=false,poisoned_=false,committed_=false;
public:
  explicit Schedule(const Bindings& b):b_(b){}
  void begin(size_t layer,size_t row,uint64_t dependency) {
    require(!poisoned_ && !committed_ && !leased_,"unavailable chunk");
    require(layer<48 && row<b_.count() && next_==layer*b_.count()+row,"causal row/layer order");
    require(dependency>=last_,"shared scratch missing dependency");dependency_=dependency;leased_=true;
  }
  void finish(uint64_t terminal_event,uint64_t routes_captured_event) {
    require(!poisoned_ && leased_ && terminal_event>dependency_ && routes_captured_event>=terminal_event,"lease/route capture event order");
    last_=routes_captured_event;leased_=false;++next_;
  }
  void fail() noexcept {poisoned_=true;}
  bool poisoned()const{return poisoned_;}
  bool publication_ready()const{return committed_ && !poisoned_;}
  uint64_t required_dependency()const{return last_;}
  Commit commit(uint64_t completed_through,bool sticky_error_clear,bool cache_readers_drained) {
    if(!sticky_error_clear){fail();throw std::invalid_argument("sticky device error");}
    require(!poisoned_ && !committed_ && !leased_ && next_==48*b_.count(),"partial/unavailable chunk commit");
    require(completed_through>=last_ && cache_readers_drained,"actual exit drain required");
    committed_=true;
    return {uint32_t(b_.row(0).position+b_.count()),b_.row(b_.count()-1).after,b_.count()-1};
  }
};
struct QsaView { size_t visible_tokens,completed_pools,tail_tokens,context_extent; };
inline QsaView qsa_view(size_t position,size_t context) {
  require(context>0 && context<=4096 && position<context,"QSA position/context");
  const auto visible=position+1;
  return {visible,visible/4,visible%4,std::min(context,((position/32)+1)*32)};
}
inline void validate_selected_ids(std::span<const int32_t> ids,size_t position,size_t context,size_t budget) {
  qsa_view(position,context);require(budget>0 && budget<=context && ids.size()==budget+3,"QSA ID storage bound");
  bool terminated=false;
  for(auto id:ids) {
    if(id==-1){terminated=true;continue;}
    require(!terminated && id>=0 && size_t(id)<=position && size_t(id)<context,"QSA noncausal/unterminated IDs");
  }
  // A full budget+3 buffer is legal without a sentinel (e.g. p2050,budget2048).
}
} // namespace p204
