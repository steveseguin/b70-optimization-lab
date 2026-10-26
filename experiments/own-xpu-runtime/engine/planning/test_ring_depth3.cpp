#include "pipeline/ring/wire.hpp"
#include <cassert>
#include <iostream>
using namespace ownrt::ring_next;
namespace w=ownrt::ring_next::wire;
template<class F>void rejects(F&& f){bool refused=false;try{f();}catch(const std::runtime_error&){refused=true;}assert(refused);}
struct Backend {
 struct Result {int token=-1;std::vector<uint8_t> stream;};
 struct Image {bool active=false;int position=0;std::array<uint8_t,32> state{};};
 int cursor=0;std::array<uint8_t,32> state{};std::array<Image,3> slots{};int capacity,captures=0,restores=0,releases=0;
 explicit Backend(int n):capacity(n){}
 bool error()const{return false;}void quiescent()const{}bool retention_disabled()const{return true;}int position()const{return cursor;}
 int capture(const Row&){for(int i=0;i<capacity;++i)if(!slots[i].active){slots[i]={true,cursor,state};++captures;return i;}throw std::runtime_error("full");}
 Result execute(const Row& row){for(size_t i=0;i<state.size();++i)state[i]=uint8_t(state[i]*3+row.token+int(i));++cursor;return {};}
 void publish(const Result&){}void restore(int i){assert(slots[i].active);cursor=slots[i].position;state=slots[i].state;++restores;}
 void release(int i){assert(slots[i].active);slots[i].active=false;++releases;}
 void reset(){for(const auto& i:slots)assert(!i.active);cursor=0;state.fill(0);captures=restores=releases=0;}
};
Row row(uint64_t epoch,uint64_t id,uint64_t parent,int ticket,int position,int token,bool tentative,const Digest& request,const Digest& before){return {epoch,id,parent,ticket,position,token,position+1,tentative,request,before,extend(before,position,token)};}
void ledger(int depth,int miss){
 Backend backend(depth);Digest request{};request[0]=17;w::Context context{1,request,0,4,16,100,depth};const auto initial=request_prefix(request,1);
 StageRing<Backend> ring(backend,false,true,64,100,1,request,initial,0,depth);int sequence=0;
 auto first=row(1,1,0,++sequence,0,7,false,request,initial);ring.execute(first);ring.accept(++sequence,first,7);
 std::vector<Row> pending;std::vector<std::array<uint8_t,32>> before;auto prior=first;
 for(int i=0;i<depth;++i){auto candidate=row(1,2+i,prior.id,++sequence,1+i,8+i,true,request,prior.after);before.push_back(backend.state);ring.execute(candidate);pending.push_back(candidate);prior=candidate;}
 assert(ring.pending()==size_t(depth)&&ring.physical()==depth+1);
 auto overflow=row(1,10,prior.id,sequence+1,depth+1,20,true,request,prior.after);rejects([&]{ring.execute(overflow);});
 for(int i=0;i<miss-1;++i){auto accepted=ring.accept(++sequence,pending[i],pending[i].token);auto ack=w::acknowledgment(context,sequence,pending[i],accepted,false);w::validate_ack(ack,context,sequence,pending[i],{});assert(ring.physical()==depth+1);}
 const auto oldest=pending[miss-1];auto resolved=ring.abort_suffix(++sequence,oldest);assert(backend.state==before[miss-1]&&ring.physical()==miss&&ring.committed()==miss&&!ring.pending());
 std::vector<uint64_t> expected;for(int i=miss-1;i<depth;++i)expected.push_back(pending[i].id);assert(resolved.discarded==expected&&backend.captures==depth&&backend.releases==depth&&backend.restores==1);
 auto ack=w::acknowledgment(context,sequence,oldest,resolved,true);w::validate_ack(ack,context,sequence,oldest,expected);assert(ack.version==unsigned(depth==3?2:1));
 auto bad=ack;bad.reserved.back()=1;rejects([&]{w::validate_ack(bad,context,sequence,oldest,expected);});bad=ack;bad.version=depth==3?1:2;rejects([&]{w::validate_ack(bad,context,sequence,oldest,expected);});
 if(expected.size()==3){assert(w::third_discard(ack)==expected[2]);bad=ack;bad.reserved[0]^=1;rejects([&]{w::validate_ack(bad,context,sequence,oldest,expected);});}
 request[1]=3;ring.reset(++sequence,2,request,request_prefix(request,2));assert(!ring.physical()&&!ring.committed()&&!ring.pending()&&!ring.rows&&!ring.abort_count);
 auto stale=first;stale.ticket=sequence+1;rejects([&]{ring.execute(stale);});auto next=row(2,1,0,++sequence,0,7,false,request,request_prefix(request,2));ring.execute(next);ring.accept(++sequence,next,7);ring.boundary();
}
void proposal(){
 w::Context c{1,{},0,4,16,100,3};w::ProposalMetaV2 p;p.base.version=2;p.base.bytes=sizeof p;p.base.flags=3;p.base.epoch=1;p.base.ticket=9;p.base.seed_row=2;p.base.parent_row=1;p.base.final_commit=3;p.base.provider_serial=1;p.base.seed_position=p.base.restored_position=1;p.base.requested_depth=p.base.available_depth=3;p.base.guess0=4;p.base.guess1=5;p.guess2=6;p.base.restored=1;
 auto check=[&](const auto& x){w::validate_batch(x,c,9,1,{}, {},{2,1,3,1});};check(p);
 auto bad=p;bad.reserved[0]=1;rejects([&]{check(bad);});bad=p;bad.guess2=100;rejects([&]{check(bad);});bad=p;bad.base.bytes=192;rejects([&]{check(bad);});bad=p;bad.base.requested_depth=2;rejects([&]{check(bad);});rejects([&]{check(p.base);});
 p.base.available_depth=2;p.guess2=-1;check(p);p.guess2=4;rejects([&]{check(p);});
 auto legacy=p.base;legacy.version=1;legacy.bytes=192;legacy.requested_depth=2;c.depth=2;w::validate_batch(legacy,c,9,1,{}, {},{2,1,3,1});
}
int main(){for(int depth:{2,3})for(int miss=1;miss<=depth;++miss)ledger(depth,miss);proposal();std::cout<<"PASS depth2/v1 and depth3/v2 exact suffixes1/2/3, ACCEPT without rewind, cancellation suffix drain, epoch reset, strict third ID and proposal extents/padding\n";}
