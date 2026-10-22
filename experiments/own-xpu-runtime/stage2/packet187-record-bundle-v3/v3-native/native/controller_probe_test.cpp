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
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet186-twocard-v3/native-base/experiments/own-xpu-runtime/stage2/packet186-twocard-v3/native_controller.hpp"
using namespace pipeline;
namespace p56x {const bool sleep20=false;}
struct State{std::vector<int> history,rows;int recurrence;};
struct Mock{
 State states[2]={{ {},{},7 },{{},{},11}},saved{};std::vector<std::pair<int,int>> fixtures[2];bool pending[2]={};Request candidate[2]{};uint8_t* shared;native38::Mailbox* mailbox;int probes=0;
 Reply execute(int rank,const Request& r){double begin=native38::clock_now();auto& s=states[rank];int token=-1;
  if(r.op==half){require(!pending[rank]&&int(s.history.size())==r.position,"mock position");if(rank==0)saved=s;
   int incoming=0;if(rank==1)std::memcpy(&incoming,shared+slot_bytes,4);
   s.history.push_back(r.token);s.recurrence=(s.recurrence*13+r.token+incoming+r.position)%104729;s.rows.push_back(s.recurrence);pending[rank]=true;candidate[rank]=r;
   if(rank==0)std::memcpy(shared,&s.recurrence,4);token=s.recurrence%31;
  }else if(r.op==accept){require(pending[rank],"mock accept");if(candidate[rank].fixture)fixtures[rank].emplace_back(candidate[rank].fixture,s.recurrence);pending[rank]=false;
  }else if(r.op==rollback){require(rank==0&&pending[rank]&&candidate[rank].speculative,"mock rollback");s=saved;pending[rank]=false;
  }else if(r.op==14){require(rank==1&&!pending[1],"mock probe ownership");++probes;
  }else if(r.op==draft){
   require(rank==1&&!pending[1],"mock draft ownership");
   struct Publication{int32_t valid,position,token,error;uint64_t elapsed_ns;int32_t sequence,reserved;double gpu_ms;};
   Publication v{1,r.position+1,(r.token+1)%31,0,1000,r.sequence,0,0};
   std::memcpy(shared+2*slot_bytes,&v,sizeof v);native38::publish(mailbox->draft_sequence,uint32_t(r.sequence));
  }else if(r.op==dump)require(!pending[rank],"mock dump");else throw std::runtime_error("mock opcode");
  double end=native38::clock_now();return {0,token,0,r.op==half&&rank==0?4:0,0,rank,{0,0},(end-begin)*1000,0,begin,end};
 }
};
std::string ints(const std::vector<int>& v){std::ostringstream o;o<<"[";for(size_t i=0;i<v.size();++i)o<<(i?",":"")<<v[i];return o.str()+"]";}

struct Outcome {native38::Result result;State states[2];int probes;};
Outcome run_case(native38::Config c,bool probe){
 std::vector<uint8_t> shared(2*slot_bytes+4096);native38::Mailbox box;Mock mock;mock.shared=shared.data();mock.mailbox=&box;std::exception_ptr error;
 std::thread worker([&](){try{native38::worker(box,5,[&](const Request&r){return mock.execute(1,r);},[]{});}catch(...){error=std::current_exception();native38::abort(box);}});
 native38::Backend backend(box,shared.data(),5,[&](const Request&r){return mock.execute(0,r);},[]{});backend.correction_probe=probe;
 native38::Result result;
 try{result=native38::run(backend,c);}catch(...){native38::abort(box);worker.join();throw;}
 worker.join();if(error)std::rethrow_exception(error);
 return {result,{mock.states[0],mock.states[1]},mock.probes};
}
int main(){try{
 unsigned cases=0,total_misses=0;
 for(int count:{8,64,128}){
  native38::Config c;c.mode=0;c.count=count;c.overlap=1;c.prompt={1,2,3,4,5};
  auto reference=run_case(c,false);
  for(int arm=0;arm<4;++arm){
   c.mode=arm==3?3:2;c.script=reference.result.tokens;
   for(size_t i=0;i<c.script.size();++i)if(arm==1||(arm==2&&i%2))c.script[i]=(c.script[i]+1)%31;
   auto off=run_case(c,false),on=run_case(c,true);
   require(off.result.tokens==reference.result.tokens&&off.result.tokens==on.result.tokens,"target token change");
   require(off.result.guess_sequence==on.result.guess_sequence&&off.result.hits==on.result.hits&&off.result.misses==on.result.misses,"proposal/acceptance changed");
   require(on.probes==on.result.misses&&off.probes==0,"miss-only command count");
   for(int r=0;r<2;++r)require(off.states[r].history==on.states[r].history&&off.states[r].rows==on.states[r].rows&&off.states[r].recurrence==on.states[r].recurrence,"state changed");
   total_misses+=on.probes;++cases;
  }
 }
 std::cout<<"{\"passed\":true,\"cases\":"<<cases<<",\"miss_commands\":"<<total_misses<<",\"device_executed\":false,\"full_model_quality_pending\":true}\n";
}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
