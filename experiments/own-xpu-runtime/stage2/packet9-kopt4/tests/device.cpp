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
void exercise(ownrt::Device& d,const Fixture& f,unsigned mutation,unsigned split,bool down_only=false) {
 Buffers b(d);constexpr unsigned bank=512,count=10,rows=7,span=5;
 unsigned k=f.type==Type::IQ4_NL?640:2560;
 auto l=layout(f.type);size_t rb=k/l.elements*l.bytes;
 std::vector<uint8_t> packed(size_t(bank)*rows*rb);
 for(unsigned e=0;e<bank;++e)for(unsigned r=0;r<rows;++r)for(size_t j=0;j<rb;++j)
  packed[(size_t(e)*rows+r)*rb+j]=f.packed[((e*3+r)%f.rows)*f.row_bytes()+j%f.row_bytes()];
 // Distinguish banks even when fixture rows repeat, keeping scales finite.
 for(unsigned e=0;e<bank;++e)for(unsigned r=0;r<rows;++r)for(size_t j=0;j<rb;j+=l.bytes) {
  size_t at=(size_t(e)*rows+r)*rb+j;uint16_t scale=uint16_t(0x1800+(e*13+r*17)%0x1800);
  packed[at]=scale&255;packed[at+1]=scale>>8;
 }
 std::vector<uint16_t> shared(k),xs(size_t(count)*k);
 for(unsigned i=0;i<k;++i)shared[i]=output_bits(float(int((i*13+mutation)%41)-20)/32,f.activation);
 for(unsigned slot=0;slot<count;++slot)for(unsigned i=0;i<k;++i)xs[size_t(slot)*k+i]=output_bits(float(int((i*7+slot*11+mutation)%53)-26)/32,f.activation);
 std::array<Route,10> routes{};std::array<uint32_t,10> status{};
 for(unsigned slot=0;slot<10;++slot) {
  routes[slot]={(slot*53+mutation*7)%512,mutation%3,span-(slot%3)};
  if(slot==9)routes[slot].expert_id=511;
  if(mutation==3 && slot==1)routes[slot]=routes[0];
  if(mutation==1 && slot==9)routes[slot].expert_id=512;
  if(mutation==2 && slot==8)routes[slot]={511,6,5};
  if(mutation==3 && slot==7)routes[slot].row_count=0;
  status[slot]=valid_route(routes[slot],bank,rows,span)?0:1;
 }
 std::array<kopt4::Matrix,3> m{};
 std::array<std::vector<uint16_t>,3> ys;
 std::array<std::vector<float>,3> fp;
 for(unsigned proj=0;proj<3;++proj) {
  if(proj==1)for(size_t at=0;at<packed.size();at+=l.bytes)packed[at+1]^=0x80;
  auto& matrix=m[proj];matrix.type=f.type;matrix.rows=rows;matrix.columns=k;matrix.experts=bank;matrix.count=count;matrix.span=span;
  matrix.activation=f.activation;matrix.output_type=Type::BF16;
  auto alloc=[&](const char* label,size_t n){return b.allocate(std::string(label)+std::to_string(proj),n,ownrt::Category::scratch);};
  matrix.w=b.allocate("packed"+std::to_string(proj),packed.size(),ownrt::Category::weights);
  b.upload(matrix.w,packed.data(),packed.size(),"packed-stage");
  matrix.x=alloc("input",proj<2?shared.size()*2:xs.size()*2);
  b.upload(matrix.x,proj<2?shared.data():xs.data(),proj<2?shared.size()*2:xs.size()*2,"x-stage");
  matrix.routes=alloc("routes",sizeof routes);b.upload(matrix.routes,routes.data(),sizeof routes,"route-stage");
  if(proj==1){matrix.x=m[0].x;matrix.routes=m[0].routes;}
  matrix.status=alloc("status",40);matrix.y=alloc("y",count*span*2);matrix.fp32=alloc("fp32",count*span*4);
  ys[proj].resize(count*span);fp[proj].resize(count*span);
  unsigned parts=proj==2?(down_only?4:1):split;
  for(unsigned slot=0;slot<count;++slot)for(unsigned r=0;r<span;++r) {
   float value=bits_float(0x7fc00000);
   if(!status[slot] && r<routes[slot].row_count) {
    size_t off=(size_t(routes[slot].expert_id)*rows+routes[slot].row_begin+r)*rb;
    value=kopt4::row(f.type,packed.data()+off,proj<2?shared.data():xs.data()+slot*k,f.activation,k,parts);
   }
   fp[proj][slot*span+r]=value;ys[proj][slot*span+r]=bf16_bits(value);
  }
 }
 require(!stopping,"cooperative stop before experts");
 wait(d,kopt4::expert_gate_up(d,m[0],m[1],split).last);
 wait(d,kopt4::expert_down(d,m[2],down_only?4:1).last);
 for(unsigned proj=0;proj<3;++proj) {
  b.equal(m[proj].y,ys[proj].data(),count*span*2,"BF16 result");
  b.equal(m[proj].fp32,fp[proj].data(),count*span*4,"FP32 result");
  b.equal(m[proj].status,status.data(),40,"route status");
 }
 std::array<float,10> weights{.25f,-.125f,.0625f,.1875f,.03125f,.09375f,-.0625f,.125f,.0625f,.375f};
 std::array<float,span> expected{};std::array<uint16_t,span> rounded{};
 for(unsigned r=0;r<span;++r){expected[r]=kopt4::combine(ys[2].data(),weights.data(),span,r);rounded[r]=bf16_bits(expected[r]);}
 auto dw=b.allocate("probabilities",40,ownrt::Category::scratch);b.upload(dw,weights.data(),40,"probability-stage");
 auto out=b.allocate("mixture",span*2,ownrt::Category::scratch),full=b.allocate("mixture-fp32",span*4,ownrt::Category::scratch);
 wait(d,kopt4::epilogue(d,m[2].y,dw,out,span,full).last);
 b.equal(out,rounded.data(),span*2,"mixture BF16");b.equal(full,expected.data(),span*4,"mixture FP32");
 b.release();std::cout<<"PASS expert type="<<unsigned(f.type)<<" mutation="<<mutation<<" split="<<split<<" down-split="<<(down_only?4:1)<<'\n'<<std::flush;
}
}
int main(int argc,char** argv) {
 if(argc!=7 || std::string(argv[1])!="--authorized-device-window")return 2;
 std::signal(SIGINT,stop);std::signal(SIGTERM,stop);
 std::unique_ptr<ownrt::Device> d;std::string error;unsigned checks=0;ownrt::Receipt teardown;
 try {
  require(std::string(argv[2])=="3","card3 only");std::string mode=argv[6];
  require(mode=="experts_sg32" || mode=="experts_split4","mode");unsigned split=mode=="experts_split4"?4:1;
  std::vector<Fixture> fixtures;
  for(const auto* name:{"random0-IQ2_S.fixture","random1-IQ3_S.fixture","random0-IQ4_NL.fixture"})fixtures.emplace_back((std::filesystem::path(argv[3])/name).string());
  require(!stopping,"cooperative stop before device");d=std::make_unique<ownrt::Device>(ownrt::make_sycl_device(3));
  for(const auto& f:fixtures)for(unsigned mutation=0;mutation<4;++mutation){exercise(*d,f,mutation,split);++checks;}
  for(unsigned mutation:{0u,1u}){exercise(*d,fixtures[1],mutation,split,true);++checks;}
 }catch(const std::exception& e){error=e.what();}
 if(d){std::ofstream census(argv[5]);census<<d->arena.census()<<'\n';census.close();teardown=d->shutdown(std::chrono::seconds(10));}
 std::ofstream out(argv[4]);out<<"{\"checks\":"<<checks<<",\"error\":"<<ownrt::quote(error)<<",\"teardown\":"<<teardown.json()<<"}\n";out.close();
 if(d && !teardown.safe_to_exit)ownrt::hold_for_supervisor();return !error.empty() || !teardown.safe_to_exit;
}
