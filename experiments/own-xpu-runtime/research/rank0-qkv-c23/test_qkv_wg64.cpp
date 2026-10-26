// CPU-device exactness test for the QKV WG64 scheduling variant; GPU access is blocked by nodri.so.
#include <sycl/sycl.hpp>
#include "stage2/packet10-kopt5/expanded.hpp"
#include "stage2/packet194-expert-diet-engine/p33_dense_raw.hpp"
#include <cstdio>
#include <fcntl.h>
#include <random>
#include <unistd.h>
#include <vector>

static std::vector<uint8_t> read_rows(const char* file,size_t offset,size_t rb,size_t first,size_t n){
 std::vector<uint8_t> v(rb*n);int fd=::open(file,O_RDONLY);if(fd<0){perror(file);std::exit(1);}
 if(::pread(fd,v.data(),v.size(),off_t(offset+first*rb))!=ssize_t(v.size())){perror("pread");std::exit(1);}::close(fd);return v;
}
static float ref_row(const uint8_t* w,const float* x){
 float s[32];
 for(unsigned lane=0;lane<32;++lane){float sum=0;
  for(unsigned tile=lane*8;tile<2560;tile+=256){const float scale=iq3::bits_float(iq3::u32(w+2560+4*(tile/16)));
   for(unsigned j=0;j<8;++j){float value=scale*float(iq3::signed8(w[tile+j]));float product=value*x[tile+j];sum=sum+product;}}
  s[lane]=sum;
 }
 for(unsigned width=1;width<32;width*=2)for(unsigned l=0;l<32;l+=2*width)s[l]=s[l]+s[l+width];
 return s[0];
}
template<unsigned WG> static size_t run(sycl::queue& q,const uint8_t* raw,const float* x,const std::vector<float>& want){
 constexpr uint32_t rows=37,K=2560,rb=2100,groups=rows;const size_t global=(size_t(groups)*32+WG-1)/WG*WG;
 uint8_t* w=sycl::malloc_device<uint8_t>(rows*rb,q);float* xd=sycl::malloc_device<float>(K,q);float* y=sycl::malloc_device<float>(rows+64,q);
 q.memcpy(w,raw,rows*rb).wait();q.memcpy(xd,x,K*4).wait();std::vector<float> sentinel(rows+64,-777.f);q.memcpy(y,sentinel.data(),sentinel.size()*4).wait();
 q.parallel_for(sycl::nd_range<1>(global,WG),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{p33::raw::dense_rows<iq3::Type::Q6_K,K,1,1>(w,xd,y,rows,rb,groups,1,it);}).wait();
 std::vector<float> got(rows+64);q.memcpy(got.data(),y,got.size()*4).wait();size_t bad=0;
 for(uint32_t r=0;r<rows;++r)bad+=std::bit_cast<uint32_t>(got[r])!=std::bit_cast<uint32_t>(want[r]);
 for(size_t i=rows;i<got.size();++i)bad+=got[i]!=-777.f;
 std::printf("WG%u: %u outputs plus 64 sentinels, mismatches %zu\n",WG,rows,bad);
 sycl::free(w,q);sycl::free(xd,q);sycl::free(y,q);return bad;
}
int main(int argc,char**argv){
 if(argc!=3){std::fprintf(stderr,"usage: %s qkv-gguf qkv-data-offset\n",argv[0]);return 2;}
 sycl::queue q{sycl::device{sycl::cpu_selector_v},sycl::property::queue::in_order{}};
 std::printf("device: %s\n",q.get_device().get_info<sycl::info::device::name>().c_str());
 constexpr uint32_t rows=37,K=2560;const auto gguf=read_rows(argv[1],std::stoull(argv[2]),2100,0,rows);
 const auto expanded=iq3::expanded::expand(iq3::Type::Q6_K,gguf.data(),gguf.size(),K);const auto raw=denseraw::repack(iq3::Type::Q6_K,gguf.data(),gguf.size(),K);
 std::mt19937 g(1234);std::uniform_real_distribution<float> u(-1.f,1.f);std::vector<float>x(K);for(auto&v:x)v=u(g);
 std::vector<float>want(rows);for(uint32_t r=0;r<rows;++r)want[r]=ref_row(expanded.data()+r*3380,x.data());
 const size_t bad=run<128>(q,raw.data(),x.data(),want)+run<64>(q,raw.data(),x.data(),want);
 std::printf("%s\n",bad?"FAILED":"ALL PASSED");return bad?1:0;
}
