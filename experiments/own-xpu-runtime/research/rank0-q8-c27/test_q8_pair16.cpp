// OpenCL CPU-device bitwise test for paired 16-byte Q8 weight loads; GPU access is blocked by nodri.so.
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
  for(unsigned tile=lane*8;tile<6144;tile+=256){const float scale=iq3::bits_float(iq3::u32(w+6144+4*(tile/32)));
   for(unsigned j=0;j<8;++j){float value=scale*float(iq3::signed8(w[tile+j]));float product=value*x[tile+j];sum=sum+product;}}
  s[lane]=sum;
 }
 for(unsigned width=1;width<32;width*=2)for(unsigned l=0;l<32;l+=2*width)s[l]=s[l]+s[l+width];
 return s[0];
}
template<unsigned R,unsigned U> static size_t run(sycl::queue& q,const uint8_t* raw,const float* x,uint32_t tokens,const std::vector<float>& want){
 constexpr uint32_t rows=37,K=6144,rb=6528;const uint32_t groups=(rows+R-1)/R;const size_t global=(size_t(groups)*tokens*32+127)/128*128;
 uint8_t* w=sycl::malloc_device<uint8_t>(rows*rb,q);float* xd=sycl::malloc_device<float>(size_t(tokens)*K,q);float* y=sycl::malloc_device<float>(size_t(tokens)*rows+64,q);
 q.memcpy(w,raw,rows*rb).wait();q.memcpy(xd,x,size_t(tokens)*K*4).wait();std::vector<float> sentinel(size_t(tokens)*rows+64,-777.f);q.memcpy(y,sentinel.data(),sentinel.size()*4).wait();
 q.parallel_for(sycl::nd_range<1>(global,128),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{p33::raw::dense_rows<iq3::Type::Q8_0,K,R,U>(w,xd,y,rows,rb,groups,tokens,it);}).wait();
 std::vector<float> got(size_t(tokens)*rows+64);q.memcpy(got.data(),y,got.size()*4).wait();size_t bad=0;
 for(size_t i=0;i<want.size();++i){bool different=std::bit_cast<uint32_t>(got[i])!=std::bit_cast<uint32_t>(want[i]);bad+=different;if(different&&bad<4)std::printf(" first %zu got %a/%08x want %a/%08x\n",i,got[i],std::bit_cast<uint32_t>(got[i]),want[i],std::bit_cast<uint32_t>(want[i]));}
 for(size_t i=want.size();i<got.size();++i)bad+=got[i]!=-777.f;
 std::printf("R%uU%u tokens %u: %zu outputs plus 64 sentinels, mismatches %zu\n",R,U,tokens,want.size(),bad);
 sycl::free(w,q);sycl::free(xd,q);sycl::free(y,q);return bad;
}
static size_t suite(sycl::queue& q,const char* file,size_t offset,size_t first){
 constexpr uint32_t rows=37,K=6144,rb=6528,erb=7296,maxtok=3;const auto gguf=read_rows(file,offset,rb,first,rows);
 const auto expanded=iq3::expanded::expand(iq3::Type::Q8_0,gguf.data(),gguf.size(),K);const auto raw=denseraw::repack(iq3::Type::Q8_0,gguf.data(),gguf.size(),K);
 const uint64_t decode_bad=denseraw::check_rows(iq3::Type::Q8_0,raw.data(),expanded.data(),rows,K,erb);
 std::printf("rows %zu..%zu: %u decoded values, single/pair decode mismatches %llu\n",first,first+rows-1,rows*K,(unsigned long long)decode_bad);
 std::mt19937 g(1234+first);std::uniform_real_distribution<float> u(-1.f,1.f);std::vector<float>x(size_t(maxtok)*K);for(auto&v:x)v=u(g);
 size_t bad=decode_bad;
 for(uint32_t tokens:{1u,3u}){std::vector<float>want(size_t(tokens)*rows);
  for(uint32_t t=0;t<tokens;++t)for(uint32_t r=0;r<rows;++r)want[size_t(t)*rows+r]=ref_row(expanded.data()+r*erb,x.data()+size_t(t)*K);
  bad+=run<1,2>(q,raw.data(),x.data(),tokens,want);bad+=run<1,1>(q,raw.data(),x.data(),tokens,want);
 }
 return bad;
}
int main(int argc,char**argv){
 if(argc!=3){std::fprintf(stderr,"usage: %s attention-gguf data-offset\n",argv[0]);return 2;}
 sycl::queue q{sycl::device{sycl::cpu_selector_v},sycl::property::queue::in_order{}};
 std::printf("device: %s\n",q.get_device().get_info<sycl::info::device::name>().c_str());
 size_t bad=suite(q,argv[1],std::stoull(argv[2]),0)+suite(q,argv[1],std::stoull(argv[2]),2560-37);
 std::printf("%s\n",bad?"FAILED":"ALL PASSED");return bad?1:0;
}
