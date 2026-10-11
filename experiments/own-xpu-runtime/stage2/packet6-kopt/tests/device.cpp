#include "fixture.hpp"
#include "device.hpp"
#include "../kernels.hpp"
#include "../reference.hpp"
#include <algorithm>
#include <array>
#include <atomic>
#include <csignal>
#include <cstring>
#include <filesystem>
#include <iostream>
#include <memory>
using namespace iq3;
namespace {
volatile std::sig_atomic_t stopping=0;
void stop(int){stopping=1;}
void require(bool b,const char* msg){if(!b)throw std::runtime_error(msg);}
void wait(ownrt::Device& d,ownrt::Event e){require(d.wait(e,std::chrono::seconds(10)),"event deadline; retain owner and await supervisor");}
struct Buffers {
  ownrt::Device& d;ownrt::CopyEngine copy;std::vector<ownrt::Allocation> ids;
  explicit Buffers(ownrt::Device& device):d(device),copy(device){}
  ownrt::Allocation allocate(const std::string& name,size_t n,ownrt::Category category) {
    auto lifetime=category==ownrt::Category::weights?ownrt::Lifetime::process:ownrt::Lifetime::transaction;
    auto id=d.arena.allocate(name,n,ownrt::Memory::device,category,lifetime);ids.push_back(id);return id;
  }
  ownrt::Allocation slab(const std::string& name,size_t n){auto id=d.arena.allocate(name,n,ownrt::Memory::pinned,ownrt::Category::pinned_slab,ownrt::Lifetime::transfer);ids.push_back(id);return id;}
  void upload(ownrt::Allocation to,const void* p,size_t n,const std::string& label) {
    require(!stopping,"cooperative stop before upload");
    auto h=slab(label,n);std::memcpy(d.arena.row(h).pointer,p,n);wait(d,copy.copy(to,0,h,0,n,{}));
  }
  void equal(ownrt::Allocation from,const void* p,size_t n,const std::string& label) {
    require(!stopping,"cooperative stop before readback");
    auto h=slab(label,n);wait(d,copy.copy(h,0,from,0,n,{}));require(!std::memcmp(d.arena.row(h).pointer,p,n),"device/CPU byte mismatch");
  }
  void release(){for(auto id:ids)d.arena.release(id);ids.clear();}
};
void exercise(ownrt::Device& d,const Fixture& f,unsigned subgroup,unsigned mutation,bool optimized) {
  Buffers b(d);auto prefix=std::string("case-")+std::to_string(unsigned(f.type))+"-"+std::to_string(subgroup)+"-"+std::to_string(mutation);
  auto x=f.x;if(mutation)for(auto& v:x)v^=0x8000; // changed inputs; kernels must not return stale data
  auto decoded=f.decoded();std::vector<uint16_t> expected(f.rows);std::vector<float> sums(f.rows);
  for(unsigned r=0;r<f.rows;++r) {
    sums[r]=optimized?kopt::gemv_row(f.type,f.packed.data()+r*f.row_bytes(),x.data(),f.activation,f.columns,subgroup):gemv_row(f.type,f.packed.data()+r*f.row_bytes(),x.data(),f.activation,f.columns);
    expected[r]=output_bits(sums[r],f.output_type);
  }
  auto w=b.allocate(prefix+"/weights",f.packed.size(),ownrt::Category::weights);
  auto dx=b.allocate(prefix+"/x",x.size()*2,ownrt::Category::scratch);
  auto dy=b.allocate(prefix+"/y",expected.size()*2,ownrt::Category::scratch);
  auto dq=b.allocate(prefix+"/dequant",decoded.size()*4,ownrt::Category::scratch);
  auto df=b.allocate(prefix+"/fp32",sums.size()*4,ownrt::Category::scratch);
  b.upload(w,f.packed.data(),f.packed.size(),prefix+"/weight-staging");b.upload(dx,x.data(),x.size()*2,prefix+"/x-staging");
  require(!stopping,"cooperative stop before dequant");
  wait(d,dequant(d,f.type,w,dq,decoded.size(),subgroup));b.equal(dq,decoded.data(),decoded.size()*4,prefix+"/dequant-readback");
  require(!stopping,"cooperative stop before GEMV");
  wait(d,(optimized?kopt::gemv:iq3::gemv)(d,f.type,w,dx,dy,f.rows,f.columns,f.activation,f.output_type,subgroup,df));b.equal(dy,expected.data(),expected.size()*2,prefix+"/gemv-readback");
  b.equal(df,sums.data(),sums.size()*4,prefix+"/fp32-readback");
  // Two experts, two rows each. IDs/spans change in the second pass. Third
  // descriptor is invalid and must emit status1 without dereferencing bank.
  require(f.rows==4,"device fixtures require four rows");
  std::array<Route,3> routes=mutation?std::array<Route,3>{Route{0,1,1},Route{1,0,2},Route{0,2,1}}:std::array<Route,3>{Route{1,0,2},Route{0,1,1},Route{2,0,2}};
  std::vector<uint16_t> rx;for(int i=0;i<3;++i)rx.insert(rx.end(),x.begin(),x.end());
  std::array<uint16_t,6> ry;ry.fill(output_bits(bits_float(0x7fc00000),f.output_type));
  std::array<float,6> rf;rf.fill(bits_float(0x7fc00000));
  std::array<uint32_t,3> status{0,0,1};
  for(unsigned route=0;route<2;++route)for(unsigned row=0;row<routes[route].row_count;++row) {
    auto source=routes[route].expert_id*2+routes[route].row_begin+row;
    ry[route*2+row]=expected[source];rf[route*2+row]=sums[source];
  }
  auto dr=b.allocate(prefix+"/routes",sizeof routes,ownrt::Category::scratch);
  auto ds=b.allocate(prefix+"/status",sizeof status,ownrt::Category::scratch);
  auto drx=b.allocate(prefix+"/routed-x",rx.size()*2,ownrt::Category::scratch);
  auto dry=b.allocate(prefix+"/routed-y",sizeof ry,ownrt::Category::scratch);
  auto drf=b.allocate(prefix+"/routed-fp32",sizeof rf,ownrt::Category::scratch);
  b.upload(dr,routes.data(),sizeof routes,prefix+"/routes-staging");b.upload(drx,rx.data(),rx.size()*2,prefix+"/rx-staging");
  require(!stopping,"cooperative stop before routed GEMV");
  wait(d,(optimized?kopt::routed_gemv:iq3::routed_gemv)(d,f.type,w,drx,dry,dr,ds,2,2,f.columns,3,2,f.activation,f.output_type,subgroup,drf));
  b.equal(dry,ry.data(),sizeof ry,prefix+"/routed-readback");b.equal(ds,status.data(),sizeof status,prefix+"/status-readback");
  b.equal(drf,rf.data(),sizeof rf,prefix+"/routed-fp32-readback");
  std::cout<<"PASS "<<prefix<<"\n"<<std::flush;b.release();
}
void fused_exercise(ownrt::Device& d,const std::vector<const Fixture*>& fixtures,unsigned mutation) {
  Buffers b(d);std::vector<kopt::Matrix> matrices;
  std::vector<std::vector<uint16_t>> outputs(4);
  std::vector<std::vector<float>> sums(4);
  for(unsigned i=0;i<4;++i) {
    const auto& f=*fixtures.at(i);auto x=f.x;for(auto& v:x)if((i+mutation)%2)v^=0x8000;
    auto rows=i+1;outputs[i].resize(rows);sums[i].resize(rows);
    for(unsigned r=0;r<rows;++r) {
      sums[i][r]=kopt::gemv_row(f.type,f.packed.data()+r*f.row_bytes(),x.data(),f.activation,f.columns,16);
      outputs[i][r]=output_bits(sums[i][r],f.output_type);
    }
    auto prefix="fused-"+std::to_string(i);
    auto w=b.allocate(prefix+"/w",f.packed.size(),ownrt::Category::weights);
    auto dx=b.allocate(prefix+"/x",x.size()*2,ownrt::Category::scratch);
    auto y=b.allocate(prefix+"/y",rows*2,ownrt::Category::scratch);
    auto fp=b.allocate(prefix+"/fp32",rows*4,ownrt::Category::scratch);
    b.upload(w,f.packed.data(),f.packed.size(),prefix+"/ws");b.upload(dx,x.data(),x.size()*2,prefix+"/xs");
    matrices.push_back({f.type,w,dx,y,rows,f.columns,f.activation,f.output_type,fp});
  }
  require(!stopping,"cooperative stop before fused GEMV");wait(d,kopt::fused_gemv(d,matrices,16));
  for(unsigned i=0;i<4;++i) {
    b.equal(matrices[i].y,outputs[i].data(),outputs[i].size()*2,"fused-y-"+std::to_string(i));
    b.equal(matrices[i].fp32,sums[i].data(),sums[i].size()*4,"fused-fp32-"+std::to_string(i));
  }
  b.release();std::cout<<"PASS fused type "<<unsigned(fixtures.front()->type)<<" mutation "<<mutation<<'\n'<<std::flush;
}

}
int main(int argc,char** argv) {
  // Native work is an explicit separate action. No enumeration in --help.
  if(argc!=7 || std::string(argv[1])!="--authorized-device-window") {
    std::cerr<<"Usage (authorized window only): device-test --authorized-device-window CARD FIXTURE_DIR RECEIPT CENSUS KERNEL\n";return 2;
  }
  std::signal(SIGINT,stop);std::signal(SIGTERM,stop);
  std::unique_ptr<ownrt::Device> d;std::string error;unsigned checks=0;ownrt::Receipt teardown;
  try {
    const std::string mode=argv[6];require(mode=="baseline" || mode=="kopt_sg16" || mode=="kopt_sg32" || mode=="kopt_fused_sg16","kernel name");
    std::vector<std::filesystem::path> paths;for(auto& entry:std::filesystem::directory_iterator(argv[3]))if(entry.path().extension()==".fixture")paths.push_back(entry.path());
    std::sort(paths.begin(),paths.end());require(!paths.empty() && paths.size()<=32,"bounded fixture count1..32");
    std::vector<Fixture> fixtures;for(auto& p:paths)fixtures.emplace_back(p.string()); // all host inputs owned before queue
    require(!stopping,"cooperative stop before device creation");
    d=std::make_unique<ownrt::Device>(ownrt::make_sycl_device(std::stoul(argv[2])));
    for(auto& f:fixtures)for(unsigned mutation:{0u,1u}) {
      require(!stopping,"cooperative stop");
      if(mode=="baseline")for(unsigned sg:{16u,32u}) {exercise(*d,f,sg,mutation,false);++checks;}
      else if(mode=="kopt_fused_sg16") {fused_exercise(*d,{&f,&f,&f,&f},mutation);++checks;}
      else {exercise(*d,f,mode=="kopt_sg16"?16:32,mutation,true);++checks;}
    }
    if(mode=="kopt_fused_sg16") {
      std::vector<const Fixture*> mixed;
      for(auto type:{Type::F32,Type::Q8_0,Type::BF16,Type::IQ3_S}) {
        auto found=std::find_if(fixtures.begin(),fixtures.end(),[&](const Fixture& f){return f.type==type;});
        require(found!=fixtures.end(),"mixed fused fixture type");mixed.push_back(&*found);
      }
      for(unsigned mutation:{0u,1u}){fused_exercise(*d,mixed,mutation);++checks;}
    }
  }catch(const std::exception& e){error=e.what();}
  if(d) {
    std::ofstream census(argv[5]);census<<d->arena.census()<<'\n';census.close();
    teardown=d->shutdown(std::chrono::seconds(10));
  }
  std::ofstream receipt(argv[4]);receipt<<"{\"checks\":"<<checks<<",\"error\":"<<ownrt::quote(error)<<",\"teardown\":"<<teardown.json()<<"}\n";receipt.close();
  if(d && !teardown.safe_to_exit)ownrt::hold_for_supervisor();
  return !error.empty() || !teardown.safe_to_exit;
}
