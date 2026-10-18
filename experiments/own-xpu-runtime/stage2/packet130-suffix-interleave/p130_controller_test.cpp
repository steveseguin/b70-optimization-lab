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
namespace p56x {const bool sleep20=false;}
using namespace pipeline;
static bool disable_interleave=false;
struct State{std::vector<int> history,rows;int recurrence;};
struct Mock{
 State states[2]={{ {},{},7 },{{},{},11}},saved{};std::vector<std::pair<int,int>> fixtures[2];bool pending[2]={};Request candidate[2]{};uint8_t* shared;
 Reply execute(int rank,const Request& r){double begin=native38::clock_now();auto& s=states[rank];int token=-1;
  if(r.op==half){require(!pending[rank]&&int(s.history.size())==r.position,"mock position");if(rank==0)saved=s;
   int incoming=0;if(rank==1)std::memcpy(&incoming,shared+slot_bytes,4);
   s.history.push_back(r.token);s.recurrence=(s.recurrence*13+r.token+incoming+r.position)%104729;s.rows.push_back(s.recurrence);pending[rank]=true;candidate[rank]=r;
   if(rank==0)std::memcpy(shared,&s.recurrence,4);token=s.recurrence%31;
  }else if(r.op==accept){require(pending[rank],"mock accept");if(candidate[rank].fixture)fixtures[rank].emplace_back(candidate[rank].fixture,s.recurrence);pending[rank]=false;
  }else if(r.op==rollback){require(rank==0&&pending[rank]&&candidate[rank].speculative,"mock rollback");s=saved;pending[rank]=false;
  }else if(r.op==dump)require(!pending[rank],"mock dump");else throw std::runtime_error("mock opcode");
  double end=native38::clock_now();return {0,token,0,r.op==half&&rank==0?4:0,0,rank,{0,0},(end-begin)*1000,0,begin,end};
 }
};
std::string ints(const std::vector<int>& v){std::ostringstream o;o<<"[";for(size_t i=0;i<v.size();++i)o<<(i?",":"")<<v[i];return o.str()+"]";}
#include "p105_common.hpp"
#include "p130_interleave.hpp"

struct Run{native38::Result result;unsigned suffixes;};
Run run_case(native38::Config c,bool split,int arrival=99){
 std::vector<uint8_t> shared(2*slot_bytes+4096);native38::Mailbox box;p105::Mailbox head;Mock mock;mock.shared=shared.data();std::exception_ptr worker_error;unsigned serviced=0;std::atomic<int> boundary{-1};p130::Interleave schedule;
 auto check=[&]{require(!native38::load(box.abort),"mock peer failed");};
 auto await=[&](auto predicate){require(p56x::wait(predicate,check,std::chrono::steady_clock::now()+std::chrono::seconds(5)),"forced arrival timeout");};
 std::vector<int> submitted;unsigned early_services=0;
 std::thread worker([&](){try{native38::worker(box,5,[&](const Request&r){
  auto reply=mock.execute(1,r);
  if(split&&r.op==half&&r.fixture>0){
   await([&]{return boundary.load(std::memory_order_acquire)>=arrival;});
   // This backend's verified final.mix is distinct from rank0's speculative streams.
   head.position=r.position;head.fixture=r.fixture;std::memcpy(head.hidden,&reply.token,4);std::fill(head.hidden+4,head.hidden+5120,uint8_t(r.position));p105::publish(head.request,r.sequence);
   auto seen=p105::load(head.reply);if(seen!=uint32_t(r.sequence))native38::wait_change(head.reply,seen,box,5,[]{});require(p105::load(head.reply)==uint32_t(r.sequence),"head return sequence");
   auto merged=p105::merge({1.f,reply.token,0,0},head.best);require(!merged.error,"finite mock");reply.token=merged.index;
  }return reply;},[]{});}catch(...){worker_error=std::current_exception();native38::abort(box);}});
 auto service=[&](uint32_t seq,int pos,int fix){
  if(schedule.done(seq,pos,fix))return;
  await([&]{return p105::load(head.request)==seq;});
  require(p105::load(head.request)==uint32_t(seq)&&head.position==pos&&head.fixture==fix,"verified head identity");
  auto saved=mock.states[0];int verified=-1;std::memcpy(&verified,head.hidden,4);require(verified>=0&&verified<31,"verified final.mix payload");
  for(unsigned i=4;i<5120;++i)require(head.hidden[i]==uint8_t(pos),"wrong hidden byte");
  // Suffix score is lower; only the verified target vector is observed.
  head.best={0.f,int32_t(p105::prefix+unsigned(verified)),0,0};p105::publish(head.reply,seq);++serviced;
  require(saved.history==mock.states[0].history&&saved.rows==mock.states[0].rows&&saved.recurrence==mock.states[0].recurrence,"suffix changed target state");
  schedule.finish(seq,pos,fix);
  if(boundary.load()<99){require(schedule.boundary==arrival,"not serviced at first ready boundary");++early_services;}
 };
 native38::Backend backend(box,shared.data(),5,[&](const Request&r){
  if(split&&r.op==half&&schedule.pending()){
   // Forced completed layer boundaries; each original layer appears once.
   for(int layer=0;layer<24;++layer){
    submitted.push_back(layer);boundary.store(layer,std::memory_order_release);
    if(layer==arrival)await([&]{return p105::load(head.request)==schedule.sequence;});
    if(!disable_interleave)schedule.chunk(layer,[]{},[&](uint32_t seq){check();return p105::load(head.request)==seq;},service);
   }
  }
  return mock.execute(0,r);
 },[]{});
 if(split){
  backend.before_remote_start=[&](const Request&r){if(r.op==half&&r.fixture>0){boundary.store(-1);schedule.arm(r.sequence,r.position,r.fixture);}};
  backend.before_remote_wait=[&](const Request&r){if(r.op!=half||r.fixture<=0)return;
   boundary.store(99,std::memory_order_release);service(r.sequence,r.position,r.fixture);
  };
 }
 native38::Result result;try{result=native38::run(backend,c);}catch(...){native38::abort(box);worker.join();throw;}worker.join();if(worker_error)std::rethrow_exception(worker_error);
 for(size_t i=0;i<submitted.size();++i)require(submitted[i]==int(i%24),"target layer order changed");
 if(split&&c.mode==2&&arrival<24)require(early_services>0,"early service did not occur");
 if(arrival==99)require(early_services==0,"late service unexpectedly early");
 return {result,serviced};
}
int main(int argc,char**argv){try{
 disable_interleave=argc==2&&std::string(argv[1])=="--old-deferred-negative";
 unsigned cases=0;
 for(int arrival:{0,1,7,23,99})for(int repeat=0;repeat<2;++repeat){
  native38::Config c;c.vocab=31;c.prompt={2,5,11};c.count=8;c.mode=0;c.overlap=1;
  auto base=run_case(c,false);auto no_guess=run_case(c,true,arrival);require(base.result.tokens==no_guess.result.tokens&&no_guess.suffixes==8,"no-guess exactness");
  c.mode=2;c.script=base.result.tokens;auto hits=run_case(c,true,arrival);require(hits.result.tokens==base.result.tokens&&hits.result.hits==7&&hits.suffixes==8,"hit path");
  for(auto&x:c.script)x=(x+1)%31;auto misses=run_case(c,true,arrival);require(misses.result.tokens==base.result.tokens&&misses.result.misses==7&&misses.suffixes==8,"miss path");
  c.eos={base.result.tokens[2]};auto eos=run_case(c,true,arrival);require(eos.result.tokens.size()<=3&&eos.suffixes==eos.result.tokens.size(),"EOS pending head");cases+=4;
 }
 for(int arrival=0;arrival<=24;++arrival){
  p130::Interleave q;q.arm(1,8,1);int submitted=-1,completed=-1,services=0;uint64_t state=7,reference=7;
  std::vector<int> order;
  for(int layer=0;layer<24;++layer){
   submitted=layer;state=state*13+uint64_t(layer);reference=reference*13+uint64_t(layer);order.push_back(layer);
   q.chunk(layer,[&]{completed=submitted;},[&](uint32_t seq){require(completed==submitted&&seq==1,"poll before queue fence");return layer>=arrival;},[&](uint32_t seq,int pos,int fix){
    require(completed==submitted&&layer==arrival,"suffix after wrong boundary");auto before=state;uint64_t hidden=123;hidden=hidden*17+5;require(state==before&&hidden==2096,"private suffix touched target");++services;q.finish(seq,pos,fix);
   });
  }
  if(q.pending()){require(arrival==24,"missed ready event");q.finish(1,8,1);++services;}
  require(services==1&&state==reference&&order.size()==24,"changed speculative work or duplicate service");
 }
 // Negative controls use the actual request state class, never a copied model.
 p130::Interleave state;unsigned refused=0;
 auto reject=[&](auto fn){try{fn();}catch(const std::logic_error&){++refused;return;}throw std::runtime_error("invalid state accepted");};
 reject([&]{state.arm(0,0,1);});state.arm(2,10,3);
 reject([&]{state.arm(3,11,4);});reject([&]{state.done(2,11,3);});reject([&]{state.done(2,10,4);});reject([&]{state.done(1,10,3);});
 bool aborted=false;try{state.chunk(5,[]{},[](auto)->bool{throw std::runtime_error("peer abort");},[](auto,auto,auto){});}catch(const std::runtime_error&){aborted=true;}
 require(aborted&&state.pending(),"abort consumed request");state.finish(2,10,3);reject([&]{state.finish(2,10,3);});reject([&]{state.arm(2,10,3);});
 unsigned fences=0;state.chunk(6,[&]{++fences;},[](auto){return true;},[](auto,auto,auto){throw std::runtime_error("duplicate service");});require(!fences,"completed request fenced");
 state={};state.arm(1,0,1);state.finish(1,0,1);require(state.done(1,0,1),"request reset reuse");
 std::cout<<"{\"passed\":true,\"device_executed\":false,\"cases\":"<<cases<<",\"forced_arrivals\":[0,1,7,23,99],\"hits_and_misses\":true,\"repeated_request_reset\":true,\"negative_controls\":"<<refused<<"}\n";return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
