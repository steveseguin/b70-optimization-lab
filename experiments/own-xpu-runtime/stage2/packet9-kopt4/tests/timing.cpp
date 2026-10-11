// Bounded diagnostic using the exact packet2 kernels and packet3 resource owner.
#include "device.hpp"
#include "../kernels.hpp"
#include <algorithm>
#include <array>
#include <chrono>
#include <csignal>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>
#include <sstream>
using namespace iq3;
namespace {
using Clock=std::chrono::steady_clock;
volatile std::sig_atomic_t stopping=0;
void stop(int){stopping=1;}
Clock::time_point deadline;
void require(bool ok,const char* message){if(!ok)throw std::runtime_error(message);}
void admit(){require(!stopping && Clock::now()<deadline,"cooperative stop/deadline; no further submissions");}
void wait(ownrt::Device& d,ownrt::Event e){require(d.wait(e,std::chrono::seconds(10)),"event deadline; owner retained if drain fails");}
constexpr size_t chunk=8*1024*1024;
constexpr unsigned iterations=20;
constexpr std::array<uint32_t,10> experts{0,7,31,63,127,255,319,383,447,511};
struct Job {
  unsigned layer,type,rows,columns,bank;
  size_t bytes;
  std::string name;
  std::vector<uint8_t> seed;
  ownrt::Allocation w=0,x=0,y=0,r=0,status=0,workspace=0;
};
std::vector<Job> read_plan(const std::filesystem::path& path) {
  std::ifstream file(path);require(bool(file),"missing plan");
  std::vector<Job> jobs;std::string line;
  while(std::getline(file,line)) {
    Job j{};std::string seed,extra;size_t size=0;
    std::istringstream in(line);
    require(bool(in>>j.layer>>j.name>>j.type>>j.rows>>j.columns>>j.bank>>j.bytes>>size>>seed) && !(in>>extra),"plan columns");
    auto l=layout(Type(j.type));
    require(j.layer<5 && j.rows>0 && j.rows<=248320 && j.columns>0 && j.columns<=16384 &&
      (j.bank==1 || j.bank==512) && l.elements && j.columns%l.elements==0,"shape bounds");
    require(j.bytes==size_t(j.columns)/l.elements*l.bytes*j.rows*j.bank && j.bytes<=512ull*1024*1024,"weight extent");
    require(size>0 && size<=65536 && size%l.bytes==0 && size<=j.bytes,"packed seed extent");
    require(seed==std::filesystem::path(seed).filename() && seed!="." && seed!="..","seed basename");
    j.seed.resize(size);std::ifstream bytes(path.parent_path()/seed,std::ios::binary);
    bytes.read(reinterpret_cast<char*>(j.seed.data()),size);char tail;
    require(bool(bytes) && !bytes.get(tail),"seed bytes");
    require(jobs.size()<100 && (jobs.empty() || jobs.back().layer<=j.layer),"bounded ordered plan");
    jobs.push_back(std::move(j));
  }
  require(!jobs.empty(),"empty plan");return jobs;
}
struct Buffers {
  ownrt::Device& d;ownrt::CopyEngine copy;std::vector<ownrt::Allocation> ids;
  ownrt::Allocation staging;
  explicit Buffers(ownrt::Device& device):d(device),copy(device) {
    admit();staging=d.arena.allocate("timing/staging",chunk,ownrt::Memory::pinned,ownrt::Category::pinned_slab,ownrt::Lifetime::transfer);
    ids.push_back(staging);
  }
  ownrt::Allocation alloc(const std::string& label,size_t bytes,bool weight=false) {
    admit();auto id=d.arena.allocate(label,bytes,ownrt::Memory::device,
      weight?ownrt::Category::weights:ownrt::Category::scratch,
      weight?ownrt::Lifetime::process:ownrt::Lifetime::transaction);
    ids.push_back(id);return id;
  }
  void upload(ownrt::Allocation to,const void* data,size_t bytes) {
    require(bytes<=chunk,"bounded staging");admit();
    std::memcpy(d.arena.row(staging).pointer,data,bytes);
    wait(d,copy.copy(to,0,staging,0,bytes,{}));
  }
  void tiled(ownrt::Allocation to,const std::vector<uint8_t>& seed,size_t bytes) {
    auto p=static_cast<uint8_t*>(d.arena.row(staging).pointer);
    for(size_t off=0;off<bytes;) {
      admit();size_t n=std::min(chunk,bytes-off),done=0;
      while(done<n) {
        auto index=(off+done)%seed.size(),count=std::min(n-done,seed.size()-index);
        std::memcpy(p+done,seed.data()+index,count);done+=count;
      }
      wait(d,copy.copy(to,off,staging,0,n,{}));off+=n;
    }
  }
  std::vector<uint32_t> status(Job& j) {
    if(j.bank==1)return {};
    admit();wait(d,copy.copy(staging,0,j.status,0,40,{}));
    auto p=static_cast<uint32_t*>(d.arena.row(staging).pointer);
    std::vector<uint32_t> result(p,p+10);
    require(std::all_of(result.begin(),result.end(),[](auto v){return v==0;}),"invalid route status");return result;
  }
  void release(){for(auto id:ids)d.arena.release(id);ids.clear();}
};
void prepare(Buffers& b,Job& j) {
  j.w=b.alloc(j.name+"/weights",j.bytes,true);b.tiled(j.w,j.seed,j.bytes);
  unsigned count=j.bank==512?10:1;
  j.x=b.alloc(j.name+"/x",size_t(count)*j.columns*2);
  j.y=b.alloc(j.name+"/y",size_t(count)*j.rows*2);
  j.workspace=b.alloc(j.name+"/workspace",kopt3::workspace_bytes(j.rows,count,kopt3::Variant::constant_split4));
  std::vector<uint16_t> x(size_t(count)*j.columns);
  for(size_t i=0;i<x.size();++i)x[i]=bf16_bits(float(int(i%31)-15)/32.0f);
  b.upload(j.x,x.data(),x.size()*2);
  if(j.bank==512) {
    std::array<Route,10> routes{};
    for(size_t i=0;i<10;++i)routes[i]={experts[i],0,j.rows};
    j.r=b.alloc(j.name+"/routes",sizeof routes);j.status=b.alloc(j.name+"/status",40);
    b.upload(j.r,routes.data(),sizeof routes);
  }
}
using Launch=kopt3::Launch;
kopt3::Matrix descriptor(const Job& j) {
  kopt3::Matrix m;static_cast<kopt::Matrix&>(m)={Type(j.type),j.w,j.x,j.y,j.rows,j.columns};
  m.experts=j.bank;m.count=j.bank==512?10:1;m.span=j.rows;m.routes=j.r;m.status=j.status;m.workspace=j.workspace;return m;
}
Launch launch(ownrt::Device& d,const Job& j) {
 admit();return kopt4::multiply_dispatched(d,descriptor(j));
}
void wait(ownrt::Device& d,Launch l){wait(d,l.last);}
std::string events_json(ownrt::Device& d,const std::vector<Launch>& events,bool passes=false) {
  std::ostringstream out;out<<'[';bool comma=false;
  for(auto e:events) {
    auto a=d.timing(e.first),b=d.timing(e.last);require(a.end_ns>a.start_ns && b.end_ns>b.start_ns,"nonpositive event timing");
    out<<(comma?",":"");
    if(passes)out<<'[';
    out<<"{\"start_ns\":"<<a.start_ns<<",\"end_ns\":"<<(passes?a.end_ns:b.end_ns)<<'}';
    if(passes && e.passes==2)out<<",{\"start_ns\":"<<b.start_ns<<",\"end_ns\":"<<b.end_ns<<'}';
    if(passes)out<<']';comma=true;
  }
  return out.str()+']';
}
struct Block {
 Job *gate=nullptr,*up=nullptr,*down=nullptr;ownrt::Allocation weights=0,out=0;
 void prepare(Buffers& b,std::vector<Job>& jobs) {
  for(auto& j:jobs){if(j.name.find("ffn_gate_exps")!=std::string::npos)gate=&j;if(j.name.find("ffn_up_exps")!=std::string::npos)up=&j;if(j.name.find("ffn_down_exps")!=std::string::npos)down=&j;}
  if(!gate){require(!up && !down,"partial block");return;}
  require(up && down,"partial block");up->x=gate->x;up->r=gate->r;
  weights=b.alloc("moe/probabilities",40);out=b.alloc("moe/mixture",down->rows*2);
  std::array<float,10> probabilities{.25f,.125f,.0625f,.1875f,.03125f,.09375f,.0625f,.0625f,.0625f,.0625f};
  b.upload(weights,probabilities.data(),40);
 }
 std::vector<Launch> submit(ownrt::Device& d,unsigned split) {
  admit();auto a=kopt4::expert_gate_up(d,descriptor(*gate),descriptor(*up),split);
  // GEMV-only diagnostic: BF16 product activations were prepared before timing.
  // This does NOT claim to implement the omitted SiLU/product dependency.
  admit();auto b=kopt4::expert_down(d,descriptor(*down),1);
  admit();auto c=kopt4::epilogue(d,down->y,weights,out,down->rows);
  return {a,b,c};
 }
};
std::string timed(ownrt::Device& d,std::vector<Job>& jobs,Block& block,unsigned split,bool expert_only) {
 auto submit=[&](){
  if(expert_only)return block.submit(d,split);
  std::vector<Launch> events;
  for(auto& j:jobs) {
   if(&j==block.gate){auto e=block.submit(d,split);events.insert(events.end(),e.begin(),e.end());}
   else if(&j!=block.up && &j!=block.down)events.push_back(launch(d,j));
  }
  return events;
 };
 auto warm=submit();wait(d,warm.back());unsigned n=0;for(auto l:warm)n+=l.passes;
 std::ostringstream out;out<<std::setprecision(17)<<"{\"variant\":\""<<(split==4?"experts_split4":"experts_sg32")<<"\",\"layer\":"<<jobs.front().layer
  <<",\"launches\":"<<n<<",\"iterations\":[";
 for(unsigned i=0;i<iterations;++i) {
  auto start=Clock::now();auto events=submit();auto submitted=Clock::now();wait(d,events.back());auto end=Clock::now();
  out<<(i?",":"")<<"{\"events\":"<<events_json(d,events)<<",\"pass_events\":"<<events_json(d,events,true)
   <<",\"host_submit_ms\":"<<std::chrono::duration<double,std::milli>(submitted-start).count()
   <<",\"host_wall_ms\":"<<std::chrono::duration<double,std::milli>(end-start).count()<<'}';
 }
 return out.str()+"]}";
}
}
int main(int argc,char** argv) {
 if(argc!=6 || std::string(argv[1])!="--authorized-device-window")return 2;
 std::signal(SIGINT,stop);std::signal(SIGTERM,stop);deadline=Clock::now()+std::chrono::seconds(120);
 std::unique_ptr<ownrt::Device> d;ownrt::Receipt teardown;std::string error,identity,seq="[]",fused="[]";std::vector<std::string> censuses,statuses;
 try {
  auto jobs=read_plan(argv[3]);require(std::string(argv[2])=="3","card3 only");admit();
  require(jobs.front().layer==jobs.back().layer,"one layer per owner");
  d=std::make_unique<ownrt::Device>(ownrt::make_sycl_device(3,true));identity=d->identity();
  Buffers b(*d);for(auto& j:jobs)prepare(b,j);Block block;block.prepare(b,jobs);
  censuses.push_back(d->arena.census());
  seq="["+timed(*d,jobs,block,1,false)+","+timed(*d,jobs,block,4,false)+"]";
  if(block.gate)fused="["+timed(*d,jobs,block,1,true)+","+timed(*d,jobs,block,4,true)+"]";
  for(auto& j:jobs)if(j.bank==512){auto s=b.status(j);std::ostringstream out;out<<'[';for(size_t i=0;i<s.size();++i)out<<(i?",":"")<<s[i];statuses.push_back(out.str()+']');}
  b.release();
 }catch(const std::exception& e){error=e.what();}
 if(d){censuses.push_back(d->arena.census());std::ofstream out(argv[5]);out<<'[';for(size_t i=0;i<censuses.size();++i)out<<(i?",":"")<<censuses[i];out<<"]\n";out.close();teardown=d->shutdown(std::chrono::seconds(10));}
 std::ofstream out(argv[4]);out<<"{\"schema\":\"own-runtime.iq3.packet9.timing-native.v1\",\"device\":"<<ownrt::quote(identity)
  <<",\"error\":"<<ownrt::quote(error)<<",\"sequence\":"<<seq<<",\"fused\":"<<fused<<",\"route_status\":[";
 for(size_t i=0;i<statuses.size();++i)out<<(i?",":"")<<statuses[i];out<<"],\"teardown\":"<<teardown.json()<<"}\n";out.close();
 if(d && !teardown.safe_to_exit)ownrt::hold_for_supervisor();return !error.empty() || !teardown.safe_to_exit;
}
