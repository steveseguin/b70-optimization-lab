// CPU-device bitwise test (OpenCL CPU, GPU blocked by nodri.so) of OWNRT_DRAFT_HEAD_RAW's BF16-activation raw Q6_K
// kernel (p33::raw::dense_rows_bf16<2560,1,1>) against a host replica of the expanded production kernel
// Kernel<0,Q6_K,2560,1,false> (dense_lane<Q6_K,2560,false>: value*float(bf16<<16), product then add, adjacent-pair tree,
// output iq3::bf16_bits), on real rows of the model's logits head (rows 0..36 and 91355..91391 of the 91392-row prefix).
#include <sycl/sycl.hpp>
#include "stage2/packet10-kopt5/expanded.hpp"
#include "stage2/packet194-expert-diet-engine/p33_dense_raw.hpp"
#include <cstdio>
#include <fcntl.h>
#include <random>
#include <unistd.h>
#include <vector>
using iq3::Type;
static uint16_t ref_row(const uint8_t* w,const uint16_t* x,uint32_t K){
 float s[32];
 for(unsigned lane=0;lane<32;++lane){float sum=0;
  for(unsigned tile=lane*8;tile<K;tile+=256){const float scale=iq3::bits_float(iq3::u32(w+K+4*(tile/16)));
   for(unsigned j=0;j<8;++j){float value=scale*float(iq3::signed8(w[tile+j]));float input=iq3::bits_float(uint32_t(x[tile+j])<<16);float product=value*input;sum=sum+product;}}
  s[lane]=sum;}
 for(unsigned width=1;width<32;width*=2)for(unsigned l=0;l<32;l+=2*width)s[l]=s[l]+s[l+width];
 return iq3::bf16_bits(s[0]);
}
int main(int argc,char** argv){
 if(argc<3){std::fprintf(stderr,"usage: %s head-file head-offset\n",argv[0]);return 2;}
 sycl::queue q{sycl::device{sycl::cpu_selector_v},sycl::property::queue::in_order{}};
 std::printf("device: %s\n",q.get_device().get_info<sycl::info::device::name>().c_str());
 constexpr uint32_t K=2560,rows=37;const size_t rb=2100,erb=iq3::expanded::row_bytes(Type::Q6_K,K);int failures=0;
 std::mt19937 g(99);std::uniform_real_distribution<float> u(-3.f,3.f);
 for(size_t first:{size_t(0),size_t(91392-rows)}){
  std::vector<uint8_t> gguf(rows*rb);int fd=::open(argv[1],O_RDONLY);if(fd<0||::pread(fd,gguf.data(),gguf.size(),off_t(std::stoull(argv[2])+first*rb))!=ssize_t(gguf.size())){perror("read");return 1;}::close(fd);
  const auto expanded=iq3::expanded::expand(Type::Q6_K,gguf.data(),gguf.size(),K);const auto raw=denseraw::repack(Type::Q6_K,gguf.data(),gguf.size(),K);
  for(int trial=0;trial<3;++trial){
   std::vector<uint16_t> x(K);for(auto& v:x)v=iq3::bf16_bits(trial==2?u(g)*1e-3f:u(g));
   std::vector<uint16_t> want(rows);for(uint32_t r=0;r<rows;++r)want[r]=ref_row(expanded.data()+r*erb,x.data(),K);
   uint8_t* w=sycl::malloc_device<uint8_t>(raw.size(),q);uint16_t* xd=sycl::malloc_device<uint16_t>(K,q);uint16_t* y=sycl::malloc_device<uint16_t>(rows+64,q);
   q.memcpy(w,raw.data(),raw.size()).wait();q.memcpy(xd,x.data(),K*2).wait();std::vector<uint16_t> sentinel(rows+64,0xbeef);q.memcpy(y,sentinel.data(),sentinel.size()*2).wait();
   p33::raw::RowsKernelBF16<K,1,1> k{w,xd,y,rows,uint32_t(rb)};q.parallel_for(sycl::nd_range<1>((size_t(rows)*32+127)/128*128,128),k).wait();
   std::vector<uint16_t> got(rows+64);q.memcpy(got.data(),y,got.size()*2).wait();
   size_t bad=0;for(uint32_t r=0;r<rows;++r)bad+=got[r]!=want[r];bool tail=true;for(uint32_t r=rows;r<rows+64;++r)tail&=got[r]==0xbeef;
   std::printf("  rows %zu..%zu trial %d: mismatches %zu, out-of-range stores %s\n",first,first+rows-1,trial,bad,tail?"none":"FOUND");failures+=bad||!tail;
   sycl::free(w,q);sycl::free(xd,q);sycl::free(y,q);
  }
 }
 std::printf("%s\n",failures?"FAILED":"ALL PASSED");return failures?1:0;
}
