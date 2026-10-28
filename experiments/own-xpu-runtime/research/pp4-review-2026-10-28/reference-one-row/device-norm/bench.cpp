#include "production-kernel-prefix.hpp"
#include <fstream>
#include <iostream>
#include <filesystem>
#include <atomic>
#include <cstring>
namespace ownrt {std::uint64_t next_handle(){static std::atomic<std::uint64_t>n{1};return n.fetch_add(1);}}
static std::vector<float> read(std::string p){std::ifstream f(p,std::ios::binary);std::vector<float>v(10240);f.read((char*)v.data(),40960);if(f.gcount()!=40960)throw std::runtime_error("input extent");return v;}
int main(int argc,char**argv){try{if(argc!=3)throw std::runtime_error("usage bench INPUTDIR FRESHOUTPUTDIR");std::string in=argv[1],out=argv[2];if(!std::filesystem::create_directory(out))throw std::runtime_error("fresh output required");
 auto x=read(in+"/hc-a-input.f32"),gain=read(in+"/hc-a-gain.f32"),ref=read(in+"/hc-a-output.f32");
 sycl::queue q(sycl::gpu_selector_v,{sycl::property::queue::in_order(),sycl::property::queue::enable_profiling()});std::cout<<"device="<<q.get_device().get_info<sycl::info::device::name>()<<"\n";
 float*dx=sycl::malloc_device<float>(10240,q),*dg=sycl::malloc_device<float>(10240,q),*dy=sycl::malloc_device<float>(10240,q),*scratch=sycl::malloc_device<float>(320,q);int32_t*ctrl=sycl::malloc_device<int32_t>(3,q);if(!dx||!dg||!dy||!scratch||!ctrl)throw std::runtime_error("allocation");int32_t hctrl[3]={0,243,1};q.memcpy(dx,x.data(),40960);q.memcpy(dg,gain.data(),40960);q.memcpy(ctrl,hctrl,12);q.memset(dy,0xcd,40960);q.memset(scratch,0xcd,1280);q.wait_and_throw();
 ng::Shape s;s.op=ng::norm;s.tokens=1;s.width=2560;s.heads=4;s.flags=ng::f32_activations_flag|8;s.capacity=4096;std::array<void*,20>a{};a[0]=dx;a[1]=dg;a[2]=dy;a[15]=ctrl;a[17]=ctrl+1;a[18]=ctrl+2;a[19]=scratch;
 specialised::Kernel<ng::norm,0,2560,4>stage0(s);specialised::Kernel<ng::norm,1,2560,4>stage1(s);auto e0=stage0.submit(q,a,{});auto e1=stage1.submit(q,a,{e0});e1.wait_and_throw();std::vector<float>actual(10240);q.memcpy(actual.data(),dy,40960);q.memcpy(hctrl,ctrl,12);q.wait_and_throw();
 std::ofstream f(out+"/device-output.f32",std::ios::binary);f.write((char*)actual.data(),40960);f.close();size_t unequal=0;double max=0;for(int i=0;i<10240;++i){unequal+=std::memcmp(&actual[i],&ref[i],4)!=0;max=std::max(max,std::abs(double(actual[i])-ref[i]));}std::cout<<"error="<<hctrl[0]<<" unequal="<<unequal<<" max_abs="<<max<<" device_bytes="<<(3*40960+1280+12)<<"\n";
 sycl::free(dx,q);sycl::free(dg,q);sycl::free(dy,q);sycl::free(scratch,q);sycl::free(ctrl,q);return hctrl[0]?2:unequal?1:0;
 }catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 3;}}
