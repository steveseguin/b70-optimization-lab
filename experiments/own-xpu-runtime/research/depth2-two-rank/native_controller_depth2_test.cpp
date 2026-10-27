#include <algorithm>
#include <chrono>
#include <cstring>
#include <cstdint>
#include <filesystem>
#include <fcntl.h>
#include <fstream>
#include <iostream>
#include <map>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>
#include <unistd.h>
namespace fs=std::filesystem;
void require(bool ok,const std::string& why){if(!ok)throw std::runtime_error(why);}
namespace pipeline {
constexpr size_t slot_bytes=65536;
constexpr size_t reverse_offset=2*slot_bytes+4096;
enum {half=1,accept=2,rollback=3,dump=4,draft=9};
struct Request {int32_t op,token,position,fixture,speculative,sequence,reserved[2];};
struct ReverseReady {uint32_t position_plus_one;};
inline ReverseReady& reverse_ready(uint8_t* shared){return *reinterpret_cast<ReverseReady*>(shared+2*slot_bytes+192);}
namespace prefill {
constexpr uint32_t magic=0x31465050u,version=1;constexpr int32_t op=15;constexpr size_t header_bytes=4096;constexpr int max_rows=256;
struct Header {uint32_t magic,version,rows,stream_bytes;int32_t tokens[max_rows];};
inline uint8_t* reverse(uint8_t* base,int index,size_t rows,size_t stream){return base+header_bytes+size_t(2+index)*rows*stream;}
}
namespace p150 {template<class F>void measure(const char*,int,bool,F&& fn){fn();}}
struct Reply {int32_t status,token,error,bytes,sequence,rank,reserved[2];double busy_ms,gpu_ms,redo_ms,reserved_ms;};
}
#include "stage2/packet194-expert-diet-engine/native_controller.hpp"
namespace p56x {const bool sleep20=false;}
using namespace pipeline;
struct State {std::vector<int> history,rows;int recurrence=0;};
struct DraftState {std::vector<int> history,rows;int recurrence=0;bool disabled=false;};
static std::string ints(const std::vector<int>& v){std::ostringstream o;o<<"[";for(size_t i=0;i<v.size();++i)o<<(i?",":"")<<v[i];return o.str()+"]";}
static std::string state_json(const State&s){return "{\"history\":"+ints(s.history)+",\"recurrence\":"+std::to_string(s.recurrence)+",\"rows\":"+ints(s.rows)+"}";}
static std::string draft_json(const DraftState&s){return "{\"history\":"+ints(s.history)+",\"recurrence\":"+std::to_string(s.recurrence)+",\"rows\":"+ints(s.rows)+",\"disabled\":"+(s.disabled?"true":"false")+"}";}
struct Mock {
 struct Pending {Request request;State saved;bool cancelled=false;int recurrence=0;};
 State states[2]={{ {},{},7 },{{},{},11}};std::vector<Pending> pending[2];std::vector<std::pair<int,int>> fixtures[2];
 DraftState draft{{},{},19,false};std::optional<DraftState> draft_saved;std::map<int,int> proposals;uint8_t* shared=nullptr;
 std::vector<std::string> dump_states;int redo_checks=0,cancelled_rows=0,head_service_abandons=0,head_merges=0,cancelled_verification_writes=0,rank1_speculative_rows=0,depth2_draft_calls=0,depth2_target_rows=0;
 const bool head_split=[]{const char* v=std::getenv("MOCK_HEAD_SPLIT");return v&&v[0]=='1';}();
 int verification_position()const{int v=0;std::memcpy(&v,shared+2*slot_bytes+128,4);return v;}
 int verification_token()const{int v=0;std::memcpy(&v,shared+2*slot_bytes+132,4);return v;}
 int proposal(int position)const{auto it=proposals.find(position);return it==proposals.end()?-1:it->second;}
 void advance_draft(int token,int position){
  require(!draft.disabled&&token>=0&&token<31&&position==int(draft.history.size())+1,"mock draft position");
  draft.history.push_back(token);draft.recurrence=(draft.recurrence*17+token+position)%104729;draft.rows.push_back(draft.recurrence);
 }
 Reply execute(int rank,const Request&r){
  const double begin=native38::clock_now();int token=-1,cancelled=0;
  if(r.op==half){
   if(int(states[rank].history.size())!=r.position)throw std::runtime_error("mock target position rank "+std::to_string(rank)+" state "+std::to_string(states[rank].history.size())+" request "+std::to_string(r.position)+" depth "+std::to_string(r.speculative));require(r.speculative>=0&&r.speculative<=2,"mock target depth");
   Pending item{r,states[rank],false};
   if(rank==1&&r.speculative)++rank1_speculative_rows;
   if(rank==0&&r.speculative==2)++depth2_target_rows;
   if(r.speculative==2&&verification_position()==r.position&&verification_token()!=r.token)item.cancelled=true;
   if(!item.cancelled){auto&s=states[rank];int incoming=0;if(rank==1)std::memcpy(&incoming,shared+slot_bytes,4);
    s.history.push_back(r.token);s.recurrence=(s.recurrence*13+r.token+incoming+r.position)%104729;s.rows.push_back(s.recurrence);
    if(rank==0)std::memcpy(shared,&s.recurrence,4);else {std::memcpy(shared+reverse_offset,&s.recurrence,4);int reverse=r.position+1;std::memcpy(shared+2*slot_bytes+192,&reverse,4);if(r.fixture>0){token=s.recurrence%31;std::memcpy(shared+2*slot_bytes+132,&token,4);int ready=r.position+1;std::memcpy(shared+2*slot_bytes+128,&ready,4);}}
   }
   if(item.cancelled){++cancelled_rows;if(head_split&&rank==1)++head_service_abandons;}
   else if(head_split&&rank==1&&r.fixture>0)++head_merges;
   cancelled=item.cancelled;item.recurrence=states[rank].recurrence;pending[rank].push_back(std::move(item));
  }else if(r.op==accept){
   require(!pending[rank].empty(),"mock accept pending");size_t index=r.speculative==2?pending[rank].size()-1:0;auto item=pending[rank][index];require(!item.cancelled,"mock accept cancelled");
   if(item.request.fixture)fixtures[rank].emplace_back(item.request.fixture,item.recurrence);pending[rank].erase(pending[rank].begin()+index);
  }else if(r.op==rollback){
   require(!pending[rank].empty()&&r.speculative>=0&&r.speculative<=2,"mock rollback pending");size_t index=r.speculative==2?pending[rank].size()-1:0;
   auto item=pending[rank][index];require(item.request.speculative,"mock rollback canonical");states[rank]=item.saved;pending[rank].erase(pending[rank].begin()+index);
   if(r.speculative==1){++redo_checks;require(verification_position()==r.position&&verification_token()==r.token,"mock redo verification identity");}
  }else if(r.op==dump){require(pending[rank].empty()&&!draft_saved,"mock dump boundary");if(rank==0)dump_states.push_back("{\"position\":"+std::to_string(r.position)+",\"target\":["+state_json(states[0])+","+state_json(states[1])+"],\"draft\":"+draft_json(draft)+"}");
  }else if(r.op==pipeline::draft){
   require(rank==0,"mock draft owner");
   if(r.speculative<=1){require(!draft_saved,"mock d1 with active d2");advance_draft(r.token,r.position);token=proposal(r.position+1);
    struct Publication{int32_t valid,position,token,error;uint64_t elapsed_ns;int32_t sequence,reserved;double gpu_ms;};
    Publication v{int32_t(token>=0&&token<31),r.position+1,token,0,0,r.sequence,-1,0};std::memcpy(shared+2*slot_bytes,&v,sizeof v);
    if(r.speculative==1)native38::publish(reinterpret_cast<native38::Mailbox*>(shared+2*slot_bytes+256)->draft_sequence,uint32_t(r.sequence));
   }else if(r.speculative==2){require(!draft_saved&&r.token==proposal(r.position),"mock d2 parent");draft_saved=draft;advance_draft(r.token,r.position);token=proposal(r.position+1);if(token<0){draft=*draft_saved;draft_saved.reset();}
   if(r.speculative==2)++depth2_draft_calls;
    int32_t reserved=token;std::memcpy(shared+2*slot_bytes+28,&reserved,4);
   }else if(r.speculative==3){require(draft_saved.has_value(),"mock draft commit");draft_saved.reset();
   }else if(r.speculative==4){require(draft_saved.has_value(),"mock draft rollback");draft=*draft_saved;draft_saved.reset();
   }else throw std::runtime_error("mock draft opcode");
  }else throw std::runtime_error("mock opcode");
  const double end=native38::clock_now();return {0,token,0,r.op==half&&rank==0?4:0,r.sequence,rank,{cancelled,0},(end-begin)*1000,0,begin,end};
 }
 void boundary()const{require(pending[0].empty()&&pending[1].empty()&&!draft_saved,"mock checkpoint/finish tentative leak");}
 std::string canonical_json()const{
  std::string out="{\"state\":["+state_json(states[0])+","+state_json(states[1])+"],\"draft\":"+draft_json(draft)+",\"fixtures\":[";
  for(int rank=0;rank<2;++rank){out+=(rank?",":"");out+="[";for(size_t i=0;i<fixtures[rank].size();++i){out+=(i?",":"");out+="["+std::to_string(fixtures[rank][i].first)+","+std::to_string(fixtures[rank][i].second)+"]";}out+="]";}
  out+="],\"dump_states\":[";for(size_t i=0;i<dump_states.size();++i)out+=(i?",":"")+dump_states[i];
  out+="],\"protocol\":{\"redo_checks\":"+std::to_string(redo_checks)+",\"cancelled_rows\":"+std::to_string(cancelled_rows)+",\"head_service_abandons\":"+std::to_string(head_service_abandons)+",\"head_merges\":"+std::to_string(head_merges)+",\"cancelled_verification_writes\":"+std::to_string(cancelled_verification_writes)+",\"rank1_speculative_rows\":"+std::to_string(rank1_speculative_rows)+",\"depth2_draft_calls\":"+std::to_string(depth2_draft_calls)+",\"depth2_target_rows\":"+std::to_string(depth2_target_rows)+"}}";
  return out;
 }
};
static native38::Config parse_config(const std::string&line){std::istringstream in(line);native38::Config c;int np,ns,ne;require(bool(in>>c.mode>>c.count>>c.overlap>>c.dumps>>np>>ns>>ne),"test input");
 for(auto [v,n]:{std::pair{&c.prompt,np},std::pair{&c.script,ns},std::pair{&c.eos,ne}}){v->resize(n);for(int&x:*v)require(bool(in>>x),"test value");}
 std::string extra;while(in>>extra){if(extra=="prefill")require(bool(in>>c.prefill),"test prefill");else if(extra=="start")require(bool(in>>c.start),"test start");else throw std::runtime_error("test trailer");}
 c.draft_rank=0;c.vocab=31;return c;
}
static std::string execute_config(const native38::Config&c,Mock&mock){
 auto& box=*reinterpret_cast<native38::Mailbox*>(mock.shared+2*slot_bytes+256);std::exception_ptr worker_error;std::thread worker([&](){try{native38::worker(box,5,[&](const Request&r){return mock.execute(1,r);},[]{});}catch(const std::exception&e){std::cerr<<"worker: "<<e.what()<<"\n";worker_error=std::current_exception();native38::abort(box);}catch(...){worker_error=std::current_exception();native38::abort(box);}});
 native38::Backend backend(box,mock.shared,5,[&](const Request&r){try{return mock.execute(0,r);}catch(const std::exception&e){std::cerr<<"local: "<<e.what()<<"\n";throw;}},[]{});native38::Result result;std::vector<int> emitted;
 try{result=native38::run(backend,c,[&](size_t,int token,double){emitted.push_back(token);});}catch(const std::exception&e){std::cerr<<"controller: "<<e.what()<<"\n";auto primary=std::current_exception();native38::abort(box);worker.join();std::rethrow_exception(primary);}catch(...){native38::abort(box);worker.join();throw;}
 worker.join();if(worker_error)std::rethrow_exception(worker_error);require(emitted==result.tokens,"confirmed stream mismatch");mock.boundary();
 auto j=native38::json(result,backend,c);j.pop_back();return j+","+mock.canonical_json().substr(1);
}
int main(){try{
 std::string line;require(bool(std::getline(std::cin,line)),"proposal input");std::istringstream pin(line);int n;require(bool(pin>>n)&&n>=0,"proposal count");Mock mock;std::vector<uint8_t> shared(2*slot_bytes+4096);mock.shared=shared.data();
 for(int i=0;i<n;++i){int position,token;require(bool(pin>>position>>token),"proposal row");mock.proposals[position]=token;}
 bool first=true;while(std::getline(std::cin,line)){if(line.empty())continue;auto c=parse_config(line);if(first)first=false;else require(c.start>0,"continuation must have start");
  // A single continuation case can provide its prior canonical prefix directly. Multi-request cases instead reuse the complete checkpoint above.
  if(c.start>0&&mock.states[0].history.empty()){for(int p=0;p<c.start;++p){Request r0{1,c.prompt[p],p,0,0,0,{0,0}};mock.execute(0,r0);Request a0{2,0,0,0,0,0,{0,0}};mock.execute(0,a0);std::memcpy(mock.shared+slot_bytes,mock.shared,4);Request r1=r0;mock.execute(1,r1);mock.execute(1,a0);}for(int p=1;p<c.start;++p){Request d{9,c.prompt[p],p,0,0,0,{0,0}};mock.execute(0,d);}}
  std::cout<<execute_config(c,mock)<<"\n";
 }
 }catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}return 0;}
