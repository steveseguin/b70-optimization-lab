// CPU-device (OpenCL CPU, GPU blocked by nodri.so) bitwise test of the dense8 Q8_0 packed-lane decode row kernel
// (kernels.cpp MultiplyQ8Packed, body restated with plain pointers and a read-bounds check) against a host replica of
// kopt Multiply's arithmetic (lane_dot: decode8<Q8_0>, product then add per 8-column chunk, adjacent-pair tree), on the
// real blk.23.ffn_down_shexp.weight (2560 x 640 Q8_0) and a synthetic one with random scales.
#include <sycl/sycl.hpp>
#include "stage2/packet6-kopt/reference.hpp"
#include <cstdio>
#include <cstring>
#include <fcntl.h>
#include <random>
#include <unistd.h>
#include <vector>
using iq3::Type;
static float host_row(const uint8_t* row,const float* x,uint32_t K){
  float s[32];
  for(unsigned lane=0;lane<32;++lane){float acc=0;
    for(uint32_t k=lane*8u;k+8u<=K;k+=256u){float v[8];iq3::kopt::decode8<Type::Q8_0>(row,k,v);for(unsigned j=0;j<8;++j){float p=v[j]*x[k+j];acc=acc+p;}}
    s[lane]=acc;}
  for(unsigned w=1;w<32;w*=2)for(unsigned l=0;l<32;l+=2*w)s[l]=s[l]+s[l+w];
  return s[0];
}
template<unsigned SG> struct K8;
template<unsigned SG,unsigned WGSG>
void device_rows(sycl::queue& q,const uint8_t* w,const float* x,float* y,uint32_t rows,uint32_t k,uint32_t rb,size_t wbytes,int* oob){
  constexpr unsigned SETS=SG/8,RPS=SETS;const uint32_t blocks=(rows+RPS-1)/RPS,total=blocks,groups=(total+WGSG-1)/WGSG;
  q.parallel_for<K8<SG>>(sycl::nd_range<1>(size_t(groups)*SG*WGSG,SG*WGSG),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(SG)]]{
    auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id(),set=lane/8,t=lane%8;
    const uint32_t logical=uint32_t(it.get_group_linear_id())*WGSG+uint32_t(sg.get_group_linear_id());if(logical>=total)return;
    const uint32_t first=(logical%blocks)*RPS+set;
    float acc[4]={0,0,0,0};const bool live=first<rows;const uint8_t* rp=live?w+size_t(first)*rb:w;
    const bool odd=t&1;
    for(uint32_t b=t;b*32u<k;b+=8u){
      float xv[32];
      {const sycl::vec<float,4>* xp=reinterpret_cast<const sycl::vec<float,4>*>(x+b*32u);
       #pragma unroll
       for(unsigned c=0;c<8;++c){const auto v=xp[c];xv[4*c]=v[0];xv[4*c+1]=v[1];xv[4*c+2]=v[2];xv[4*c+3]=v[3];}}
      if(!live)continue;
      const uint32_t* wp=reinterpret_cast<const uint32_t*>(rp+b*34u-(odd?2u:0u));
      const size_t lo=size_t(reinterpret_cast<const uint8_t*>(wp)-w),hi=lo+36;
      if(hi>wbytes||(lo%4)!=0||reinterpret_cast<const uint8_t*>(wp)<rp||hi>size_t(rp-w)+rb)sycl::atomic_ref<int,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(*oob).fetch_add(1);
      uint32_t wv[9];
      #pragma unroll
      for(unsigned e=0;e<9;++e)wv[e]=wp[e];
      const uint32_t sbits=odd?(wv[0]>>16):(wv[0]&0xffffu);
      uint32_t cw[8];
      #pragma unroll
      for(unsigned e=0;e<8;++e)cw[e]=odd?wv[e+1]:(wv[e]>>16)|(wv[e+1]<<16);
      const float scale=iq3::kopt::half_scale(sbits);
      #pragma unroll
      for(unsigned j=0;j<4;++j){
        #pragma unroll
        for(unsigned jj=0;jj<8;++jj){const uint32_t byte=(cw[2*j+jj/4]>>(8*(jj%4)))&255u;const float value=scale*float(int(int8_t(uint8_t(byte))));
          const float product=value*xv[8*j+jj];acc[j]=acc[j]+product;}}
    }
    const float a01=acc[0]+acc[1],a23=acc[2]+acc[3];float sum=a01+a23;
    #pragma unroll
    for(unsigned width=1;width<8;width*=2){float rhs=sycl::select_from_group(sg,sum,(lane+width)%SG);if(t%(2*width)==0)sum=sum+rhs;}
    if(t==0&&first<rows)y[first]=sum;
  });
  q.wait();
}
int main(){
  sycl::queue q;std::printf("device: %s\n",q.get_device().get_info<sycl::info::device::name>().c_str());
  const uint32_t rows=2560,k=640,rb=k/32*34;const size_t bytes=size_t(rows)*rb;
  std::vector<uint8_t> real(bytes);
  int fd=::open("/mnt/usb-models/llm-models/SC117-Qwen3.8-Flash-Next-GSQ-RCO-abliterated-IQ3_S-eec4e10a/Qwen3.8-Flash-Next-GSQ-RCO-abliterated-IQ3_S-00001-of-00002.gguf",O_RDONLY);
  if(fd<0||::pread(fd,real.data(),bytes,off_t(26049056000ull))!=ssize_t(bytes)){std::perror("read");return 1;}::close(fd);
  std::mt19937 g(1);std::vector<uint8_t> synth(bytes);for(auto& b:synth)b=uint8_t(g());
  for(uint32_t r=0;r<rows;++r)for(uint32_t b=0;b<k/32;++b){uint16_t s=uint16_t(g()&0x7bff);if(r%97==0)s=uint16_t(0x8000|(g()&0x03ff));synth[size_t(r)*rb+b*34]=s&255;synth[size_t(r)*rb+b*34+1]=s>>8;} // incl. negative subnormal scales
  int fails=0;
  for(int which=0;which<2;++which){
    const auto& W=which?synth:real;
    std::vector<float> hx(k);for(auto& v:hx)v=std::normal_distribution<float>(0,1)(g);hx[5]=-0.f;hx[300]=1e-30f;
    auto* w=sycl::malloc_shared<uint8_t>(bytes,q);auto* x=sycl::malloc_shared<float>(k,q);auto* y=sycl::malloc_shared<float>(rows,q);auto* oob=sycl::malloc_shared<int>(1,q);
    std::memcpy(w,W.data(),bytes);std::memcpy(x,hx.data(),k*4);
    for(int sgv=0;sgv<2;++sgv){
      std::memset(y,0xff,rows*4);*oob=0;
      if(sgv==0)device_rows<16,4>(q,w,x,y,rows,k,rb,bytes,oob);else device_rows<32,4>(q,w,x,y,rows,k,rb,bytes,oob);
      int bad=0;for(uint32_t r=0;r<rows;++r){float h=host_row(W.data()+size_t(r)*rb,hx.data(),k);if(std::memcmp(&h,&y[r],4)){if(bad<3)std::printf("  row %u host %.9g (%08x) dev %.9g (%08x)\n",r,h,*(uint32_t*)&h,y[r],*(uint32_t*)&y[r]);++bad;}}
      std::printf("%s SG%d: rows %u mismatches %d out-of-bounds %d\n",which?"synthetic":"blk.23.ffn_down_shexp",sgv?32:16,rows,bad,*oob);fails+=bad+*oob;
    }
    sycl::free(w,q);sycl::free(x,q);sycl::free(y,q);sycl::free(oob,q);
  }
  std::printf(fails?"FAIL\n":"PASS\n");return fails?1:0;
}
