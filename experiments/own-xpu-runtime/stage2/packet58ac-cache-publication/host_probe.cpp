// CPU-only experiment. Source headers and packing loop are extracted by replay.py.
// No runtime, SYCL, model data, device allocations or device libraries.
#include <array>
#include <chrono>
#include <cstring>
#include <iostream>
#include <map>
#include <random>
#include <set>
#include <string>
#include "cache_table.hpp"
#include "tracked_cache.hpp"
#include "cache_protocol.hpp"

struct Pointer { uint64_t address, generation; };
struct Delta { uint32_t id, reserved; p58::Entry entry; };
static_assert(sizeof(Delta)==40 && sizeof(Pointer)==16);
struct Bank { int layer, projection; };
constexpr size_t N=48*512, BYTES=144*512*sizeof(Pointer);
std::map<std::string,Bank> banks;
std::array<size_t,144> bank_index;

__attribute__((noinline)) void full_pack(const std::vector<p58::Entry>& table, Pointer* staging) {
  size_t base=0;
  for(auto& [name,b]:banks) {
    // Exact archived loop, variable p.g.experts replaced with its fixed value.
#include "packing_loop.inc"
    base+=512;
  }
}
__attribute__((noinline)) size_t delta_pack(const std::vector<p58::Entry>& table,
    const std::vector<uint32_t>& ids, Delta* out) {
  for(size_t i=0;i<ids.size();++i)out[i]={ids[i],0,table.at(ids[i])};
  return ids.size()*sizeof(Delta);
}
void apply(Pointer* table, const Delta* delta, size_t count) {
  // Validation is before mutation; device implementation must enforce the same
  // bounded/deduplicated producer contract and retain buffers until its event.
  std::set<uint32_t> seen;
  for(size_t i=0;i<count;++i)
    if(delta[i].id>=N || delta[i].reserved || !seen.insert(delta[i].id).second)
      throw std::logic_error("malformed delta");
  for(size_t i=0;i<count;++i) {
    const auto& d=delta[i];auto layer=d.id/512, slot=d.id%512;
    uint64_t ptrs[]={d.entry.gate,d.entry.up,d.entry.down};
    for(size_t p=0;p<3;++p)table[bank_index[layer*3+p]*512+slot]={ptrs[p],d.entry.generation};
  }
}
bool same(const auto& a,const auto& b) {
  return a.size()==b.size() && std::memcmp(a.data(),b.data(),a.size()*sizeof(a[0]))==0;
}
void check(bool b) { if(!b)throw std::logic_error("CPU equivalence failure"); }
template<class F> void refused(F f) {bool hit=false;try{f();}catch(const std::logic_error&){hit=true;}check(hit);}

void protocol_tests() {
  std::mt19937 rng(580018);
  size_t transactions=0, generation_only=0, evictions=0;
  for(size_t count: {size_t(96),N})for(uint64_t capacity: {uint64_t(0),uint64_t(256*12),uint64_t(256*80)}) {
    std::vector<p58::Expert> es(count);
    std::vector<tracked58ac::Expert> cs(count);
    for(size_t i=0;i<count;++i) {
      es[i]={0x100000000ull+i*1024,0x100000040ull+i*1024,0x100000080ull+i*1024,64,64,64};
      std::memcpy(&cs[i],&es[i],sizeof(es[i]));
    }
    p58::Cache original(es,0x200000000ull,capacity);
    tracked58ac::Cache candidate(cs,0x200000000ull,capacity);
    // Pack into the full production geometry, using valid filler entries.
    std::vector<p58::Entry> published(N,{1,2,3,1});
    std::copy(original.table().begin(),original.table().end(),published.begin());
    std::vector<Pointer> device(N*3), expected(N*3);
    full_pack(published,device.data());
    for(size_t turn=0;turn<80;++turn) {
      std::vector<uint32_t> routes;
      size_t active=std::min(count,size_t(160));
      if(turn%11)for(size_t i=0;i<40;++i)routes.push_back(rng()%active);
      auto p=original.prepare(routes);auto c=candidate.prepare(routes);
      check(same(p.table,c.table));check(p.fill_bytes==c.fill_bytes && p.evictions==c.evictions);
      auto dirty=c.changed;std::sort(dirty.begin(),dirty.end());dirty.erase(std::unique(dirty.begin(),dirty.end()),dirty.end());
      auto safe=p.table;
      for(const auto& f:p.fills){const auto& e=es[f.expert];safe[f.expert]={e.host_gate,e.host_up,e.host_down,safe[f.expert].generation};}
      for(size_t id=0;id<count;++id) {
        auto a=original.table()[id],b=safe[id];
        if(std::memcmp(&a,&b,sizeof(a)))check(std::binary_search(dirty.begin(),dirty.end(),id));
        if(a.gate==b.gate && a.up==b.up && a.down==b.down && a.generation!=b.generation)++generation_only;
      }
      std::vector<Delta> delta;
      for(auto id:dirty)delta.push_back({id,0,safe[id]});
      apply(device.data(),delta.data(),delta.size());
      std::copy(safe.begin(),safe.end(),published.begin());full_pack(published,expected.data());check(same(device,expected));
      // During any partial/late fill, no published cache address overlaps it.
      for(const auto& f:p.fills)for(const auto& row:safe)for(auto ptr:{row.gate,row.up,row.down})
        check(ptr<0x200000000ull+f.offset || ptr>=0x200000000ull+f.offset+f.bytes);
      // Only fill IDs can change from revoked to committed, including a fill
      // later evicted in the same prepare; always use the FINAL plan entry.
      std::set<uint32_t> final_ids;for(const auto& f:p.fills)final_ids.insert(f.expert);
      delta.clear();for(auto id:final_ids)delta.push_back({id,0,p.table[id]});
      apply(device.data(),delta.data(),delta.size());
      std::copy(p.table.begin(),p.table.end(),published.begin());full_pack(published,expected.data());check(same(device,expected));
      original.commit(p.epoch,true,true);candidate.commit(c.epoch,true,true);
      check(same(original.table(),candidate.table()));++transactions;evictions+=p.evictions;
    }
    original.close();candidate.close();
  }
  std::vector<p58::Expert> es(4,{0x10000,0x10040,0x10080,64,64,64});
  p58::Cache cache(es,0x20000,256);p58v::Protocol protocol;
  protocol.begin();protocol.prepare(cache,{0});
  refused([&]{protocol.revoked(cache);});refused([&]{protocol.submitted(true,1);});
  refused([&]{protocol.end(false);});protocol.end(true);protocol.revoked(cache);
  refused([&]{protocol.submitted(false,1);});protocol.submitted(true,1);
  refused([&]{protocol.commit(cache,false,true);});protocol.begin();
  refused([&]{protocol.commit(cache,true,true);});protocol.end(true);
  refused([&]{protocol.commit(cache,true,false);});protocol.commit(cache,true,true);
  // Failed fill cannot restore overwritten victim pointers.
  auto failed=cache.prepare({1});refused([&]{cache.close_failed(false);});cache.close_failed(true);
  refused([&]{cache.table();});
  std::vector<Pointer> target(N*3), before=target;
  Delta bad[]={ {0,0,{1,2,3,1}}, {0,0,{4,5,6,2}} };
  refused([&]{apply(target.data(),bad,2);});check(same(target,before));
  bad[1].id=N;refused([&]{apply(target.data(),bad,2);});check(same(target,before));
  std::cout<<"\"protocol\":{\"passed\":true,\"transactions\":"<<transactions
    <<",\"generation_only_revocations\":"<<generation_only<<",\"evictions\":"<<evictions<<"},\n";
}
template<class F> void bench(const char* name,F f) {
  std::vector<double> samples;
  for(int trial=0;trial<31;++trial) {
    auto start=std::chrono::steady_clock::now();
    for(int i=0;i<128;++i){f(i);asm volatile("" ::: "memory");}
    samples.push_back(std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count()/128);
  }
  std::sort(samples.begin(),samples.end());
  std::cout<<"\""<<name<<"\":{\"min_ms\":"<<samples.front()<<",\"median_ms\":"<<samples[15]<<",\"p90_ms\":"<<samples[27]<<",\"max_ms\":"<<samples.back()<<"}";
}
int main() {
  for(int l=0;l<48;++l)for(int p=0;p<3;++p)banks.emplace("blk."+std::to_string(l)+".projection"+std::to_string(p),Bank{l,p});
  size_t k=0;for(auto [name,b]:banks)bank_index[b.layer*3+b.projection]=k++;
  std::cout<<"{\n";protocol_tests();
  std::vector<std::vector<p58::Entry>> tables(8,std::vector<p58::Entry>(N));
  for(size_t j=0;j<8;++j)for(size_t i=0;i<N;++i)tables[j][i]={i*256+j,i*256+j+64,i*256+j+128,i+j+1};
  std::vector<Pointer> a(N*3),b(N*3),c(N*3);
  std::vector<Delta> delta(N);
  std::cout<<"\"benchmarks\":{";
  bench("full_pack_hot",[&](int){full_pack(tables[0],a.data());});std::cout<<",";
  bench("full_pack_rotating_8",[&](int i){full_pack(tables[i%8],a.data());});std::cout<<",";
  bench("cpu_memcpy_1179648",[&](int){std::memcpy(b.data(),a.data(),BYTES);});std::cout<<",";
  bench("cpu_scatter_144_banks",[&](int){for(size_t i=0;i<144;++i)std::memcpy(c.data()+i*512,b.data()+i*512,512*sizeof(Pointer));});
  for(size_t n:{size_t(32),size_t(64),size_t(128)}) {
    std::vector<uint32_t> ids;for(size_t i=0;i<n;++i)ids.push_back((i*193)%N);
    std::cout<<",";std::string name="delta_pack_"+std::to_string(n);
    bench(name.c_str(),[&](int i){delta_pack(tables[i%8],ids,delta.data());});
  }
  std::cout<<"},\"checksum\":"<<(a[0].generation+b[0].generation+c[0].generation+delta[0].entry.generation)<<"}\n";
}
