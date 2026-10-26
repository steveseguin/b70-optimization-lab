// CPU-device bitwise test (OpenCL CPU, GPU blocked by nodri.so) of the OWNRT_DENSE_RAW kernels before any GPU launch:
// p33::raw::dense_rows<T,K,R,U> (decode rows and token rows) and the reuse2 tiles over raw rows (Reuse2Raw<T>), against a
// host replica of the expanded p33 kernel (Kernel<0,T,K,1,true>: dense_lane<T,K,true> per lane, adjacent-pair tree),
// on real rows of the model's GGUF (head Q6_K, attention Q8_0). Also out-of-range rows/tokens (partial tiles).
#include <sycl/sycl.hpp>
#include "stage2/packet10-kopt5/expanded.hpp"
#include "stage2/packet194-expert-diet-engine/p33_dense_raw.hpp"
#include <cstdio>
#include <fcntl.h>
#include <random>
#include <unistd.h>
#include <vector>
using iq3::Type;
// The production tile list of prefill_reuse2_op.hpp (REUSE2_CONFIGS), restated (that header needs the engine runtime).
template<unsigned RW,unsigned T,unsigned S,unsigned GRF,unsigned O=0> struct Cfg {static constexpr unsigned rw=RW,t=T,s=S,grf=GRF,o=O;};
static std::vector<uint8_t> read_rows(const char* file,size_t offset,size_t rb,size_t first,size_t n){
 std::vector<uint8_t> v(rb*n);int fd=::open(file,O_RDONLY);if(fd<0){perror(file);std::exit(1);}
 if(::pread(fd,v.data(),v.size(),off_t(offset+first*rb))!=ssize_t(v.size())){perror("pread");std::exit(1);}::close(fd);return v;
}
// Host replica of p33 Kernel<0,T,K,1,true> on expanded rows (dense_lane<T,K,true> + subgroup adjacent-pair tree).
template<unsigned G> static float ref_row(const uint8_t* w,const float* x,uint32_t K){
 float s[32];
 for(unsigned lane=0;lane<32;++lane){float sum=0;
  for(unsigned tile=lane*8;tile<K;tile+=256){const float scale=iq3::bits_float(iq3::u32(w+K+4*(tile/G)));
   for(unsigned j=0;j<8;++j){float value=scale*float(iq3::signed8(w[tile+j]));float input=x[tile+j];float product=value*input;sum=sum+product;}}
  s[lane]=sum;}
 for(unsigned width=1;width<32;width*=2)for(unsigned l=0;l<32;l+=2*width)s[l]=s[l]+s[l+width];
 return s[0];
}
static int failures=0;
static void report(const char* what,const std::vector<float>& got,const std::vector<float>& want){
 size_t bad=0;for(size_t i=0;i<want.size();++i)bad+=std::bit_cast<uint32_t>(got[i])!=std::bit_cast<uint32_t>(want[i]);
 std::printf("  %-44s outputs %6zu  mismatches %zu %s\n",what,want.size(),bad,bad?"FAIL":"ok");failures+=bad!=0;
}
template<Type T,unsigned K,unsigned R,unsigned U> void rows_case(sycl::queue& q,const uint8_t* raw,uint32_t rows,uint32_t tokens,const float* x,const std::vector<float>& want){
 const uint32_t rb=uint32_t(denseraw::row_bytes(T,K)),groups=(rows+R-1)/R;
 uint8_t* w=sycl::malloc_device<uint8_t>(size_t(rows)*rb,q);float* xd=sycl::malloc_device<float>(size_t(tokens)*K,q);float* y=sycl::malloc_device<float>(size_t(tokens)*rows+64,q);
 q.memcpy(w,raw,size_t(rows)*rb).wait();q.memcpy(xd,x,size_t(tokens)*K*4).wait();
 std::vector<float> sentinel(size_t(tokens)*rows+64,-777.f);q.memcpy(y,sentinel.data(),sentinel.size()*4).wait();
 const size_t global=(size_t(groups)*tokens*32+127)/128*128;
 q.parallel_for(sycl::nd_range<1>(global,128),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{p33::raw::dense_rows<T,K,R,U>(w,xd,y,rows,rb,groups,tokens,it);}).wait();
 std::vector<float> got(size_t(tokens)*rows+64);q.memcpy(got.data(),y,got.size()*4).wait();
 bool tail=true;for(size_t i=size_t(tokens)*rows;i<got.size();++i)tail&=got[i]==-777.f;if(!tail){std::printf("  out-of-range store\n");++failures;}
 got.resize(size_t(tokens)*rows);char name[96];std::snprintf(name,sizeof name,"%s dense_rows R%u U%u rows %u tokens %u",T==Type::Q6_K?"Q6_K":"Q8_0",R,U,rows,tokens);report(name,got,want);
 sycl::free(w,q);sycl::free(xd,q);sycl::free(y,q);
}
template<Type T,class C> void tile_case(sycl::queue& q,const uint8_t* raw,uint32_t rows,uint32_t K,uint32_t tokens,const float* x,const std::vector<float>& want){
 const uint32_t rb=uint32_t(denseraw::row_bytes(T,K));
 uint8_t* w=sycl::malloc_device<uint8_t>(size_t(rows)*rb,q);float* xd=sycl::malloc_device<float>(size_t(tokens)*K,q);float* y=sycl::malloc_device<float>(size_t(tokens)*rows,q);
 q.memcpy(w,raw,size_t(rows)*rb).wait();q.memcpy(xd,x,size_t(tokens)*K*4).wait();q.memset(y,0xff,size_t(tokens)*rows*4).wait();
 auto p=reuse2::prepare<p33::raw::Reuse2Raw<T>,C::rw,C::t,C::s,C::grf,C::o>(w,xd,y,rows,K,tokens,rb);auto kernel=p.kernel;
 q.parallel_for(p.range,kernel).wait();
 std::vector<float> got(size_t(tokens)*rows);q.memcpy(got.data(),y,got.size()*4).wait();
 char name[96];std::snprintf(name,sizeof name,"%s reuse2 RW%u T%u S%u O%u rows %u tokens %u",T==Type::Q6_K?"Q6_K":"Q8_0",C::rw,C::t,C::s,C::o,rows,tokens);report(name,got,want);
 sycl::free(w,q);sycl::free(xd,q);sycl::free(y,q);
}
template<Type T,unsigned K> void suite(sycl::queue& q,const char* file,size_t offset,size_t first){
 constexpr unsigned G=T==Type::Q6_K?16:32;const uint32_t rows=37,maxtok=32;
 const size_t rb=denseraw::row_bytes(T,K),erb=iq3::expanded::row_bytes(T,K);
 const auto gguf=read_rows(file,offset,rb,first,rows);const auto expanded=iq3::expanded::expand(T,gguf.data(),gguf.size(),K);const auto raw=denseraw::repack(T,gguf.data(),gguf.size(),K);
 std::mt19937 g(1234+K);std::uniform_real_distribution<float> u(-1.f,1.f);std::vector<float> x(size_t(maxtok)*K);for(auto& v:x)v=u(g);
 for(uint32_t tokens:{1u,3u,13u,32u}){
  std::vector<float> want(size_t(tokens)*rows);for(uint32_t t=0;t<tokens;++t)for(uint32_t r=0;r<rows;++r)want[size_t(t)*rows+r]=ref_row<G>(expanded.data()+r*erb,x.data()+size_t(t)*K,K);
  if(tokens<=3){rows_case<T,K,1,1>(q,raw.data(),rows,tokens,x.data(),want);rows_case<T,K,2,1>(q,raw.data(),rows,tokens,x.data(),want);rows_case<T,K,2,2>(q,raw.data(),rows,tokens,x.data(),want);
   rows_case<T,K,4,1>(q,raw.data(),rows,tokens,x.data(),want);rows_case<T,K,4,2>(q,raw.data(),rows,tokens,x.data(),want);rows_case<T,K,8,2>(q,raw.data(),rows,tokens,x.data(),want);
   rows_case<T,K,1,2>(q,raw.data(),rows,tokens,x.data(),want);rows_case<T,K,1,4>(q,raw.data(),rows,tokens,x.data(),want);rows_case<T,K,8,1>(q,raw.data(),rows,tokens,x.data(),want);}
  if(tokens>1){tile_case<T,Cfg<1,32,4,256>>(q,raw.data(),rows,K,tokens,x.data(),want);tile_case<T,Cfg<4,8,4,256>>(q,raw.data(),rows,K,tokens,x.data(),want);
   tile_case<T,Cfg<1,4,4,128>>(q,raw.data(),rows,K,tokens,x.data(),want);tile_case<T,Cfg<1,1,4,128>>(q,raw.data(),rows,K,tokens,x.data(),want);
   tile_case<T,Cfg<2,16,4,256,1>>(q,raw.data(),rows,K,tokens,x.data(),want);}
 }
}
int main(int argc,char** argv){
 if(argc<5){std::fprintf(stderr,"usage: %s q6-file q6-offset q8-file q8-offset\n",argv[0]);return 2;}
 sycl::queue q{sycl::device{sycl::cpu_selector_v},sycl::property::queue::in_order{}};
 std::printf("device: %s\n",q.get_device().get_info<sycl::info::device::name>().c_str());
 // Head rows 0..36 and 248283..248319 (the last 37 rows), attention rows 0..36 and 2523..2559.
 suite<Type::Q6_K,2560>(q,argv[1],std::stoull(argv[2]),0);suite<Type::Q6_K,2560>(q,argv[1],std::stoull(argv[2]),248320-37);
 suite<Type::Q8_0,6144>(q,argv[3],std::stoull(argv[4]),0);suite<Type::Q8_0,6144>(q,argv[3],std::stoull(argv[4]),2560-37);
 std::printf("%s (%d failing cases)\n",failures?"FAILED":"ALL PASSED",failures);return failures?1:0;
}
