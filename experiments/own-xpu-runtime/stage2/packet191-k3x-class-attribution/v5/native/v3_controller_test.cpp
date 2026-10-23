// Packet186: native controller run_v3() against run() on a two-rank mailbox mock (GNU and Intel).
// The mock carries three recurrences: rank 0's layers 0-23, the moved layers 24-25 and rank 1's
// layers 26-47. Under run() (U semantics) rank 1 applies the moved layers to rank 0's exported
// stream; under run_v3() rank 0 applies them in the boundary command to its ACCEPTED half output
// and exports the result. The mock enforces the V3 guards (the boundary only after the accept of
// the matching half, no rank-0 half while a boundary is pending, no boundary on a pending guess).
// Tokens, acceptance, guess sequences and all three final states must match for all-hit, all-miss,
// mixed and no-guess scripts, the native rank-1 draft, prompt overlap on/off and an EOS stop.
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
#include <iomanip>
#include "split_timing.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet191-k3x-class-attribution/native-base/experiments/own-xpu-runtime/stage2/packet191-k3x-class-attribution/native_controller.hpp"
#include "v3_controller.hpp"
using namespace pipeline;
namespace p56x {const bool sleep20=false;}
struct State{std::vector<int> history;int recurrence;};
struct Mock{
 bool v3=false;State s0{{},7},saved{},s1{{},11};int moved0=3,moved1=3; // moved layers' state on rank 0 (V3) / rank 1 (U)
 bool pending0=false,ready=false;Request candidate{};int ready_position=-1,ready_output=0,boundaries=0,accepts=0;
 uint8_t* shared;native38::Mailbox* mailbox;
 static int mix(int state,int input){return int((int64_t(state)*17+input)%104729);}
 Reply execute(int rank,const Request& r){double begin=native38::clock_now();int token=-1,bytes=0;
  if(rank==0&&r.op==half){require(!pending0&&int(s0.history.size())==r.position,"mock rank0 position");require(!v3||!ready,"V3: rank-0 half before the pending boundary");
   saved=s0;s0.history.push_back(r.token);s0.recurrence=int((int64_t(s0.recurrence)*13+r.token+r.position)%104729);pending0=true;candidate=r;
   if(!v3){std::memcpy(shared,&s0.recurrence,4);bytes=4;}}
  else if(rank==0&&r.op==accept){require(pending0,"mock accept");pending0=false;++accepts;
   if(v3){require(!ready,"V3: double accept");ready=true;ready_position=candidate.position;ready_output=s0.recurrence;}}
  else if(rank==0&&r.op==rollback){require(pending0&&candidate.speculative,"mock rollback");s0=saved;pending0=false;}
  else if(rank==0&&r.op==v3::boundary_op){require(v3&&ready&&!pending0&&r.position==ready_position,"V3 boundary guard");
   moved0=mix(moved0,ready_output);std::memcpy(shared,&moved0,4);bytes=4;ready=false;++boundaries;}
  else if(rank==1&&r.op==half){int incoming=0;std::memcpy(&incoming,shared+slot_bytes,4);
   int x=incoming;if(!v3){moved1=mix(moved1,incoming);x=moved1;}
   s1.history.push_back(r.token);s1.recurrence=int((int64_t(s1.recurrence)*13+x+r.position)%104729);token=s1.recurrence%31;}
  else if(rank==1&&r.op==accept){}
  else if(rank==1&&r.op==draft){
   struct Publication{int32_t valid,position,token,error;uint64_t elapsed_ns;int32_t sequence,reserved;double gpu_ms;};
   Publication v{1,r.position+1,(r.token*7+3)%31,0,1000,r.sequence,0,0};
   std::memcpy(shared+2*slot_bytes,&v,sizeof v);native38::publish(mailbox->draft_sequence,uint32_t(r.sequence));}
  else if(r.op==dump)require(!pending0&&!ready,"mock dump");
  else throw std::runtime_error("mock opcode");
  double end=native38::clock_now();return {0,token,0,bytes,0,rank,{0,0},(end-begin)*1000,0,begin,end};
 }
};
struct Outcome{native38::Result result;Mock mock;};
Outcome run_case(native38::Config c,bool v3){
 std::vector<uint8_t> shared(3*slot_bytes+4096);native38::Mailbox box;Mock mock;mock.v3=v3;mock.shared=shared.data();mock.mailbox=&box;std::exception_ptr error;
 std::thread worker([&](){try{native38::worker(box,5,[&](const Request&r){return mock.execute(1,r);},[]{});}catch(...){error=std::current_exception();native38::abort(box);}});
 native38::Backend backend(box,shared.data(),5,[&](const Request&r){return mock.execute(0,r);},[]{});
 native38::Result result;
 try{result=v3?native38::run_v3(backend,c):native38::run(backend,c);}catch(...){native38::abort(box);worker.join();throw;}
 worker.join();if(error)std::rethrow_exception(error);
 require(!mock.ready&&!mock.pending0,"controller left rank 0 unresolved");
 return {result,mock};
}
int main(){try{
 unsigned cases=0,boundaries=0,misses=0,hits=0,no_guess=0;
 for(int count:{8,64,128})for(int overlap:{0,1}){
  native38::Config c;c.mode=0;c.count=count;c.overlap=overlap;c.prompt={1,2,3,4,5};
  auto reference=run_case(c,false);
  for(int arm=0;arm<6;++arm){
   c.mode=arm==4?3:arm==5?0:2;c.script=reference.result.tokens;c.eos.clear();
   for(size_t i=0;i<c.script.size();++i){if(arm==1||(arm==2&&i%3==1))c.script[i]=(c.script[i]+1)%31;if(arm==3)c.script[i]=i%4==3?-1:(i%4==2?(c.script[i]+5)%31:c.script[i]);}
   for(int eos:{0,1}){
    if(eos){if(reference.result.tokens.size()<4)continue;c.eos={reference.result.tokens[reference.result.tokens.size()/2]};}
    auto u=run_case(c,false),x=run_case(c,true);
    require(u.result.tokens==x.result.tokens,"V3 target tokens differ");
    if(!eos)require(u.result.tokens==reference.result.tokens,"U tokens differ from the reference");
    require(u.result.guess_sequence==x.result.guess_sequence&&u.result.hits==x.result.hits&&u.result.misses==x.result.misses&&u.result.no_guess==x.result.no_guess,"proposals/acceptance changed");
    require(u.mock.s0.history==x.mock.s0.history&&u.mock.s0.recurrence==x.mock.s0.recurrence,"rank-0 state changed");
    require(u.mock.s1.history==x.mock.s1.history&&u.mock.s1.recurrence==x.mock.s1.recurrence,"rank-1 state changed");
    require(u.mock.moved1==x.mock.moved0&&x.mock.moved1==3&&u.mock.moved0==3,"moved-layer state changed or moved owner");
    require(x.mock.boundaries==x.mock.accepts&&u.mock.boundaries==0,"boundary count must equal rank-0 accepts");
    boundaries+=x.mock.boundaries;misses+=x.result.misses;hits+=x.result.hits;no_guess+=x.result.no_guess;++cases;
   }
  }
 }
 require(hits&&misses&&no_guess,"case mix");
 std::cout<<"{\"passed\":true,\"cases\":"<<cases<<",\"boundaries\":"<<boundaries<<",\"hits\":"<<hits<<",\"misses\":"<<misses<<",\"no_guess\":"<<no_guess<<",\"device_executed\":false}\n";
}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
