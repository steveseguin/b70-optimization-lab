#include "stage2/packet6-kopt/dense_v2.hpp"
#include "stage2/packet194-expert-diet-engine/prepared_submission.hpp"
#include <fstream>
#include <atomic>
namespace ownrt {std::uint64_t next_handle(){static std::atomic<std::uint64_t>n{1};return n.fetch_add(1);}}
#include <filesystem>
#include <iostream>
#include <vector>
#include <cstring>
#include <iomanip>
static std::vector<char>read(std::string p,size_t n){std::ifstream f(p,std::ios::binary);std::vector<char>v(n);f.read(v.data(),n);if(f.gcount()!=n)throw std::runtime_error("extent");return v;}
int main(int argc,char**argv){try{if(argc!=3)throw std::runtime_error("inputdir freshoutdir");std::string in=argv[1],out=argv[2];if(!std::filesystem::create_directory(out))throw std::runtime_error("fresh output");auto w=read(in+"/weight.bf16",6553600),x=read(in+"/input.f32",40960),host=read(in+"/cpu-output/native-host.f32",1280),ref=read(in+"/cpu-output/ggml-f64.f32",1280);
 sycl::queue q(sycl::gpu_selector_v,{sycl::property::queue::in_order(),sycl::property::queue::enable_profiling()});std::cout<<q.get_device().get_info<sycl::info::device::name>()<<"\n";auto*dw=sycl::malloc_device<uint8_t>(6553600,q);auto*dx=sycl::malloc_device<float>(10240,q);auto*dy=sycl::malloc_device<float>(320,q);if(!dw||!dx||!dy)throw std::runtime_error("allocation");q.memcpy(dw,w.data(),w.size());q.memcpy(dx,x.data(),x.size());q.memset(dy,0xcd,1280);q.wait_and_throw();std::array<iq3::kopt::dense_v2::Mat,4>m{};m[0]={dw,dx,dy,320,10240,20480,0};unsigned count=1;const size_t global=320*32;
 auto ev=ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(sycl::range<1>(global),sycl::range<1>(128))](sycl::handler&h){h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{iq3::kopt::dense_v2::bf16_multi<1,8>(m,count,it);}));});ev.wait_and_throw();std::vector<float>actual(320);q.memcpy(actual.data(),dy,1280).wait_and_throw();std::ofstream f(out+"/device-output.f32",std::ios::binary);f.write((char*)actual.data(),1280);f.close();size_t nh=0,nr=0;double mh=0,mr=0;for(int i=0;i<320;++i){float h,r;std::memcpy(&h,host.data()+4*i,4);std::memcpy(&r,ref.data()+4*i,4);nh+=std::memcmp(&h,&actual[i],4)!=0;nr+=std::memcmp(&r,&actual[i],4)!=0;mh=std::max(mh,std::abs(double(h)-actual[i]));mr=std::max(mr,std::abs(double(r)-actual[i]));}std::cout<<std::setprecision(17)<<"host_unequal="<<nh<<" host_max="<<mh<<" reference_unequal="<<nr<<" reference_max="<<mr<<" device_bytes=6595840\n";sycl::free(dw,q);sycl::free(dx,q);sycl::free(dy,q);return nh?1:0;
 }catch(std::exception&e){std::cerr<<e.what()<<"\n";return 3;}}
