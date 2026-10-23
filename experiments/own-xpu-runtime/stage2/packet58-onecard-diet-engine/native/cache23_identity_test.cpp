// packet58-cache23 byte-identity proof for the `max` view (CPU, host-only, no device).
//
// The engine allocates ONE arena per load (23,049,601,024 bytes) and switches the usable
// extent at the drained view boundary: `max` = 21,552,729,600, `max23` = the whole arena.
// p58::Cache's decisions (fills, offsets, evictions, published table, resident bytes) must
// depend only on (base, capacity) and never on the allocation extent, so an A view inside the
// larger arena behaves byte-for-byte like packet182c's cache. This test replays the same
// synthetic route trace on (arena S, cap C) and (arena S + growth, cap C) and requires identical
// plans, fills, published tables and residency at every step; then shows cap = S + growth admits
// more (the max23 mechanism), and that the production literals are consistent.
#include "cache_table.hpp"
#include <array>
#include <cstdlib>
#include <cstring>
#include <functional>
#include <iostream>
#include <sstream>
static unsigned checks=0;
static void check(bool ok,const char* what){if(!ok)throw std::runtime_error(what);++checks;}
struct Trace{std::string log;size_t fills=0,fill_bytes=0,resident_peak=0;};
static Trace replay(uint64_t arena_bytes,uint64_t cap,const std::vector<std::array<unsigned char,256>>& host,unsigned steps){
  std::vector<p58::Expert> experts;
  for(size_t i=0;i<host.size();++i){auto p=uint64_t(host[i].data());experts.push_back({p,p+64,p+160,64,96,96});}
  auto* allocation=static_cast<unsigned char*>(std::aligned_alloc(256,arena_bytes));check(allocation,"arena");
  std::memset(allocation,0,arena_bytes);p58::Cache cache(experts,uint64_t(allocation),arena_bytes);
  cache.reset_capacity(cap);check(cache.capacity()==cap&&cache.resident_bytes()==0,"view starts empty");
  Trace t;std::ostringstream log;
  for(unsigned step=0;step<steps;++step){
    auto epoch=cache.begin_position();
    for(size_t i=0;i<host.size();++i){const auto& e=cache.table()[i];const bool r=cache.resident(i);const uint64_t base=r?uint64_t(allocation):0; // resident entries publish arena addresses: compare base-relative
      log<<(e.gate-base)<<','<<(e.up-base)<<','<<(e.down-base)<<','<<r<<';';}
    cache.finish_position(epoch,true);
    const uint32_t n=uint32_t(host.size());auto plan=cache.prepare({uint32_t((step*7)%n),uint32_t((step*3+1)%n),uint32_t((step*5+2)%n),uint32_t((step*11+5)%n)});
    for(const auto& f:plan.fills){check(f.offset+f.bytes<=cap,"fill inside the usable extent");log<<'F'<<f.expert<<'@'<<f.offset<<'+'<<f.bytes<<';';
      std::memcpy(allocation+f.offset,host[f.expert].data(),256);++t.fills;t.fill_bytes+=f.bytes;}
    cache.commit(plan.epoch,true,true);t.resident_peak=std::max(t.resident_peak,size_t(cache.resident_bytes()));log<<'R'<<cache.resident_bytes()<<'\n';
  }
  // Published pointers are offsets from the arena base (device addresses differ per allocation);
  // compare base-relative values so two arenas can be compared byte-for-byte.
  std::string s=log.str();std::ostringstream rel;
  for(size_t i=0;i<host.size();++i)rel<<i<<':'<<(cache.resident(i)?cache.table()[i].gate-uint64_t(allocation):0)<<';';
  t.log=s;t.log+=rel.str();
  std::free(allocation);return t;
}
int main(){
  const uint64_t S=32*256,growth=256*4,C=S;   // scaled: 32-slot arena under a 96-expert working set (eviction pressure), growth = 4 slots
  std::vector<std::array<unsigned char,256>> host(96);
  for(size_t i=0;i<host.size();++i)for(size_t j=0;j<256;++j)host[i][j]=(i*31+j*17)%251;
  // 1. max inside the larger arena == max inside its own arena (byte-for-byte, every step).
  auto a=replay(S,C,host,64),b=replay(S+growth,C,host,64);
  // addresses differ between allocations; the logs embed absolute pointers of host rows (identical) and
  // of the arena only through relative offsets, so strip nothing: both runs use the same host rows.
  check(a.fills==b.fills&&a.fill_bytes==b.fill_bytes&&a.resident_peak==b.resident_peak,"same fills/bytes/residency");
  check(a.log==b.log,"identical plan/fill/table trace under the larger allocation");
  // 2. max23 (cap = whole arena) admits more than max on the same trace.
  auto c=replay(S+growth,S+growth,host,64);
  check(c.resident_peak>a.resident_peak,"larger usable extent keeps more resident");
  check(c.resident_peak<=S+growth&&a.resident_peak<=S,"residency inside each extent");
  // 3. Capacity switch rules: a cap above the allocation is refused; the switch needs quiescence.
  {std::vector<p58::Expert> experts;for(size_t i=0;i<host.size();++i){auto p=uint64_t(host[i].data());experts.push_back({p,p+64,p+160,64,96,96});}
   auto* alloc=static_cast<unsigned char*>(std::aligned_alloc(256,S+growth));p58::Cache cache(experts,uint64_t(alloc),S+growth);
   bool refused=false;try{cache.reset_capacity(S+growth+256);}catch(const std::logic_error&){refused=true;}check(refused,"cap above allocation refused");
   refused=false;try{cache.reset_capacity(S+1);}catch(const std::logic_error&){refused=true;}check(refused,"unaligned cap refused");
   cache.reset_capacity(S);check(cache.capacity()==S,"max selectable");cache.reset_capacity(S+growth);check(cache.capacity()==S+growth,"max23 selectable");
   auto epoch=cache.begin_position();refused=false;try{cache.reset_capacity(S);}catch(const std::logic_error&){refused=true;}check(refused,"switch during a position refused");
   cache.finish_position(epoch,true);std::free(alloc);}
  // 4. Production literals.
  const uint64_t MAX=21552729600ull,MAX23=23049601024ull;
  check(MAX23%256==0&&MAX%256==0,"256-byte alignment");check(MAX23-MAX==1496871424ull,"growth 1,496,871,424");
  check(MAX23<=29828911360ull-5815529984ull,"arena below the bound minus non-expert weights");
  std::cout<<"{\"passed\":true,\"device_executed\":false,\"checks\":"<<checks<<",\"scaled_arena_bytes\":"<<S<<",\"scaled_growth_bytes\":"<<growth
    <<",\"steps\":64,\"max_fills\":"<<a.fills<<",\"max_fill_bytes\":"<<a.fill_bytes<<",\"max_resident_peak\":"<<a.resident_peak
    <<",\"max23_resident_peak\":"<<c.resident_peak<<",\"max23_fills\":"<<c.fills<<",\"trace_bytes\":"<<a.log.size()<<"}\n";
  return 0;
}
