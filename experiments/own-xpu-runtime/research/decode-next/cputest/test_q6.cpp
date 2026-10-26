// CPU-device bitwise test of the dense8 Q6_K packed-lane decode rows (q6_packed.hpp, the engine's own body) against a
// host replica of kopt Multiply's arithmetic (decode8<Q6_K>, product then add per 8-column chunk, adjacent-pair tree), on
// real blk.23.attn_k / attn_v (512 x 2560 Q6_K) and a synthetic matrix; read bounds checked by guard copies.
#include <sycl/sycl.hpp>
#include "stage2/packet6-kopt/q6_packed.hpp"
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
    for(uint32_t k=lane*8u;k+8u<=K;k+=256u){float v[8];iq3::kopt::decode8<Type::Q6_K>(row,k,v);for(unsigned j=0;j<8;++j){float p=v[j]*x[k+j];acc=acc+p;}}
    s[lane]=acc;}
  for(unsigned w=1;w<32;w*=2)for(unsigned l=0;l<32;l+=2*w)s[l]=s[l]+s[l+w];
  return s[0];
}
template<unsigned SG> struct K6;
template<unsigned SG,unsigned WGSG>
void device_rows(sycl::queue& q,const uint8_t* w,const float* x,float* y,uint32_t rows,uint32_t k,uint32_t rb){
  constexpr unsigned SETS=SG/8;const uint32_t blocks=(rows+SETS-1)/SETS,groups=(blocks+WGSG-1)/WGSG;
  q.parallel_for<K6<SG>>(sycl::nd_range<1>(size_t(groups)*SG*WGSG,SG*WGSG),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(SG)]]{
    auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id(),set=lane/8,t=lane%8;
    const uint32_t logical=uint32_t(it.get_group_linear_id())*WGSG+uint32_t(sg.get_group_linear_id());if(logical>=blocks)return;
    const uint32_t row=logical*SETS+set;const bool live=row<rows;const uint8_t* rp=live?w+size_t(row)*rb:w;
    float acc[4]={0,0,0,0};
    for(uint32_t bi=0;bi*256u<k;++bi){
      float xv[32];
      {const sycl::vec<float,4>* xp=reinterpret_cast<const sycl::vec<float,4>*>(x+bi*256u+32u*t);
       #pragma unroll
       for(unsigned c=0;c<8;++c){const auto v=xp[c];xv[4*c]=v[0];xv[4*c+1]=v[1];xv[4*c+2]=v[2];xv[4*c+3]=v[3];}}
      if(live)iq3::kopt::q6p::block(rp+bi*210u,(bi&1u)!=0,t,xv,acc);
    }
    const float a01=acc[0]+acc[1],a23=acc[2]+acc[3];float sum=a01+a23;
    #pragma unroll
    for(unsigned width=1;width<8;width*=2){float rhs=sycl::select_from_group(sg,sum,(lane+width)%SG);if(t%(2*width)==0)sum=sum+rhs;}
    if(t==0&&live)y[row]=sum;
  });
  q.wait();
}
int main(){
  sycl::queue q;std::printf("device: %s\n",q.get_device().get_info<sycl::info::device::name>().c_str());
  const uint32_t rows=512,k=2560,rb=k/256*210;const size_t bytes=size_t(rows)*rb;
  const char* f="/mnt/usb-models/llm-models/SC117-Qwen3.8-Flash-Next-GSQ-RCO-abliterated-IQ3_S-eec4e10a/Qwen3.8-Flash-Next-GSQ-RCO-abliterated-IQ3_S-00001-of-00002.gguf";
  const off_t offs[2]={off_t(25536705792ull),off_t(25576121600ull)};const char* names[3]={"blk.23.attn_k","blk.23.attn_v","synthetic"};
  std::mt19937 g(2);int fails=0;
  for(int which=0;which<3;++which){
    std::vector<uint8_t> W(bytes);
    if(which<2){int fd=::open(f,O_RDONLY);if(fd<0||::pread(fd,W.data(),bytes,offs[which])!=ssize_t(bytes)){std::perror("read");return 1;}::close(fd);}
    else {for(auto& b:W)b=uint8_t(g());for(uint32_t r=0;r<rows;++r)for(uint32_t b=0;b<k/256;++b){uint16_t s=uint16_t(g()&0x3bff);W[size_t(r)*rb+b*210+208]=s&255;W[size_t(r)*rb+b*210+209]=s>>8;}}
    std::vector<float> hx(k);for(auto& v:hx)v=std::normal_distribution<float>(0,1)(g);
    // the matrix sits at the very end of its allocation (+ 0 slack) so a read past the last row's end would leave it
    auto* w=sycl::malloc_shared<uint8_t>(bytes,q);auto* x=sycl::malloc_shared<float>(k,q);auto* y=sycl::malloc_shared<float>(rows,q);
    std::memcpy(w,W.data(),bytes);std::memcpy(x,hx.data(),k*4);
    for(int sgv=0;sgv<2;++sgv){
      std::memset(y,0xff,rows*4);
      if(sgv==0)device_rows<16,4>(q,w,x,y,rows,k,rb);else device_rows<32,4>(q,w,x,y,rows,k,rb);
      int bad=0;for(uint32_t r=0;r<rows;++r){float h=host_row(W.data()+size_t(r)*rb,hx.data(),k);if(std::memcmp(&h,&y[r],4)){if(bad<3)std::printf("  row %u host %.9g dev %.9g\n",r,h,y[r]);++bad;}}
      std::printf("%s SG%d: rows %u mismatches %d\n",names[which],sgv?32:16,rows,bad);fails+=bad;
    }
    sycl::free(w,q);sycl::free(x,q);sycl::free(y,q);
  }
  std::printf(fails?"FAIL\n":"PASS\n");return fails?1:0;
}
