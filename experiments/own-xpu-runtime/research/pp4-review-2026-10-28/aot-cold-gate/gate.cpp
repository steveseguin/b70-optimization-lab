// Prepared source only: one production Q5_K shape; no engine/state transaction.
#include <atomic>
#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#include "stage2/packet194-expert-diet-engine/p33_submit.hpp"
#include "stage2/packet194-expert-diet-engine/performance.hpp"
#include "stage2/packet194-expert-diet-engine/adapter.hpp"
#include "stage1/packet3-prep/src/sycl_operation.hpp"
#include "stage2/packet194-expert-diet-engine/prepared_submission.hpp"
#define GSQN_RUNTIME_HEADERS_PROVIDED
#include "gsq-rco-iq3s/integration/build/private/additive/packed.hpp"
#include "gsq-rco-iq3s/dense-packed-block/engine/build/source/block.hpp"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstring>
#include <fstream>
#include <filesystem>
#include <iostream>
#include <stdexcept>
#include <vector>
namespace ownrt { std::uint64_t next_handle(){static std::atomic<std::uint64_t> n{1};return n.fetch_add(1);} }
constexpr uint32_t R=10240,K=2560,RB=1760;constexpr size_t WB=size_t(R)*RB;
static void need(bool ok,const char* why){if(!ok)throw std::runtime_error(why);}
static std::vector<uint8_t> read(const char* path,size_t size){std::ifstream f(path,std::ios::binary|std::ios::ate);need(f.good()&&f.tellg()==std::streamoff(size),"exact fixture extent");f.seekg(0);std::vector<uint8_t> b(size);need(bool(f.read(reinterpret_cast<char*>(b.data()),size)),"fixture read");return b;}
static sycl::event scalar(sycl::queue&q,const uint8_t*w,const float*x,float*y){
 denseblock::DenseBlockOperation<13,true> op;op.s=gsqn::Shape{R,K,RB,1,1,false,false,true,false};
 std::array<void*,5> p{(void*)w,(void*)x,(void*)y,(void*)x,(void*)y};return op.submit(q,std::span<void*const>(p.data(),p.size()),{});
}
template<unsigned T> static sycl::event batch(sycl::queue&q,const uint8_t*w,const float*x,float*y,unsigned width){
 reuse2::Op<reuse2::Block32<13,denseblock::BlockElement>,1,T,4,128,0> op;
 op.rows=R;op.k=K;op.tokens=width;op.rb=RB;
 std::array<void*,3> p{(void*)w,(void*)x,(void*)y};return op.submit(q,std::span<void*const>(p.data(),p.size()),{});
}
int main(int argc,char**argv){const auto main_start=std::chrono::steady_clock::now();try{
 need(argc==5,"usage: gate weights.q5k inputs3x2560.f32 timing_iterations0..1000 fresh-output-directory");
 std::filesystem::path output=argv[4];need(std::filesystem::create_directory(output),"fresh exclusive output directory required");
 auto stamp=[](auto start){return std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-start).count();};
 auto save=[&](const std::string&name,const std::vector<uint32_t>&data){std::ofstream f(output/name,std::ios::binary);f.write(reinterpret_cast<const char*>(data.data()),data.size()*4);need(bool(f),"output evidence write");};
 need(std::getenv("FilterBdfPath")&&*std::getenv("FilterBdfPath"),"explicit coordinated physical BDF required");
 need(std::getenv("OWNRT_DENSE_DECODE_V2")&&std::string(std::getenv("OWNRT_DENSE_DECODE_V2"))=="1","registered scalar V2 flag required");
 unsigned iters=0;if(argc==5){std::string s=argv[3];size_t used=0;auto n=std::stoul(s,&used);need(used==s.size()&&n<=1000,"bounded timing iterations");iters=unsigned(n);}
 auto wh=read(argv[1],WB),xb=read(argv[2],3*K*4);std::vector<float> xh(3*K);std::memcpy(xh.data(),xb.data(),xb.size());for(float v:xh)need(std::isfinite(v),"finite actual input rows");
 sycl::queue q{sycl::gpu_selector_v,sycl::property_list{sycl::property::queue::in_order(),sycl::property::queue::enable_profiling()}};
 auto device=q.get_device();need(device.has(sycl::aspect::ext_intel_pci_address),"PCI-address capability required");
 need(device.get_info<sycl::ext::intel::info::device::pci_address>()==std::string(std::getenv("FilterBdfPath")),"selected physical BDF differs from requested BDF");
 std::cout<<"{\"metric\":\"main_to_queue_ready_us\",\"value\":"<<stamp(main_start)<<"}\n";
 auto*w=sycl::malloc_device<uint8_t>(WB,q);auto*x=sycl::malloc_device<float>(3*K,q);auto*ref=sycl::malloc_device<float>(3*R,q);auto*storage=sycl::malloc_device<uint32_t>(3*R+64,q);need(w&&x&&ref&&storage,"bounded device allocation");float*y=reinterpret_cast<float*>(storage+32);
 q.memcpy(w,wh.data(),WB);q.memcpy(x,xh.data(),3*K*4);q.wait_and_throw();need(gsqn::v2::fits<13>(w,R,K,RB),"actual scalar V2 dispatch geometry/alignment");
 std::cout<<"{\"metric\":\"main_to_fixture_device_ready_us\",\"value\":"<<stamp(main_start)<<"}\n";
 for(unsigned width:{1u,2u,3u}){
  auto scalar_start=std::chrono::steady_clock::now();for(unsigned row=0;row<width;++row)scalar(q,w,x+row*K,ref+row*R);q.wait_and_throw();if(width==1)std::cout<<"{\"metric\":\"main_to_first_scalar_complete_us\",\"value\":"<<stamp(main_start)<<"}\n";
  std::cout<<"{\"metric\":\"scalar_initial_callset_host_us\",\"width\":"<<width<<",\"value\":"<<stamp(scalar_start)<<"}\n";
  std::vector<uint32_t> want(width*R);q.memcpy(want.data(),ref,want.size()*4).wait_and_throw();save("scalar-width"+std::to_string(width)+".u32",want);
  for(unsigned tile:{2u,4u}){
   auto fill_start=std::chrono::steady_clock::now();q.memset(storage,0xa5,(3*R+64)*4).wait_and_throw();std::cout<<"{\"metric\":\"guard_fill_host_us\",\"width\":"<<width<<",\"tile_tokens\":"<<tile<<",\"value\":"<<stamp(fill_start)<<"}\n";auto candidate_start=std::chrono::steady_clock::now();if(tile==2)batch<2>(q,w,x,y,width);else batch<4>(q,w,x,y,width);q.wait_and_throw();
   std::cout<<"{\"metric\":\"candidate_initial_call_host_us\",\"width\":"<<width<<",\"tile_tokens\":"<<tile<<",\"value\":"<<stamp(candidate_start)<<"}\n";
   std::vector<uint32_t> got(3*R+64);q.memcpy(got.data(),storage,got.size()*4).wait_and_throw();save("candidate-width"+std::to_string(width)+"-tile"+std::to_string(tile)+".u32",got);size_t differences=0,guard_errors=0;std::vector<size_t> per_row(width);
   for(size_t i=0;i<want.size();++i)if(got[i+32]!=want[i]){++differences;++per_row[i/R];}
   for(size_t i=0;i<32;++i)guard_errors+=got[i]!=0xa5a5a5a5;
   for(size_t i=32+want.size();i<got.size();++i)guard_errors+=got[i]!=0xa5a5a5a5;
   std::cout<<"{\"width\":"<<width<<",\"tile_tokens\":"<<tile<<",\"outputs\":"<<want.size()<<",\"bit_differences\":"<<differences<<",\"guard_errors\":"<<guard_errors<<",\"per_row_bit_differences\":[";for(unsigned row=0;row<width;++row)std::cout<<(row?",":"")<<per_row[row];std::cout<<"]}\n";
   need(!differences&&!guard_errors,"bitwise or output extent gate failed; timing refused");
  }
 }
 // Timing is explicitly optional and only reached after ALL six correctness gates.
 for(unsigned width:{1u,2u,3u})for(unsigned tile:{2u,4u})if(iters){
  auto run=[&](bool multi){if(multi){if(tile==2)batch<2>(q,w,x,y,width);else batch<4>(q,w,x,y,width);}else for(unsigned row=0;row<width;++row)scalar(q,w,x+row*K,ref+row*R);q.wait_and_throw();};
  for(int n=0;n<3;++n){run(false);run(true);}std::vector<double> a,b;
  for(unsigned n=0;n<iters;++n)for(bool multi:{bool(n%2),!bool(n%2)}){auto t=std::chrono::steady_clock::now();run(multi);double us=std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-t).count();(multi?b:a).push_back(us);}
  std::sort(a.begin(),a.end());std::sort(b.begin(),b.end());std::cout<<"{\"width\":"<<width<<",\"tile_tokens\":"<<tile<<",\"iterations\":"<<iters<<",\"serial_host_us_median\":"<<a[a.size()/2]<<",\"multirow_host_us_median\":"<<b[b.size()/2]<<",\"scope\":\"warm stateless kernel calls plus queue wait; not decode throughput\"}\n";
 }
 std::cout<<"{\"metric\":\"main_to_work_complete_us\",\"value\":"<<stamp(main_start)<<"}\n";
 sycl::free(w,q);sycl::free(x,q);sycl::free(ref,q);sycl::free(storage,q);return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
