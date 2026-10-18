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
#include "p106_common.hpp"

struct Run{native38::Result result;unsigned suffixes;};
Run run_case(native38::Config c,bool split,std::vector<int> proposals={}){
 std::vector<uint8_t> shared(2*slot_bytes+4096);native38::Mailbox box;p106::Mailbox head;Mock mock;mock.shared=shared.data();std::exception_ptr worker_error;unsigned serviced=0;
 std::thread worker([&](){try{native38::worker(box,5,[&](const Request&r){
  if(r.op==draft){
   require(!mock.pending[1],"draft before verifier accept");
   int index=r.position-int(c.prompt.size())+1;
   int token=index>=0&&index<int(proposals.size())?proposals[index]:-1;
   bool hit=split&&r.reserved[0]&&r.fixture>0;
   require(r.reserved[0]==0||r.reserved[0]==1,"invalid hit flag");
   if(r.reserved[0])require(index>0&&proposals[index-1]==mock.fixtures[1].back().second%31,"split before verified hit");
   if(hit){
    head.position=r.position;head.fixture=r.fixture;std::memcpy(head.hidden,&token,4);std::fill(head.hidden+4,head.hidden+5120,uint8_t(r.position));p106::publish(head.request,r.sequence);
    auto seen=p106::load(head.reply);if(seen!=uint32_t(r.sequence))native38::wait_change(head.reply,seen,box,5,[]{});
    require(p106::load(head.reply)==uint32_t(r.sequence),"draft suffix reply");
    token=p106::merge({1.f,token,0,0},head.best).index;
   }
   struct Publication{int32_t valid,position,token,error;uint64_t elapsed_ns;int32_t sequence,reserved;double gpu_ms;};
   Publication v{int32_t(token>=0),r.position+1,token,0,0,r.sequence,0,0};std::memcpy(shared.data()+2*slot_bytes,&v,sizeof v);native38::publish(box.draft_sequence,r.sequence);
   return Reply{};
  }
  auto reply=mock.execute(1,r);
  return reply;},[]{});}catch(...){worker_error=std::current_exception();native38::abort(box);}});
 native38::Backend backend(box,shared.data(),5,[&](const Request&r){return mock.execute(0,r);},[]{});
 if(split)backend.before_remote_wait=[&](const Request&r){if(r.op!=draft||!r.reserved[0]||r.fixture<=0)return;
  require(!mock.pending[0],"suffix before rank0 accept");
  auto seen=p106::load(head.request);if(seen!=uint32_t(r.sequence))native38::wait_change(head.request,seen,box,5,[]{});
  require(p106::load(head.request)==uint32_t(r.sequence)&&head.position==r.position&&head.fixture==r.fixture,"verified head identity");
  auto saved=mock.states[0];int verified=-1;std::memcpy(&verified,head.hidden,4);require(verified>=0&&verified<31,"verified final.mix payload");
  for(unsigned i=4;i<5120;++i)require(head.hidden[i]==uint8_t(r.position),"wrong hidden byte");
  // Suffix score is lower; only the verified target vector is observed.
  head.best={0.f,int32_t(p106::prefix+unsigned(verified)),0,0};p106::publish(head.reply,r.sequence);++serviced;
  require(saved.history==mock.states[0].history&&saved.rows==mock.states[0].rows&&saved.recurrence==mock.states[0].recurrence,"suffix changed target state");
 };
 native38::Result result;try{result=native38::run(backend,c);}catch(...){native38::abort(box);worker.join();throw;}worker.join();if(worker_error)std::rethrow_exception(worker_error);return {result,serviced};
}
int main(){try{
 native38::Config c;c.vocab=31;c.prompt={2,5,11};c.count=8;c.mode=0;c.overlap=1;
 auto base=run_case(c,false);c.mode=3;
 auto hits=run_case(c,true,base.result.tokens);auto control=run_case(c,false,base.result.tokens);
 require(hits.result.tokens==base.result.tokens&&hits.result.guess_sequence==control.result.guess_sequence&&hits.result.hits==7&&hits.suffixes==7,"hit-only split proposal identity");
 auto wrong=base.result.tokens;for(auto&x:wrong)x=(x+1)%31;
 auto misses=run_case(c,true,wrong);require(misses.result.tokens==base.result.tokens&&misses.result.misses==7&&misses.suffixes==0,"miss must use full prefix");
 auto mixed=base.result.tokens;for(unsigned i=0;i<mixed.size();i+=2)mixed[i]=(mixed[i]+1)%31;
 auto mixed_split=run_case(c,true,mixed),mixed_full=run_case(c,false,mixed);
 require(mixed_split.result.tokens==base.result.tokens&&mixed_split.result.guess_sequence==mixed_full.result.guess_sequence&&mixed_split.suffixes==unsigned(mixed_split.result.hits)&&mixed_split.result.misses>0,"mixed hit/miss transitions");
 auto no=run_case(c,true);require(no.result.tokens==base.result.tokens&&no.suffixes==0,"no guess must use full prefix");
 c.eos={base.result.tokens[2]};auto eos=run_case(c,true,base.result.tokens);require(eos.result.tokens.size()<=3&&eos.suffixes+1==eos.result.tokens.size(),"EOS outstanding suffix");
 std::cout<<"{\"passed\":true,\"device_executed\":false,\"hit_split_count\":7,\"miss_split_count\":0,\"full_prefix_on_miss\":true,\"identical_proposals\":true,\"EOS\":true}\n";return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
