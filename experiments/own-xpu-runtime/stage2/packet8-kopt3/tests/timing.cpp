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
    require(j.layer<4 && j.rows>0 && j.rows<=32768 && j.columns>0 && j.columns<=16384 &&
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
constexpr std::array<const char*,7> names{"kopt_sg32","splitk4_v1","decode_const_sg32_v1","decode_slm_sg32_v1","decode_const_split4_v1","decode_slm_split4_v1","shape_dispatch_v1"};
kopt3::Variant variant_of(unsigned v){return v==3?kopt3::Variant::slm:v==4?kopt3::Variant::constant_split4:v==5?kopt3::Variant::slm_split4:kopt3::Variant::constant;}
kopt3::Matrix descriptor(const Job& j) {
  kopt3::Matrix m;static_cast<kopt::Matrix&>(m)={Type(j.type),j.w,j.x,j.y,j.rows,j.columns};
  m.experts=j.bank;m.count=j.bank==512?10:1;m.span=j.rows;m.routes=j.r;m.status=j.status;m.workspace=j.workspace;return m;
}
Launch launch(ownrt::Device& d,const Job& j,unsigned variant=0) {
  admit();
  if(variant==6)return kopt3::multiply_dispatched(d,descriptor(j));
  if(variant==1){auto l=kopt2::multiply(d,{descriptor(j)},kopt2::Variant::split4);return {l.first,l.last,l.passes};}
  if(variant)return kopt3::multiply(d,{descriptor(j)},variant_of(variant));
  auto e=j.bank==512?kopt::routed_gemv(d,Type(j.type),j.w,j.x,j.y,j.r,j.status,512,j.rows,j.columns,10,j.rows,Type::BF16,Type::BF16,32,0):kopt::gemv(d,Type(j.type),j.w,j.x,j.y,j.rows,j.columns,Type::BF16,Type::BF16,32,0);
  return {e,e,1};
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
std::string kernel(ownrt::Device& d,Buffers& b,Job& j,unsigned variant) {
  wait(d,launch(d,j,variant));std::vector<Launch> events;
  for(unsigned i=0;i<iterations;++i)events.push_back(launch(d,j,variant));
  wait(d,events.back());auto timings=events_json(d,events);auto status=b.status(j);
  std::ostringstream out;out<<"{\"name\":"<<ownrt::quote(j.name)<<",\"variant\":"<<ownrt::quote(names[variant])<<",\"events\":"<<timings<<",\"pass_events\":"<<events_json(d,events,true)<<",\"route_status\":[";
  for(size_t i=0;i<status.size();++i)out<<(i?",":"")<<status[i];return out.str()+"]}";
}
std::string sequence(ownrt::Device& d,std::vector<Job>& jobs,unsigned variant) {
  std::vector<Job*> layer;for(auto& j:jobs)if(j.layer==0)layer.push_back(&j);
  unsigned native_events=0;for(auto j:layer)native_events+=variant==6 && kopt3::dispatch_split4(j->type,j->rows,j->columns,j->bank)?2:1;
  Launch last{};for(auto j:layer)last=launch(d,*j,variant);wait(d,last);
  std::ostringstream out;out<<std::setprecision(17)<<"{\"variant\":"<<ownrt::quote(names[variant])<<",\"layer\":0,\"launches_per_layer\":"<<layer.size()<<",\"native_events_per_layer\":"<<native_events<<",\"iterations\":[";
  for(unsigned i=0;i<iterations;++i) {
    std::vector<Launch> events;events.reserve(layer.size());
    auto start=Clock::now();for(auto j:layer)events.push_back(launch(d,*j,variant));auto submitted=Clock::now();
    wait(d,events.back());auto end=Clock::now();
    out<<(i?",":"")<<"{\"events\":"<<events_json(d,events)
      <<",\"pass_events\":"<<events_json(d,events,true)<<",\"host_submit_ms\":"<<std::chrono::duration<double,std::milli>(submitted-start).count()
      <<",\"host_wall_ms\":"<<std::chrono::duration<double,std::milli>(end-start).count()<<'}';
  }
  return out.str()+"]}";
}
std::string fused(ownrt::Device& d,Buffers& buffers,std::vector<Job>& jobs,unsigned family,unsigned variant) {
  std::vector<Job*> selected;
  const std::vector<std::string> small{"hc_attn_inject","hc_ffn_inject","ssm_alpha","ssm_beta","ffn_gate_inp","ffn_gate_inp_shexp"};
  const std::vector<std::string> expert=family==1?std::vector<std::string>{"ffn_gate_exps","ffn_up_exps"}:std::vector<std::string>{"ffn_down_exps"};
  for(auto& suffix:(family?expert:small))for(auto& j:jobs)if(j.name=="blk.0."+suffix+".weight")selected.push_back(&j);
  require(selected.size()==(family?expert.size():6),"fused coverage");
  std::vector<kopt3::Matrix> matrices;for(auto j:selected)matrices.push_back(descriptor(*j));
  auto submit=[&](){admit();return family==1?kopt3::expert_gate_up(d,matrices[0],matrices[1],variant_of(variant)):family==2?kopt3::expert_down(d,matrices[0],variant_of(variant)):kopt3::multiply(d,matrices,variant_of(variant));};
  wait(d,submit());std::vector<Launch> events;
  for(unsigned i=0;i<iterations;++i)events.push_back(submit());wait(d,events.back());
  for(auto j:selected)buffers.status(*j);
  std::ostringstream out;out<<"{\"names\":[";
  for(size_t i=0;i<selected.size();++i)out<<(i?",":"")<<ownrt::quote(selected[i]->name);
  out<<"],\"variant\":"<<ownrt::quote(names[variant])<<",\"kind\":\""<<(family==1?"expert_gate_up":family==2?"expert_down":"small")<<"\",\"events\":"<<events_json(d,events)<<",\"separate_iterations\":[";
  for(unsigned i=0;i<iterations;++i) {
    std::vector<Launch> separate;for(auto j:selected)separate.push_back(launch(d,*j,variant));wait(d,separate.back());
    out<<(i?",":"")<<events_json(d,separate);
  }
  return out.str()+"]}";
}

}
int main(int argc,char** argv) {
  if(argc!=7 || std::string(argv[1])!="--authorized-device-window") {
    std::cerr<<"coordinator only: device-timing --authorized-device-window CARD PLAN RECEIPT CENSUS PHASE\n";return 2;
  }
  std::signal(SIGINT,stop);std::signal(SIGTERM,stop);deadline=Clock::now()+std::chrono::seconds(120);
  std::unique_ptr<ownrt::Device> d;ownrt::Receipt teardown;
  std::string error,identity,seq="[]",fused_result="[]";std::vector<std::string> results,censuses;
  try {
    auto jobs=read_plan(argv[3]);size_t card=std::stoul(argv[2]);require(card==3,"card3 only");admit();
    d=std::make_unique<ownrt::Device>(ownrt::make_sycl_device(card,true));identity=d->identity();
    require(jobs.front().layer==jobs.back().layer,"one layer per owner session");
    bool grouped=std::string(argv[6])=="groups";require(grouped || std::string(argv[6])=="kernels" || std::string(argv[6])=="splits","phase");
    require(!grouped || jobs.front().layer==0,"group layer");
    for(unsigned layer=jobs.front().layer;layer<=jobs.back().layer;++layer) {
      Buffers b(*d);
      for(auto& j:jobs)if(j.layer==layer)prepare(b,j); // all layer weights resident together
      censuses.push_back(d->arena.census());
      for(auto& j:jobs)if(j.layer==layer && !grouped) {
        for(unsigned variant=0;variant<6;++variant)if(variant<2 || (std::string(argv[6])=="kernels"?variant<4:variant>=4))results.push_back(kernel(*d,b,j,variant));std::cout<<"TIMED "<<j.name<<'\n'<<std::flush;
      }
      if(grouped) {
        seq="["+sequence(*d,jobs,0)+","+sequence(*d,jobs,6)+"]";
        fused_result="[";bool comma=false;
        for(unsigned family:{0u,1u,2u})for(unsigned v:{2u,3u}){fused_result+=(comma?",":"")+fused(*d,b,jobs,family,v);comma=true;}
        fused_result+="]";
      }
      b.release();
    }
  }catch(const std::exception& e){error=e.what();}
  if(d) {
    censuses.push_back(d->arena.census());
    // Write evidence BEFORE teardown, which may refuse to return ownership.
    std::ofstream census(argv[5]);census<<"[";
    for(size_t i=0;i<censuses.size();++i)census<<(i?",":"")<<censuses[i];census<<"]\n";census.close();
    teardown=d->shutdown(std::chrono::seconds(10));
  }
  std::ofstream out(argv[4]);out<<"{\"schema\":\"own-runtime.iq3.packet8.timing-native.v1\",\"device\":"<<ownrt::quote(identity)
    <<",\"phase\":"<<ownrt::quote(argv[6])<<",\"device_properties\":"<<kopt3::device_properties()<<",\"error\":"<<ownrt::quote(error)<<",\"kernels\":[";
  for(size_t i=0;i<results.size();++i)out<<(i?",":"")<<results[i];
  out<<"],\"sequence\":"<<seq<<",\"fused\":"<<fused_result<<",\"teardown\":"<<teardown.json()<<"}\n";out.close();
  if(d && !teardown.safe_to_exit)ownrt::hold_for_supervisor();
  return !error.empty() || !teardown.safe_to_exit;
}
