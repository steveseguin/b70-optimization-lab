#include <algorithm>
#include <chrono>
#include <cstring>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
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
enum {half=1,accept=2,rollback=3,dump=4,draft=9};
struct Request {int32_t op,token,position,fixture,speculative,sequence,reserved[2];};
struct Reply {int32_t status,token,error,bytes,sequence,rank,reserved[2];double busy_ms,gpu_ms,redo_ms,reserved_ms;};
}
#include "native_controller.hpp"
using namespace pipeline;
struct State {std::vector<int> history,rows;int recurrence;bool operator==(const State&) const = default;};
struct Publication {int32_t valid,position,token,error;uint64_t elapsed_ns;int32_t sequence,reserved;double gpu_ms;};
struct Mock {
 State states[2]={{{},{},7},{{},{},11}},saved{};
 std::vector<std::pair<int,int>> fixtures[2];bool pending[2]={};Request candidate[2]{};
 struct PendingDraft {bool live=false;int polls=0;Publication value{};} publication[2];
 int draft_positions[2]={},reverse_position=0,last_verified=-1,last_fixture=0,last_incoming=0,rollbacks=0;int scenario=0;
 uint8_t* shared;native38::Mailbox* box;
 static int step(int old,int token,int position,int incoming=0){return (old*13+token+incoming+position)%104729;}
 void poll(int rank){auto& d=publication[rank];if(!d.live||++d.polls<4)return;std::memcpy(shared+2*slot_bytes,&d.value,sizeof d.value);native38::publish(box->draft_sequence,d.value.sequence);d.live=false;}
 Reply execute(int rank,const Request& r){double begin=native38::clock_now();auto& s=states[rank];int token=-1;
  if(r.op==half){require(!pending[rank]&&int(s.history.size())==r.position,"mock position");if(rank==0)saved=s;
   int incoming=0;if(rank==1)std::memcpy(&incoming,shared+slot_bytes,4);
   s.history.push_back(r.token);s.recurrence=step(s.recurrence,r.token,r.position,incoming);s.rows.push_back(s.recurrence);pending[rank]=true;candidate[rank]=r;
   if(rank==0)std::memcpy(shared,&s.recurrence,4);token=s.recurrence%31;
   if(rank==1){reverse_position=r.position+1;last_verified=token;last_fixture=r.fixture;last_incoming=incoming;}
  }else if(r.op==accept){require(pending[rank],"mock accept");if(candidate[rank].fixture)fixtures[rank].emplace_back(candidate[rank].fixture,s.recurrence);pending[rank]=false;
  }else if(r.op==rollback){require(rank==0&&pending[rank]&&candidate[rank].speculative,"mock rollback");s=saved;pending[rank]=false;++rollbacks;
  }else if(r.op==draft){require(r.position>0&&reverse_position==r.position,"reverse hidden position");if(last_fixture>0)require(r.token==last_verified,"draft must use verified token");
   require(!publication[rank].live&&r.position==++draft_positions[rank],"draft once per confirmed position");
   int p=r.position;require(int(states[1].rows.size())==p,"draft target position");
   int next0=step(last_incoming,r.token,p);int guess=step(states[1].rows[p-1],r.token,p,next0)%31;
   if(scenario==1||(scenario==2&&p%2))guess=(guess+1)%31;
   bool suppress=!r.fixture||(scenario==3&&p%3==0);
   auto& d=publication[rank];d.live=true;d.polls=0;d.value={int32_t(!suppress),p+1,suppress?-1:guess,int32_t(suppress&&r.fixture),0,r.sequence,0,0};
  }else if(r.op==dump)require(!pending[rank],"mock dump");else throw std::runtime_error("mock opcode");
  double end=native38::clock_now();return {0,token,0,r.op==half&&rank==0?4:0,0,rank,{0,0},(end-begin)*1000,0,begin,end};
 }
};
struct Outcome {native38::Result result;State states[2];std::vector<std::pair<int,int>> fixtures[2];std::vector<native38::Trace> trace;int rollbacks;};
Outcome run_case(native38::Config c,int scenario){
 std::vector<uint8_t> shared(2*slot_bytes+4096);native38::Mailbox box;Mock mock;mock.shared=shared.data();mock.box=&box;mock.scenario=scenario;std::exception_ptr worker_error;
 std::thread worker([&](){try{native38::worker(box,5,[&](const Request&r){return mock.execute(1,r);},[&]{mock.poll(1);});}catch(...){worker_error=std::current_exception();native38::abort(box);}});
 native38::Backend backend(box,shared.data(),5,[&](const Request&r){return mock.execute(0,r);},[&]{mock.poll(0);});native38::Result result;
 try{result=native38::run(backend,c);}catch(...){native38::abort(box);worker.join();throw;}worker.join();if(worker_error)std::rethrow_exception(worker_error);
 require(!mock.pending[0]&&!mock.pending[1]&&!mock.publication[0].live&&!mock.publication[1].live,"unresolved mock state");
 return {result,{mock.states[0],mock.states[1]},{mock.fixtures[0],mock.fixtures[1]},backend.trace,mock.rollbacks};
}
void equal(const Outcome&a,const Outcome&b){require(a.result.tokens==b.result.tokens,"target output changed");for(int r=0;r<2;++r){require(a.states[r]==b.states[r],"target rollback state changed");require(a.fixtures[r]==b.fixtures[r],"committed target fixtures changed");}}
int main(){try{int cases=0;for(int repeat=0;repeat<2;++repeat){native38::Config c;c.prompt={3,7,2,19};c.count=16;c.dumps=1;c.vocab=31;c.mode=0;auto baseline=run_case(c,0);
 for(int rank:{0,1})for(int scenario:{0,1,2,3}){c.mode=3;c.draft_rank=rank;auto got=run_case(c,scenario);equal(got,baseline);require(got.result.guesses_count>0,"draft unused");if(scenario==0)require(got.result.hits>0&&got.result.misses==0,"all-hit coverage");if(scenario==1)require(got.result.misses>0&&got.result.hits==0&&got.rollbacks>0,"all-miss rollback coverage");if(scenario==2)require(got.result.hits>0&&got.result.misses>0,"mixed coverage");if(scenario==3)require(got.result.no_guess>0,"no-guess coverage");
 if(rank==0)for(auto& d:got.trace)if(d.command.op==draft){auto h=std::find_if(got.trace.begin(),got.trace.end(),[&](auto&t){return t.rank==1&&t.command.op==half&&t.command.position==d.command.position;});require(h!=got.trace.end()&&d.sent<=h->sent,"draft issued before overlapping target");for(auto&t:got.trace)if(t.rank==0&&t.command.op==half&&t.command.speculative&&t.command.position==d.command.position+1)require(h->sent<=t.sent,"target started before speculative half");}++cases;}
 c.mode=0;c.eos={baseline.result.tokens.front()};auto eosbase=run_case(c,0);for(int rank:{0,1}){c.mode=3;c.draft_rank=rank;auto got=run_case(c,0);equal(got,eosbase);require(got.rollbacks>0,"EOS pending speculation rollback");++cases;}}
 std::cout<<"{\"passed\":true,\"device_executed\":false,\"cases\":"<<cases<<",\"draft_ranks\":[0,1],\"delayed_publication\":true}\n";return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
