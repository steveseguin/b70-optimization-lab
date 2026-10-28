#include "production-round2-prefix.hpp"
#include <fstream>
#include <filesystem>
#include <iostream>
#include <atomic>
#include <cstring>
#include <iomanip>
namespace ownrt {uint64_t next_handle(){static std::atomic<uint64_t>n{1};return n++;}}
void need(bool b,const char*s){if(!b)throw std::runtime_error(s);}
std::vector<float>read(const std::string&p,size_t n){std::ifstream f(p,std::ios::binary);std::vector<float>x(n);f.read((char*)x.data(),n*4);need(size_t(f.gcount())==n*4&&f.peek()==EOF,"exact input extent");return x;}
void save(const std::string&p,const std::vector<float>&x){std::ofstream f(p,std::ios::binary);f.write((char*)x.data(),x.size()*4);need(bool(f),"output write");}
int main(int argc,char**argv){try{
 need(argc==4,"history controls freshoutput");need(std::getenv("FilterBdfPath")&&std::getenv("OWNRT_GDN_PREP")&&std::string(std::getenv("OWNRT_GDN_PREP"))=="1","explicit BDF and preparation mode");
 std::string out=argv[3];need(std::filesystem::create_directory(out),"fresh output");constexpr int T=244,Y=6144,S=786432,P=4192;
 auto raw=read(argv[1],T*65920/4),w=read(argv[2],96);std::vector<float>conv(T*10240),alpha(T*48),beta(T*48),expected(T*Y);
 for(int r=0;r<T;++r){auto*x=raw.data()+r*16480;std::memcpy(conv.data()+r*10240,x,40960);std::memcpy(alpha.data()+r*48,x+10240,192);std::memcpy(beta.data()+r*48,x+10288,192);std::memcpy(expected.data()+r*Y,x+10336,24576);}
 sycl::queue q(sycl::gpu_selector_v,{sycl::property::queue::in_order()});auto d=q.get_device();need(d.has(sycl::aspect::ext_intel_pci_address),"PCI identity capability");auto bdf=d.get_info<sycl::ext::intel::info::device::pci_address>();need(bdf==std::getenv("FilterBdfPath"),"physical BDF mismatch");std::cout<<"bdf="<<bdf<<" device="<<d.get_info<sycl::info::device::name>()<<"\n";
 size_t bytes=0;std::vector<void*>allocations;auto alloc=[&](size_t n){auto*p=sycl::malloc_device<float>(n,q);need(p,"allocation");bytes+=n*4;allocations.push_back(p);return p;};
 auto*dc=alloc(conv.size()),*da=alloc(alpha.size()),*db=alloc(beta.size()),*dw=alloc(96),*dy=alloc(T*Y),*prep=alloc(T*P),*s0=alloc(S),*s1=alloc(S);auto*ctl=(int32_t*)alloc(3*T);
 std::vector<int32_t>ctrl(3*T);for(int r=0;r<T;++r){ctrl[3*r]=0;ctrl[3*r+1]=r;ctrl[3*r+2]=1;}
 q.memcpy(dc,conv.data(),conv.size()*4);q.memcpy(da,alpha.data(),alpha.size()*4);q.memcpy(db,beta.data(),beta.size()*4);q.memcpy(dw,w.data(),384);q.memcpy(ctl,ctrl.data(),ctrl.size()*4);q.memset(s0,0,S*4);q.memset(s1,0xcd,S*4);q.memset(dy,0xcd,T*Y*4);q.memset(prep,0xcd,T*P*4);q.wait_and_throw();
 ng::Shape shape;shape.op=ng::gdn;shape.tokens=1;shape.capacity=4096;shape.flags=94;round2::Kernel<ng::gdn,1>producer(shape);round2::Kernel<ng::gdn,0>consumer(shape);std::vector<sycl::event>deps;
 for(int r=0;r<T;++r){std::array<void*,20>a{};a[0]=dc+r*10240;a[1]=da+r*48;a[2]=db+r*48;a[3]=dw;a[4]=dw+48;a[5]=r%2?s1:s0;a[6]=dy+r*Y;a[7]=r%2?s0:s1;a[15]=ctl+3*r;a[17]=ctl+3*r+1;a[18]=ctl+3*r+2;a[19]=prep+r*P;auto first=producer.submit(q,a,deps);auto last=consumer.submit(q,a,{first});deps={last};}
 q.wait_and_throw();std::vector<float>actual(T*Y),prepared(T*P),state(S);q.memcpy(actual.data(),dy,actual.size()*4);q.memcpy(prepared.data(),prep,prepared.size()*4);q.memcpy(state.data(),s0,S*4);q.memcpy(ctrl.data(),ctl,ctrl.size()*4);q.wait_and_throw();save(out+"/device-y.f32",actual);save(out+"/device-prepared.f32",prepared);save(out+"/device-final-state.f32",state);
 size_t unequal=0;double max=0,sum=0;for(size_t i=0;i<actual.size();++i){need(std::isfinite(actual[i])&&std::isfinite(expected[i]),"nonfinite output");unequal+=std::memcmp(&actual[i],&expected[i],4)!=0;double delta=double(actual[i])-expected[i];max=std::max(max,std::abs(delta));sum+=delta*delta;}for(int r=0;r<T;++r)need(ctrl[3*r]==0,"production error word");
 std::cout<<std::setprecision(17)<<"unequal="<<unequal<<" max_abs="<<max<<" rms="<<std::sqrt(sum/actual.size())<<" device_bytes="<<bytes<<" rows=244 tokens_per_launch=1 flags=94 local=32 SIMD=32\n";for(auto*p:allocations)sycl::free(p,q);return unequal?1:0;
 }catch(std::exception&e){std::cerr<<e.what()<<"\n";return 3;}}
