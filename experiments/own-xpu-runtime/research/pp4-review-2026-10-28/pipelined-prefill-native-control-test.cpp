// Ephemeral control-only harness. Methods below extracted verbatim from candidate.
#include <vector>
#include <array>
#include <stdexcept>
#include <cassert>
#include <iostream>
using std::size_t;
void require(bool ok,const char* message){if(!ok)throw std::runtime_error(message);}
struct Request{int op,token,position;};
struct Row{int position,token;};
struct Args{int prefill_rows=2;bool pipeline_ring_persistent_requests=true;bool pipeline_first()const{return true;}};
struct Engine{Args a;};
struct Ring{int count=0;void prefill(int n,const Row&){count+=n;}};
struct Provider{int position=0;int live_position()const{return position;}};
struct Sequence{int serial=0;std::vector<int> parents;void prefill(const Row& r,int parent){require(r.position==serial+1,"sequence position");parents.push_back(parent);++serial;}};
struct Harness{
 Engine e;Ring ring;Provider owner;Provider* provider=&owner;Sequence sequence;Sequence* provider_sequence=&sequence;
 std::array<int,4> provider_borrows_by_depth{};Row metadata{};
 Row prefill_row(const Request&)const{return metadata;}
 struct PrefillReplay {int start;std::vector<int> tokens;size_t consumed=0;};
 std::vector<PrefillReplay> prefill_replay;
 void prefill_complete(const Request& r,const int* tokens){
  require(e.a.prefill_rows&&e.a.pipeline_ring_persistent_requests&&r.op==15&&r.token>0&&r.token<=e.a.prefill_rows,"ring prefill completion admission");
  if(e.a.pipeline_first()){
   require(tokens&&prefill_replay.size()<2,"ring prefill bounded token ownership");
   if(!prefill_replay.empty()){const auto& previous=prefill_replay.back();require(r.position==previous.start+int(previous.tokens.size()),"ring prefill replay chunk continuity");}
  }
  ring.prefill(r.token,prefill_row(r));
  if(e.a.pipeline_first())prefill_replay.push_back({r.position,std::vector<int>(tokens,tokens+r.token),0});
 }
 void draft_prefill(const Request& r){
  require(!prefill_replay.empty(),"ring prefill DRAFT replay ownership");
  auto& chunk=prefill_replay.front();const auto row=prefill_row(r);
  require(row.token==r.token&&row.position==r.position&&chunk.consumed<chunk.tokens.size()&&r.position==chunk.start+int(chunk.consumed)+1&&provider->live_position()==r.position,"ring prefill DRAFT canonical token/position");
  provider_sequence->prefill(row,chunk.tokens[chunk.consumed]);++provider_borrows_by_depth[0];
  if(++chunk.consumed==chunk.tokens.size())prefill_replay.erase(prefill_replay.begin());
 }
 void reset_admission(){require(prefill_replay.empty(),"ring reset retains unreplayed prefill chunk");}
};

int main(){
 int rejected=0;
 auto refuses=[&](auto fn){try{fn();assert(false);}catch(const std::runtime_error&){++rejected;}};
 Harness h;int a[]={10,20},b[]={30,40},c[]={50,60};
 h.prefill_complete({15,2,0},a);a[0]=99; // retained token ownership
 h.prefill_complete({15,2,2},b);b[0]=99;
 assert(h.prefill_replay.size()==2&&h.ring.count==4);
 refuses([&]{h.prefill_complete({15,2,4},c);});
 assert(h.ring.count==4); // reject before control state mutation
 refuses([&]{h.reset_admission();});
 h.metadata={3,40};h.owner.position=3;
 refuses([&]{h.draft_prefill({9,40,3});}); // B before A
 h.metadata={1,20};h.owner.position=1;
 refuses([&]{h.draft_prefill({9,99,1});}); // request token vs metadata
 h.metadata={2,20};
 refuses([&]{h.draft_prefill({9,20,1});}); // request position vs metadata
 h.metadata={1,20};h.owner.position=0;
 refuses([&]{h.draft_prefill({9,20,1});}); // canonical provider position
 for(int pos=1;pos<=4;++pos){
  h.metadata={pos,10*(pos+1)};h.owner.position=pos;
  h.draft_prefill({9,h.metadata.token,pos});
  if(pos==2)assert(h.prefill_replay.size()==1&&h.prefill_replay.front().start==2);
 }
 assert(h.prefill_replay.empty());assert(h.sequence.serial==4);
 assert((h.sequence.parents==std::vector<int>{10,20,30,40}));
 assert(h.provider_borrows_by_depth[0]==4);h.reset_admission();
 refuses([&]{h.draft_prefill({9,50,4});}); // stale replay after exhaustion
 Harness discontinuous;discontinuous.prefill_complete({15,2,0},c);
 refuses([&]{discontinuous.prefill_complete({15,2,3},c);});
 assert(discontinuous.prefill_replay.size()==1&&discontinuous.ring.count==2);
 assert(rejected==8);
 std::cout<<"PASS native control harness: owned tokens, two chunks, FIFO consumption, cursor/token/provider checks, empty reset; 8 malformed cases rejected\n";
}
