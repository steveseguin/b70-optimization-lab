#include "demand.hpp"
#include <iostream>
static void check(bool v){if(!v)throw std::logic_error("ownership proof");}
template<class F>static void refuses(F f){bool failed=false;try{f();}catch(const std::logic_error&){failed=true;}check(failed);}
int main(){
 for(unsigned layer=0;layer<48;++layer)for(unsigned mask=0;mask<1024;++mask){
  p58am::Pool pool;std::array<int,10> slots;slots.fill(-1);
  for(unsigned slot=0;slot<10;++slot)if(mask&(1u<<slot)){
   slots[slot]=pool.acquire(layer*512+slot,17,mask!=1023,false);
   check((slots[slot]>=0)==(mask!=1023));if(slots[slot]<0)continue;
   pool.copied(slots[slot],100+slot);refuses([&]{pool.select(layer*512+slot,17,4);});
  }
  refuses([&]{pool.reset(false);});pool.consumed(17);
  for(unsigned slot=0;slot<10;++slot)if(slots[slot]>=0&&slot%2==0){check(pool.select(layer*512+slot,17,4)==slots[slot]);check(pool.leased(layer*512+slot,4)==slots[slot]);}
  pool.discard(17);refuses([&]{pool.fill_done(4,false);});pool.fill_done(4,true);pool.reset(true);
  for(auto&e:pool.rows)check(e.state==p58am::State::free);
 }
 p58am::Pool pool;
 check(pool.acquire(0,1,true,true)<0);check(pool.acquire(0,1,false,false)<0);
 for(unsigned i=0;i<64;++i){check(pool.acquire(i,i/32+1,true,false)==int(i));pool.copied(i,i+1);}
 check(pool.acquire(99,3,true,false)<0);pool.consumed(1);pool.consumed(2);
 check(pool.select(0,1,7)==0);pool.discard(1);pool.discard(2);
 refuses([&]{pool.reset(true);});check(pool.rows[0].state==p58am::State::leased);
 pool.fill_done(7,true);check(pool.acquire(0,3,true,false)==0);check(pool.repeated_bytes==p58am::expert_bytes);
 pool.copied(0,100);pool.consumed(3);pool.discard(3);pool.reset(true);
 check(sizeof(p58am::Pool)<2*1024*1024);check(sizeof(p58am::Map)*96<1024*1024);
 std::cout<<"{\"passed\":true,\"layer_masks\":49152,\"slot_masks\":1024,\"pool_entries\":64,\"pool_bytes\":126156800,\"pool_metadata_bytes\":"<<sizeof(pool)<<",\"delayed_consumer_and_D2D_refused\":true,\"reset_and_exhaustion\":true}\n";
}
