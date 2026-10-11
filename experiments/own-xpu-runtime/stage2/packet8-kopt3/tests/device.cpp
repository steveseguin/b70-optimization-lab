#include "fixture.hpp"
#include "device.hpp"
#include "../kernels.hpp"
#include "../reference.hpp"
#include "../../packet7-kopt2/kernels.hpp"
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
void exercise(ownrt::Device& d,const Fixture& f,unsigned subgroup,unsigned mutation,bool optimized,kopt3::Variant variant,bool oldsplit=false) {
  Buffers b(d);auto prefix=std::string("case-")+std::to_string(unsigned(f.type))+"-"+std::to_string(subgroup)+"-"+std::to_string(mutation);
  auto x=f.x;if(mutation)for(auto& v:x)v^=0x8000; // changed inputs; kernels must not return stale data
  auto decoded=f.decoded();std::vector<uint16_t> expected(f.rows);std::vector<float> sums(f.rows);
  for(unsigned r=0;r<f.rows;++r) {
    sums[r]=optimized?kopt3::row(f.type,f.packed.data()+r*f.row_bytes(),x.data(),f.activation,f.columns,variant):kopt::gemv_row(f.type,f.packed.data()+r*f.row_bytes(),x.data(),f.activation,f.columns,32);
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
  auto ws=b.allocate(prefix+"/workspace",kopt3::workspace_bytes(f.rows,1,variant),ownrt::Category::scratch);
  kopt3::Matrix matrix;static_cast<kopt::Matrix&>(matrix)={f.type,w,dx,dy,f.rows,f.columns,f.activation,f.output_type,df};matrix.workspace=ws;
  wait(d,oldsplit?kopt2::multiply(d,{static_cast<kopt2::Matrix>(matrix)},kopt2::Variant::split4).last:optimized?kopt3::multiply(d,{matrix},variant).last:kopt::gemv(d,f.type,w,dx,dy,f.rows,f.columns,f.activation,f.output_type,32,df));b.equal(dy,expected.data(),expected.size()*2,prefix+"/gemv-readback");
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
  auto rws=b.allocate(prefix+"/route-workspace",kopt3::workspace_bytes(2,3,variant),ownrt::Category::scratch);
  static_cast<kopt::Matrix&>(matrix)={f.type,w,drx,dry,2,f.columns,f.activation,f.output_type,drf};
  matrix.experts=2;matrix.count=3;matrix.span=2;matrix.routes=dr;matrix.status=ds;matrix.workspace=rws;
  wait(d,oldsplit?kopt2::multiply(d,{static_cast<kopt2::Matrix>(matrix)},kopt2::Variant::split4).last:optimized?kopt3::multiply(d,{matrix},variant).last:kopt::routed_gemv(d,f.type,w,drx,dry,dr,ds,2,2,f.columns,3,2,f.activation,f.output_type,32,drf));
  b.equal(dry,ry.data(),sizeof ry,prefix+"/routed-readback");b.equal(ds,status.data(),sizeof status,prefix+"/status-readback");
  b.equal(drf,rf.data(),sizeof rf,prefix+"/routed-fp32-readback");
  std::cout<<"PASS "<<prefix<<"\n"<<std::flush;b.release();
}
void fused_exercise(ownrt::Device& d,const std::vector<const Fixture*>& fixtures,unsigned mutation,kopt3::Variant variant,bool routed) {
  Buffers b(d);std::vector<kopt3::Matrix> matrices;
  std::vector<std::vector<uint16_t>> outputs(fixtures.size());std::vector<std::vector<float>> sums(fixtures.size());
  std::vector<std::vector<uint32_t>> statuses(fixtures.size());
  for(unsigned i=0;i<fixtures.size();++i) {
    const auto& f=*fixtures[i];auto x=f.x;for(auto& v:x)if((routed?mutation:i+mutation)%2)v^=0x8000;
    unsigned rows=routed?2:1+i%4,count=routed?10:1,span=rows;std::vector<Route> routes(count);
    std::vector<uint16_t> xs;for(unsigned slot=0;slot<count;++slot)xs.insert(xs.end(),x.begin(),x.end());
    outputs[i].resize(count*span);sums[i].resize(count*span);statuses[i].resize(count);
    for(unsigned slot=0;slot<count;++slot) {
      routes[slot]=routed?Route{(slot+mutation)%2,slot%2,2-slot%2}:Route{0,0,rows};
      if(routed && slot==9)routes[slot]={2,0,2};
      bool valid=valid_route(routes[slot],routed?2:1,rows,span);statuses[i][slot]=valid?0:1;
      for(unsigned r=0;r<span;++r) {
        float value=bits_float(0x7fc00000);
        if(valid && r<routes[slot].row_count) {
          auto source=routes[slot].expert_id*rows+routes[slot].row_begin+r;
          value=kopt3::row(f.type,f.packed.data()+source*f.row_bytes(),x.data(),f.activation,f.columns,variant);
        }
        sums[i][slot*span+r]=value;outputs[i][slot*span+r]=output_bits(value,f.output_type);
      }
    }
    auto prefix="fused-"+std::to_string(i);kopt3::Matrix m;
    m.type=f.type;m.rows=rows;m.columns=f.columns;m.activation=f.activation;m.output_type=f.output_type;
    m.w=b.allocate(prefix+"/w",f.packed.size(),ownrt::Category::weights);
    m.x=b.allocate(prefix+"/x",xs.size()*2,ownrt::Category::scratch);
    m.y=b.allocate(prefix+"/y",outputs[i].size()*2,ownrt::Category::scratch);
    m.fp32=b.allocate(prefix+"/fp32",sums[i].size()*4,ownrt::Category::scratch);
    m.workspace=b.allocate(prefix+"/workspace",kopt3::workspace_bytes(span,count,variant),ownrt::Category::scratch);
    b.upload(m.w,f.packed.data(),f.packed.size(),prefix+"/ws");b.upload(m.x,xs.data(),xs.size()*2,prefix+"/xs");
    if(routed) {
      m.experts=2;m.count=count;m.span=span;
      m.routes=b.allocate(prefix+"/routes",routes.size()*sizeof(Route),ownrt::Category::scratch);
      m.status=b.allocate(prefix+"/status",count*4,ownrt::Category::scratch);
      b.upload(m.routes,routes.data(),routes.size()*sizeof(Route),prefix+"/rs");
    }
    if(routed && i==1 && m.columns==matrices[0].columns && m.activation==matrices[0].activation){m.x=matrices[0].x;m.routes=matrices[0].routes;} // actual gate/up sharing
    matrices.push_back(m);
  }
  require(!stopping,"cooperative stop before fused");if(routed && matrices.size()==3) {
    wait(d,kopt3::expert_gate_up(d,matrices[0],matrices[1],variant).last);
    wait(d,kopt3::expert_down(d,matrices[2],variant).last);
  } else wait(d,kopt3::multiply(d,matrices,variant).last);
  for(unsigned i=0;i<matrices.size();++i) {
    b.equal(matrices[i].y,outputs[i].data(),outputs[i].size()*2,"fused-y-"+std::to_string(i));
    b.equal(matrices[i].fp32,sums[i].data(),sums[i].size()*4,"fused-fp32-"+std::to_string(i));
    if(routed)b.equal(matrices[i].status,statuses[i].data(),statuses[i].size()*4,"fused-status-"+std::to_string(i));
  }
  b.release();std::cout<<"PASS fused "<<kopt3::name(variant)<<" routed="<<routed<<'\n'<<std::flush;
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
    require(std::string(argv[2])=="3","card3 only");
    const std::string mode=argv[6];require(mode=="kopt_sg32" || mode=="splitk4_v1" || mode=="decode_const_sg32_v1" || mode=="decode_slm_sg32_v1" || mode=="decode_const_split4_v1" || mode=="decode_slm_split4_v1" || mode=="fused_decode_const_sg32_v1" || mode=="fused_decode_slm_sg32_v1","kernel variant");
    std::vector<std::filesystem::path> paths;for(auto& entry:std::filesystem::directory_iterator(argv[3]))if(entry.path().extension()==".fixture")paths.push_back(entry.path());
    std::sort(paths.begin(),paths.end());require(!paths.empty() && paths.size()<=32,"bounded fixture count1..32");
    std::vector<Fixture> fixtures;for(auto& p:paths)fixtures.emplace_back(p.string()); // all host inputs owned before queue
    require(!stopping,"cooperative stop before device creation");
    d=std::make_unique<ownrt::Device>(ownrt::make_sycl_device(std::stoul(argv[2])));
    bool baseline=mode=="kopt_sg32",fused=mode.starts_with("fused_");
    auto variant=mode.find("split4")!=std::string::npos || mode=="splitk4_v1"?(mode.find("slm")!=std::string::npos?kopt3::Variant::slm_split4:kopt3::Variant::constant_split4):(mode.find("slm")!=std::string::npos?kopt3::Variant::slm:kopt3::Variant::constant);
    for(auto& f:fixtures)for(unsigned mutation:{0u,1u}) {
      require(!stopping,"cooperative stop");
      if(fused){fused_exercise(*d,{&f,&f,&f,&f,&f,&f},mutation,variant,false);++checks;fused_exercise(*d,{&f,&f,&f},mutation,variant,true);++checks;}
      else {exercise(*d,f,32,mutation,!baseline,variant,mode=="splitk4_v1");++checks;}
    }
    if(fused) {
      std::vector<const Fixture*> mixed;
      for(auto type:{Type::F32,Type::Q8_0,Type::BF16,Type::IQ3_S,Type::Q6_K}) {
        auto found=std::find_if(fixtures.begin(),fixtures.end(),[&](const Fixture& f){return f.type==type;});
        require(found!=fixtures.end(),"mixed fused fixture");mixed.push_back(&*found);
      }
      for(unsigned mutation:{0u,1u})for(bool routed:{false,true}){fused_exercise(*d,mixed,mutation,variant,routed);++checks;}
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
