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
int main(){try{std::string line;while(std::getline(std::cin,line)){
 std::istringstream in(line);native38::Config c;int np,ns,ne;require(bool(in>>c.mode>>c.count>>c.overlap>>c.dumps>>np>>ns>>ne),"test input");for(auto [v,n]:{std::pair{&c.prompt,np},std::pair{&c.script,ns},std::pair{&c.eos,ne}}){v->resize(n);for(int& x:*v)require(bool(in>>x),"test value");}
 std::vector<uint8_t> shared(2*slot_bytes+4096);native38::Mailbox box;Mock mock;mock.shared=shared.data();std::exception_ptr worker_error;
 std::thread worker([&](){try{native38::worker(box,5,[&](const Request& r){return mock.execute(1,r);},[]{});}catch(...){worker_error=std::current_exception();native38::abort(box);}});
 native38::Backend backend(box,shared.data(),5,[&](const Request& r){return mock.execute(0,r);},[]{});native38::Result result;
 try{result=native38::run(backend,c);}catch(...){native38::abort(box);worker.join();throw;}worker.join();if(worker_error)std::rethrow_exception(worker_error);
 auto j=native38::json(result,backend,c);j.pop_back();std::cout<<j<<",\"state\":[";
 for(int rank=0;rank<2;++rank){auto& s=mock.states[rank];std::cout<<(rank?",":"")<<"{\"history\":"<<ints(s.history)<<",\"recurrence\":"<<s.recurrence<<",\"rows\":"<<ints(s.rows)<<"}";}
 std::cout<<"],\"fixtures\":[";for(int rank=0;rank<2;++rank){std::cout<<(rank?",":"")<<"[";for(size_t i=0;i<mock.fixtures[rank].size();++i){auto [f,v]=mock.fixtures[rank][i];std::cout<<(i?",":"")<<"["<<f<<","<<v<<"]";}std::cout<<"]";}std::cout<<"]}"<<std::endl;
 }}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}return 0;}
