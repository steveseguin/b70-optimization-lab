#include "pipeline/ring/stage_ring.hpp"
#include <cassert>
#include <iostream>
#include <map>
using namespace ownrt::ring_next;
struct Backend {
 struct State {int position=0,error=0,extent=32,parity=0;std::vector<int> tokens;std::array<std::vector<int>,2> banks;std::vector<uint8_t> scratch;bool operator==(const State&)const=default;};
 struct Result {int token=-1;std::vector<uint8_t> stream;};
 State target;std::array<State,2> snapshots;std::array<bool,2> active{};std::vector<int> draft_state;
 bool retained=false,final=false;int restored=0,captured=0,published=0,resets=0;bool fail_execute=false;
 int position()const{return target.position;}int error()const{return target.error;}bool retention_disabled()const{return !retained;}void quiescent(){}
 int capture(const Row&){for(int i=0;i<2;++i)if(!active[i]){snapshots[i]=target;active[i]=true;++captured;return i;}throw std::runtime_error("test full ring");}
 Result execute(const Row& r){target.extent=((r.position+32)/32)*32;target.tokens.push_back(r.token);target.parity^=1;target.banks[target.parity]=target.tokens;target.scratch={uint8_t(r.position),uint8_t(r.token),0xab};++target.position;if(fail_execute)throw std::runtime_error("partial submission");return {final&&r.fixture?((r.token*7+r.position)%97):-1,{uint8_t(r.token)}};}
 void restore(int s){assert(active[s]);target=snapshots[s];++restored;}void release(int s){assert(active[s]);active[s]=false;}void publish(const Result&){++published;}
 void reset(){assert(!active[0]&&!active[1]);target={};draft_state.clear();++resets;}
};
struct Driver {
 Backend b;Digest request{},seed{};StageRing<Backend> ring;
 int sequence=0;uint64_t next_id=1;std::deque<Row> pending;Row accepted{};
 Driver(bool final=false,bool partition=true):ring(b,final,partition,128,97,0,request,seed){b.final=final;}
 Row row(int token,bool tentative,int fixture=-1){Row r;r.epoch=0;r.request=request;r.id=next_id++;r.ticket=++sequence;r.position=b.position();r.token=token;r.tentative=tentative;
  const Row& parent=pending.empty()?accepted:pending.back();r.parent=parent.id;r.before=parent.id?parent.after:seed;r.after=extend(r.before,r.position,token);r.fixture=fixture<0?(parent.fixture?parent.fixture+1:1):fixture;
  ring.execute(r);pending.push_back(r);return r;
 }
 Resolution accept(int actual){auto r=pending.front();auto done=ring.accept(++sequence,r,actual);accepted=r;pending.pop_front();return done;}
 Resolution abort(){auto r=pending.front();auto done=ring.abort_suffix(++sequence,r);pending.clear();return done;}
 void verified(int token,int fixture=0){row(token,false,fixture);accept(token);}
};
template<class F>void refusal(F f){bool refused=false;try{f();}catch(const std::exception&){refused=true;}assert(refused);}
int main(){
 // All-hit older ACCEPT releases one slot without changing any newer bytes.
 {Driver d;d.verified(3);auto a=d.row(7,true),b=d.row(9,true);auto physical=d.b.target;auto r=d.accept(7);assert(r.physical==3&&r.committed==2&&r.pending==1&&d.b.target==physical);d.accept(9);d.ring.boundary();assert(d.b.target==physical&&d.b.restored==0);}
 // Every rejection depth restores the whole dependent suffix exactly once,
 // including31/32/33 extent crossings, bank parity and overwrite-only scratch.
 for(int miss=0;miss<2;++miss){Driver d,reference;for(int p=0;p<31;++p){d.verified(p%9);reference.verified(p%9);}const int truth[2]={7,9};
  auto a=d.row(miss==0?8:7,true),b=d.row(miss==1?10:9,true);
  for(int i=0;i<miss;++i){d.accept(truth[i]);reference.verified(truth[i],i+1);}
  d.ring.draft(++d.sequence,[&]{d.b.draft_state.push_back(51);return 0;});
  auto ack=d.abort();assert(ack.discarded==(miss==0?std::vector<uint64_t>{a.id,b.id}:std::vector<uint64_t>{b.id}));assert(ack.physical==31+miss&&ack.committed==31+miss&&ack.pending==0&&d.b.restored==1);assert(d.b.target==reference.b.target&&d.b.draft_state==std::vector<int>{51});
  refusal([&]{d.ring.accept(++d.sequence,b,9);});
  for(int i=miss;i<2;++i){d.verified(truth[i],i+1);reference.verified(truth[i],i+1);}assert(d.b.target==reference.b.target);
 }
 // Row provenance checks happen before any capture or mutable execution.
 {Driver d;d.verified(3);auto a=d.row(7,true);Row bad=a;bad.ticket=++d.sequence;bad.id=d.next_id++;bad.position=d.b.position();bad.parent=999;bad.before=a.after;bad.after=extend(bad.before,bad.position,bad.token);auto state=d.b.target;
  refusal([&]{d.ring.execute(bad);});assert(d.b.target==state&&d.b.captured==1);bad.parent=a.id;bad.epoch=1;refusal([&]{d.ring.execute(bad);});bad.epoch=0;bad.after[0]^=1;refusal([&]{d.ring.execute(bad);});d.abort();
 }
 // Cannot bypass oldest ticket, exceed slots, or borrow draft around verified work.
 {Driver d;auto v=d.row(3,false);refusal([&]{d.ring.draft(++d.sequence,[]{return 0;});});d.accept(3);auto a=d.row(7,true),b=d.row(9,true);
  refusal([&]{d.ring.accept(++d.sequence,b,9);});refusal([&]{d.row(11,true);});d.abort();
 }
 {Driver d(false,false);d.row(3,true);refusal([&]{d.ring.draft(++d.sequence,[]{return 0;});});d.abort();}
 // A partially submitted row or sticky fault never triggers automatic rollback.
 {Driver d;d.row(3,true);d.b.target.error=1;auto before=d.b.target;refusal([&]{d.abort();});assert(d.b.target==before&&d.b.restored==0);}
 {Driver d;d.b.fail_execute=true;refusal([&]{d.row(3,true);});d.b.fail_execute=false;refusal([&]{d.ring.boundary();});assert(d.b.target.position==1&&d.b.restored==0);}
 // Final owner sees only the input implied by its last committed target output.
 {Driver d(true);refusal([&]{d.row(3,true);});auto r=d.row(3,false,1);const int next=(r.token*7+r.position)%97;d.accept(3);refusal([&]{d.row((next+1)%97,false);});d.row(next,false);d.accept(next);d.ring.boundary();}
 // Empty cold reset preserves monotonic socket sequence and rejects old epoch.
 {Driver d;d.verified(3);auto a=d.row(7,true);refusal([&]{d.ring.reset(++d.sequence,1,d.request,d.seed);});d.abort();const int reset_sequence=++d.sequence;d.ring.reset(reset_sequence,1,d.request,d.seed);assert(d.b.resets==1&&d.ring.last_sequence()==reset_sequence&&d.ring.physical()==0&&d.ring.committed()==0);a.ticket=++d.sequence;a.position=0;refusal([&]{d.ring.execute(a);});}
 {Backend b;Digest digest{};StageRing<Backend> ring(b,false,true,4096,97,std::numeric_limits<uint64_t>::max(),digest,digest);refusal([&]{ring.reset(1,0,digest,digest);});assert(!b.resets);}
 {Driver d;d.b.target.tokens={3,5};d.b.target.position=2;Row last;last.epoch=0;last.request=d.request;last.id=2;last.parent=1;last.ticket=++d.sequence;last.position=1;last.token=5;last.before=extend(d.seed,0,3);last.after=extend(last.before,1,5);d.ring.prefill(2,last);d.next_id=3;d.accepted=last;d.ring.boundary();assert(d.ring.rows==2&&d.ring.commits==2&&d.ring.physical()==2&&d.ring.committed()==2);d.row(7,true);d.abort();assert(d.b.target.position==2&&d.ring.committed()==2&&d.b.restored==1);d.verified(7);assert(d.b.target.position==3&&d.b.target.tokens==std::vector<int>({3,5,7}));}
 std::cout<<"PASS native StageRing two-slot causality, ACCEPT no rewind, single suffix restore, independent draft survival, stale lineage/refusal, sticky failure and reset; synthetic CPU backend only\n";
}
