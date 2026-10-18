#include "cache_table.hpp"
#include <cstring>
#include <iostream>
#include <memory>
#include <random>
#include <string>
using namespace p58;
namespace {
size_t checks=0;
void check(bool v,const char* what){++checks;if(!v)throw std::runtime_error(what);}
template<class F>void rejects(F f){bool caught=false;try{f();}catch(const std::exception&){caught=true;}check(caught,"missing rejection");}
struct Arena {void*p;explicit Arena(size_t n):p(::operator new(n,std::align_val_t(256))){}~Arena(){::operator delete(p,std::align_val_t(256));}};
struct Bank {
 std::vector<std::vector<uint8_t>> gates,ups,downs;std::vector<Expert> experts;
 explicit Bank(unsigned n){gates.resize(n);ups.resize(n);downs.resize(n);
  for(unsigned i=0;i<n;++i){size_t bytes=32*(1+i%4);gates[i].assign(bytes,uint8_t(i));ups[i].assign(bytes,uint8_t(i+17));downs[i].assign(bytes,uint8_t(i+83));
   experts.push_back({uint64_t(gates[i].data()),uint64_t(ups[i].data()),uint64_t(downs[i].data()),bytes,bytes,bytes});}}
 void copies(const Plan&p,void*arena){for(auto f:p.fills){auto&e=experts[f.expert];auto*d=static_cast<uint8_t*>(arena)+f.offset;std::memcpy(d,reinterpret_cast<void*>(f.gate),e.gate_bytes);std::memcpy(d+e.gate_bytes,reinterpret_cast<void*>(f.up),e.up_bytes);std::memcpy(d+e.gate_bytes+e.up_bytes,reinterpret_cast<void*>(f.down),e.down_bytes);}}
 void verify(const Cache&c){for(size_t i=0;i<experts.size();++i){auto t=c.table()[i];auto&e=experts[i];check(!std::memcmp(reinterpret_cast<void*>(t.gate),gates[i].data(),e.gate_bytes),"gate bytes");check(!std::memcmp(reinterpret_cast<void*>(t.up),ups[i].data(),e.up_bytes),"up bytes");check(!std::memcmp(reinterpret_cast<void*>(t.down),downs[i].data(),e.down_bytes),"down bytes");}}
};
}
int main(){try{
 Bank bank(64);Arena arena(4096);Cache cache(bank.experts,uint64_t(arena.p),4096);bank.verify(cache);
 auto initial=cache.table()[0];auto epoch=cache.begin_position();
 rejects([&]{cache.begin_position();});rejects([&]{cache.prepare({0});});rejects([&]{cache.close();});
 rejects([&]{cache.finish_position(epoch+1,true);});rejects([&]{cache.finish_position(epoch,false);});cache.finish_position(epoch,true);
 rejects([&]{cache.prepare({64});});auto plan=cache.prepare({0,1,2,3,0});
 rejects([&]{cache.begin_position();});rejects([&]{cache.prepare({4});});rejects([&]{cache.close();});
 rejects([&]{cache.commit(epoch+1,true,true);});rejects([&]{cache.commit(epoch,false,true);});rejects([&]{cache.commit(epoch,true,false);});
 bank.copies(plan,arena.p);cache.commit(epoch,true,true);check(!cache.matches(0,initial),"stale host generation accepted");bank.verify(cache);
 check(cache.resident_bytes()==1536,"aligned variable sizes");
 std::mt19937 gen(58);uint64_t fills=plan.fill_bytes,evictions=0;
 for(unsigned position=0;position<800;++position){epoch=cache.begin_position();auto old=cache.table();cache.finish_position(epoch,true);std::vector<uint32_t> routes;
  for(unsigned j=0;j<1+gen()%24;++j)routes.push_back(gen()%64);
  plan=cache.prepare(routes);bank.copies(plan,arena.p);cache.commit(epoch,true,true);
  bank.verify(cache);check(cache.resident_bytes()<=cache.capacity(),"arena over capacity");
  for(unsigned id=0;id<64;++id){check(cache.matches(id,cache.table()[id]),"new entry rejected");if(old[id].generation!=cache.table()[id].generation)check(!cache.matches(id,old[id]),"ABA generation accepted");}
  fills+=plan.fill_bytes;evictions+=plan.evictions;
 }
 check(fills>0&&evictions>0,"random gate did not evict");cache.close();rejects([&]{cache.begin_position();});rejects([&]{cache.table();});
 Cache zero(bank.experts,0,0);auto no=zero.prepare({1,2,3});check(no.fills.empty(),"zero cache allocated");zero.commit(0,true,true);bank.verify(zero);zero.close();
 Cache tiny(bank.experts,uint64_t(arena.p),128);auto too_big=tiny.prepare({0});check(too_big.fills.empty(),"oversized expert admitted");tiny.commit(0,true,true);bank.verify(tiny);tiny.close();
 // Deterministic recency, distinct from frequency, and generation ABA.
 Cache lru(bank.experts,uint64_t(arena.p),512);auto update=[&](std::vector<uint32_t> r){auto e=lru.begin_position();lru.finish_position(e,true);auto p=lru.prepare(r);bank.copies(p,arena.p);lru.commit(e,true,true);};
 update({0,1});auto old=lru.table()[0];for(int i=0;i<20;++i)update({0});update({1});update({4});check(!lru.resident(0)&&lru.resident(1)&&lru.resident(4),"frequency replaced recency");update({0});check(!lru.matches(0,old),"ABA after slot reuse");lru.close();
 Cache failure(bank.experts,uint64_t(arena.p),4096);failure.prepare({0});rejects([&]{failure.close_failed(false);});failure.close_failed(true);rejects([&]{failure.begin_position();});
 auto bad=bank.experts;bad[0].host_gate=0;rejects([&]{Cache x(bad,uint64_t(arena.p),4096);});
 rejects([&]{Cache x(bank.experts,123,4096);});bad=bank.experts;bad[0].gate_bytes=UINT64_MAX;rejects([&]{Cache x(bad,uint64_t(arena.p),4096);});
 std::cout<<"{\"schema\":\"packet58.cache-cpu.v1\",\"passed\":true,\"device_executed\":false,\"checks\":"<<checks<<",\"positions\":800,\"fill_bytes\":"<<fills<<",\"evictions\":"<<evictions<<",\"maximum_synthetic_arena_bytes\":4096}\n";
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
