#include "pipeline/wavefront.hpp"
#include <array>
#include <cassert>
#include <iostream>
#include <vector>
using ownrt::wavefront::Ledger;using ownrt::wavefront::Row;
template<class F>void refuses(F f){bool refused=false;try{f();}catch(const std::exception&){refused=true;}assert(refused);}
struct Owner {
 Ledger ledger;std::vector<int> state,backup;int result=-1;
 explicit Owner(bool final):ledger(final,128,128){}
 void begin(Row r){ledger.begin(r);if(r.tentative)backup=state;state.push_back(r.token);result=(r.token+1)%128;}
 void commit(Row r,bool final){ledger.commit(r.ticket,r.token,r.position,r.fixture,final&&r.fixture?result:-1);backup.clear();}
 void abort(Row r){ledger.match(r.ticket,r.token,r.position,r.fixture);assert(r.tentative);state=backup;backup.clear();ledger.abort(r.ticket,r.token,r.position,r.fixture);}
};
int main(){
 // Every possible first miss in a bounded run; stage0 may run the successor
 // while the previous verified row is still travelling through later owners.
 for(int stages:{2,4,6})for(int miss:{-1,0,1,7,31}){
  std::vector<Owner> owners;for(int i=0;i<stages;++i)owners.emplace_back(i+1==stages);
  std::vector<int> reference;int next=3,ticket=0,proposals=0,actual_aborts=0;
  for(int pos=0;pos<74;++pos){
   int token=next;reference.push_back(token);
   for(int stage=0;stage<stages;++stage){Row row{++ticket,token,pos,pos+1,false};owners[stage].begin(row);owners[stage].commit(row,stage+1==stages);}
   next=(token+1)%128;
   if(pos+1==74)break;
   // Tentative successors on all earlier stages are causally dependent on the
   // same guessed token; final owner never executes a rejected input.
   int guess=proposals++==miss?(next+5)%128:next;std::vector<Row> rows;
   for(int stage=0;stage<stages-1;++stage){rows.push_back({++ticket,guess,pos+1,pos+2,true});owners[stage].begin(rows.back());}
   if(guess!=next){++actual_aborts;for(int stage=0;stage<stages-1;++stage)owners[stage].abort(rows[stage]);}
   else { // Resolve hits, then account for this verified row on final owner.
    for(int stage=0;stage<stages-1;++stage)owners[stage].commit(rows[stage],false);
    Row final{++ticket,next,pos+1,pos+2,false};owners.back().begin(final);owners.back().commit(final,true);
    reference.push_back(next);next=(next+1)%128;++pos;
   }
   for(auto& owner:owners){owner.ledger.boundary();assert(owner.state==reference);}
  }
  assert(actual_aborts==(miss<0?0:1));
  for(auto& owner:owners){assert(owner.state==reference);owner.ledger.boundary();}
 }
 Ledger first(false,64,128);Row pending{1,3,0,1,true};first.begin(pending);
 refuses([&]{first.begin({2,4,1,2,true});});refuses([&]{first.boundary();});
 refuses([&]{first.abort(2,3,0,1);});refuses([&]{first.commit(1,4,0,1,-1);});
 first.abort(1,3,0,1);refuses([&]{first.begin(pending);});
 first.begin({3,4,0,1,false});refuses([&]{first.abort(3,4,0,1);});first.commit(3,4,0,1,-1);
 Ledger final(true,64,128);refuses([&]{final.begin({1,3,0,1,true});});
 final.begin({2,3,0,1,false});final.commit(2,3,0,1,4);
 refuses([&]{final.begin({3,5,1,2,false});});final.begin({4,4,1,2,false});
 refuses([&]{final.commit(4,4,1,2,-1);});final.commit(4,4,1,2,5);
 refuses([&]{final.begin({5,5,2,0,false});});refuses([&]{final.begin({5,5,3,3,false});});
 std::cout<<"PASS wavefront causal commit/forced suffix abort,2/4/6 stages,31/32/33 positions,stale ticket,wrong token,final-only verification,boundary refusal\n";
}
