// Identical CPU-only owner workload for baseline and packet26. No device headers.
#include "owner.hpp"
#include <algorithm>
#include <array>
#include <cstring>
#include <iostream>
#include <numeric>
struct Noop final:ownrt::Operation {};
struct Mock final:ownrt::Backend {
 uint64_t digest=0;std::vector<ownrt::Event> events;
 Mock(){events.reserve(16384);}
 std::string identity()const override{return "CPU no-op submission mock; no GPU timing";}
 void* allocate(size_t n,ownrt::Memory)override{return ::operator new(n);}
 void release(void* p,ownrt::Memory)override{::operator delete(p);}
 ownrt::Event marker(std::span<const ownrt::Event>)override{auto e=ownrt::next_handle();events.push_back(e);return e;}
 ownrt::Event compute(const ownrt::Operation&,std::span<void*const> p,std::span<const ownrt::Event> deps)override {
  // Consume each binding and dependency identically; no optimizer can drop submission.
  for(auto v:p)digest^=reinterpret_cast<uintptr_t>(v);
  for(auto e:deps)digest+=e;
  return marker({});
 }
 ownrt::Event copy(void* a,const void* b,size_t n,std::span<const ownrt::Event> d)override {std::memcpy(a,b,n);return marker(d);}
 bool complete(ownrt::Event e)override{return std::binary_search(events.begin(),events.end(),e);}
 bool wait(ownrt::Event e,ownrt::Deadline)override{return complete(e);}
 void synchronize()override{}
 void clear_events()override{events.clear();}
 void close_queue()override{}
 void close_context()override{}
};
int main(){
 auto backend=std::make_unique<Mock>();auto* mock=backend.get();ownrt::Device d(std::move(backend));
 constexpr size_t sites=2181,allocation_count=3000,binding_count=19;
 std::vector<ownrt::Allocation> allocations;
 for(size_t i=0;i<allocation_count;++i)allocations.push_back(d.arena.allocate("card0:b"+std::to_string(i),4,ownrt::Memory::device,ownrt::Category::scratch,ownrt::Lifetime::transaction));
 std::vector<std::array<ownrt::Allocation,binding_count>> bindings(sites);
 for(size_t i=0;i<sites;++i)for(size_t j=0;j<binding_count;++j)bindings[i][j]=allocations[(i*17+j*43)%allocation_count];
 Noop op;std::vector<double> measured;
 for(int repeat=0;repeat<12;++repeat) {
  auto start=std::chrono::steady_clock::now();
  for(const auto& ids:bindings)d.compute(op,ids,{});
  double ms=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();
  if(repeat>=3)measured.push_back(ms);
  d.retire_completed_events();
 }
 std::sort(measured.begin(),measured.end());auto digest=mock->digest;
 auto closed=d.shutdown(std::chrono::seconds(10));if(!closed.safe_to_exit)return 1;
 std::cout<<"{\"schema\":\"packet26.host-issue-mock.v1\",\"device_executed\":false,\"allocations\":"<<allocation_count<<",\"launches_per_token\":"<<sites<<",\"bindings_per_launch\":"<<binding_count<<",\"warmup_iterations\":3,\"measured_iterations\":9,\"median_ms\":"<<measured[4]<<",\"p90_ms\":"<<measured[8]<<",\"us_per_launch\":"<<measured[4]*1000/sites<<",\"checksum\":"<<digest<<",\"sorted_ms\":[";
 for(size_t i=0;i<measured.size();++i)std::cout<<(i?",":"")<<measured[i];
 std::cout<<"]}\n";return 0;
}
