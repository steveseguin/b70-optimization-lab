// Lab-owned transport diagnostic. No model/runtime import and no peer-USM alias.
#include "device.hpp"
#include "timing.hpp"
#include <algorithm>
#include <chrono>
#include <csignal>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>
#include <sstream>
using namespace ownrt;
using Clock=std::chrono::steady_clock;
namespace {
volatile std::sig_atomic_t stopping=0;
Clock::time_point deadline;
std::string stop_file;
void stop(int){stopping=1;}
void require(bool b,const char* s){if(!b)throw std::runtime_error(s);}
void admit(){require(!stopping && Clock::now()<deadline && !std::filesystem::exists(stop_file),"stop latch/deadline; no new work");}
void wait(Device& d,Event e){require(d.wait(e,std::chrono::seconds(5)),"event wait deadline");}
constexpr size_t max_bytes=256ull*1024*1024,chunk=128ull*1024*1024;
constexpr unsigned repeats=20;
struct Case{std::string label;size_t bytes;};
std::vector<Case> plan(const char* path){
  std::ifstream in(path);require(bool(in),"missing plan");std::vector<Case> out;Case c;
  while(in>>c.label>>c.bytes){require(out.size()<6 && c.bytes>0 && c.bytes<=max_bytes,"plan bound");out.push_back(c);}
  require(in.eof() && out.size()==6,"six complete plan rows required");return out;
}
struct Buffers {
  Device& d;CopyEngine copy;Allocation a,b=0,p,h=0,w=0,x=0,y=0;
  Buffers(Device& owner,bool primary):d(owner),copy(owner){
    auto alloc=[&](std::string label,size_t bytes,Memory m){admit();return d.arena.allocate(label,bytes,m,
      m==Memory::device?Category::scratch:Category::loader_staging,
      m==Memory::device?Lifetime::transaction:Lifetime::transfer);};
    a=alloc("copy/destination",max_bytes,Memory::device);
    p=alloc("copy/pinned",max_bytes,Memory::pinned);
    if(primary){
      b=alloc("copy/source",max_bytes,Memory::device);h=alloc("copy/pageable",max_bytes,Memory::shadow);
      w=alloc("gemv/IQ2_S",524800,Memory::device);x=alloc("gemv/BF16-input",5120,Memory::device);y=alloc("gemv/BF16-output",1280,Memory::device);
    }
  }
  void* ptr(Allocation id){return d.arena.row(id).pointer;}
  Event gemv(){admit();return iq3::gemv(d,iq3::Type::IQ2_S,w,x,y,640,2560);}
};
struct Timed {std::string device,kind;EventTiming t;};
std::vector<Timed> transfer(Buffers& b,Allocation dst,Allocation src,size_t n,const std::string& kind){
  std::vector<Timed> times;
  for(size_t off=0;off<n;off+=chunk){
    admit();auto e=b.copy.copy(dst,off,src,off,std::min(chunk,n-off),{});wait(b.d,e);
    auto t=b.d.timing(e);
    times.push_back({b.d.identity(),kind,t});
  }
  return times;
}
void append(std::vector<Timed>& a,std::vector<Timed> b){a.insert(a.end(),b.begin(),b.end());}
std::string events(const std::vector<Timed>& v){
  std::ostringstream o;o<<'[';
  for(size_t i=0;i<v.size();++i){
    auto duration=event_duration(v[i].t);
    o<<(i?",":"")<<"{\"device\":"<<quote(v[i].device)<<",\"kind\":"<<quote(v[i].kind)<<",\"start_ns\":"<<v[i].t.start_ns<<",\"end_ns\":"<<v[i].t.end_ns
     <<",\"duration_ns\":"<<(duration?std::to_string(*duration):"null")<<'}';
  }
  return o.str()+']';
}
std::string sample(double wall,const std::vector<Timed>& v,double cpu=0){
  std::ostringstream o;o<<std::setprecision(17)<<"{\"wall_ns\":"<<wall<<",\"host_bounce_memcpy_ns\":"<<cpu<<",\"events\":"<<events(v)<<'}';return o.str();
}
double ns(Clock::time_point start){return std::chrono::duration<double,std::nano>(Clock::now()-start).count();}
void pattern(void* p,size_t n,unsigned seed){auto v=static_cast<unsigned char*>(p);for(size_t i=0;i<n;++i)v[i]=static_cast<unsigned char>((i*131+(i>>8)+seed)%251);}
void verify(const void* p,size_t n,unsigned seed){auto v=static_cast<const unsigned char*>(p);for(size_t i=0;i<n;++i)require(v[i]==static_cast<unsigned char>((i*131+(i>>8)+seed)%251),"byte copy mismatch");}
std::string row(const Case& c,const std::string& mode,const std::vector<std::string>& samples){
  std::ostringstream o;o<<"{\"label\":"<<quote(c.label)<<",\"bytes\":"<<c.bytes<<",\"mode\":"<<quote(mode)<<",\"verified\":true,\"samples\":[";
  for(size_t i=0;i<samples.size();++i)o<<(i?",":"")<<samples[i];return o.str()+"]}";
}
std::string measure(Buffers& b,Buffers* peer,const Case& c,const std::string& mode,unsigned seed){
  Allocation host=mode.find("pageable")!=std::string::npos?b.h:b.p;
  pattern(b.ptr(host),c.bytes,seed);
  transfer(b,b.b,host,c.bytes,"setup-H2D");
  // b.b is immutable source. Destinations are poisoned so a missing copy fails.
  std::memset(b.ptr(host),0,c.bytes);
  if(mode.starts_with("H2D"))pattern(b.ptr(host),c.bytes,seed);
  std::vector<std::string> samples;
  for(unsigned i=0;i<repeats;++i){
    admit();std::vector<Timed> times;double cpu=0;auto start=Clock::now();
    if(mode.starts_with("H2D"))times=transfer(b,b.a,host,c.bytes,"H2D");
    else if(mode.starts_with("D2H"))times=transfer(b,host,b.b,c.bytes,"D2H");
    else if(mode=="D2D")times=transfer(b,b.a,b.b,c.bytes,"D2D");
    else {
      require(peer!=nullptr,"bounce peer missing");
      times=transfer(b,b.p,b.b,c.bytes,"D2H-A");
      admit();auto copy_start=Clock::now();std::memcpy(peer->ptr(peer->p),b.ptr(b.p),c.bytes);cpu=ns(copy_start);
      append(times,transfer(*peer,peer->a,peer->p,c.bytes,"H2D-B"));
    }
    samples.push_back(sample(ns(start),times,cpu));
  }
  if(mode.starts_with("D2H"))verify(b.ptr(host),c.bytes,seed);
  else if(mode=="host-bounce-A-B"){
    std::memset(peer->ptr(peer->p),0,c.bytes);transfer(*peer,peer->p,peer->a,c.bytes,"verify-D2H");verify(peer->ptr(peer->p),c.bytes,seed);
  } else {
    std::memset(b.ptr(b.p),0,c.bytes);transfer(b,b.p,b.a,c.bytes,"verify-D2H");verify(b.ptr(b.p),c.bytes,seed);
  }
  return row(c,mode,samples);
}
std::string overlap(Buffers& b,const Case& c,const std::string& mode){
  pattern(b.ptr(b.p),c.bytes,83);std::vector<std::string> samples;
  for(unsigned i=0;i<repeats;++i){
    admit();std::vector<Timed> times;Event gemv=0;auto start=Clock::now();
    if(mode=="concurrent" || mode=="compute-only")gemv=b.gemv();
    if(mode!="compute-only")times=transfer(b,b.a,b.p,c.bytes,"H2D");
    if(mode=="serial")gemv=b.gemv();
    if(gemv){wait(b.d,gemv);times.push_back({b.d.identity(),"GEMV",b.d.timing(gemv)});}
    samples.push_back(sample(ns(start),times));
  }
  // Separate disjoint compute and copy buffers; both paths checked after timing.
  if(mode!="compute-only"){
    std::memset(b.ptr(b.p),0,c.bytes);transfer(b,b.p,b.a,c.bytes,"verify-D2H");verify(b.ptr(b.p),c.bytes,83);
  }
  if(mode!="copy-only"){
    transfer(b,b.p,b.y,1280,"verify-GEMV");auto out=static_cast<uint16_t*>(b.ptr(b.p));
    // Synthetic packed blocks have d=1, zero IQ2 indices/signs/scales; x=0.
    for(size_t i=0;i<640;++i)require(out[i]==0,"GEMV changed across overlap modes");
  }
  return row(c,mode,samples);
}
}
int main(int argc,char** argv){
  if(argc!=7 || std::string(argv[1])!="--authorized-device-window"){
    std::cerr<<"coordinator only: h2d-native --authorized-device-window CARD PEER_OR_-1 PLAN RECEIPT STOP_LATCH\n";return 2;
  }
  std::signal(SIGINT,stop);std::signal(SIGTERM,stop);deadline=Clock::now()+std::chrono::seconds(120);stop_file=argv[6];
  std::unique_ptr<Device> a,b;Receipt ta,tb;std::string error;std::vector<std::string> cases,overlaps,censuses,identities;
  bool finished=false;
  auto save=[&]{
    std::ofstream o(std::string(argv[5])+".tmp");
    o<<"{\"schema\":\"own-runtime.h2d.native.v1\",\"completed\":"<<(finished?"true":"false")<<",\"error\":"<<quote(error);
    auto array=[&](const char* name,const std::vector<std::string>& v){o<<",\""<<name<<"\":[";for(size_t i=0;i<v.size();++i)o<<(i?",":"")<<v[i];o<<']';};
    array("devices",identities);array("cases",cases);array("overlap",overlaps);array("census",censuses);
    o<<",\"teardown\":[";if(a)o<<ta.json();if(b)o<<','<<tb.json();o<<"]}\n";o.close();
    std::filesystem::rename(std::string(argv[5])+".tmp",argv[5]);
  };
  try{
    auto jobs=plan(argv[4]);int card=std::stoi(argv[2]),peer=std::stoi(argv[3]);
    require(card>=0 && card<4 && peer>=-1 && peer<4 && peer!=card,"card admission bounds");admit();
    a=std::make_unique<Device>(make_sycl_device(card,true),true);identities.push_back(quote(a->identity()));
    if(peer>=0){admit();b=std::make_unique<Device>(make_sycl_device(peer,true),true);identities.push_back(quote(b->identity()));}
    Buffers main(*a,true);std::unique_ptr<Buffers> other;if(b)other=std::make_unique<Buffers>(*b,false);
    censuses.push_back(a->arena.census());if(b)censuses.push_back(b->arena.census());save();
    // Valid synthetic packed weights, exact zero input. No model payload read.
    std::memset(main.ptr(main.p),0,524800);
    auto packed=static_cast<unsigned char*>(main.ptr(main.p));for(size_t i=0;i<524800;i+=82){packed[i]=0;packed[i+1]=0x3c;}
    transfer(main,main.w,main.p,524800,"setup-weights");
    std::memset(main.ptr(main.p),0,5120);transfer(main,main.x,main.p,5120,"setup-input");
    wait(*a,main.gemv()); // one explicitly untimed GEMV JIT warmup
    unsigned seed=1;
    for(const auto& c:jobs){
      for(const auto& mode:{"H2D-pinned","H2D-pageable","D2H-pinned","D2H-pageable","D2D"}){
        cases.push_back(measure(main,other.get(),c,mode,seed++));save();
      }
      if(other){cases.push_back(measure(main,other.get(),c,"host-bounce-A-B",seed++));save();}
      for(const auto& mode:{"copy-only","compute-only","serial","concurrent"}){overlaps.push_back(overlap(main,c,mode));save();}
      std::cout<<"completed "<<c.label<<'\n'<<std::flush;
    }
    admit();finished=true;
  }catch(const std::exception& e){error=e.what();}
  save(); // evidence precedes potentially blocked driver teardown
  if(b){tb=b->shutdown(std::chrono::seconds(5));save();}
  if(a){ta=a->shutdown(std::chrono::seconds(5));save();}
  if((a && !ta.safe_to_exit)||(b && !tb.safe_to_exit))hold_for_supervisor();
  return !finished || !error.empty() || !a || !ta.safe_to_exit;
}
