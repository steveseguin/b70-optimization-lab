#pragma once
#include "../packet27-round2/kernels.hpp"
#include <cstring>
#include <string>
namespace p30::attention {
// Decode only. s.extra is a schedule-known upper bound on admitted selection
// slots; zero is explicitly the empty diagnostic. No device count readback.
inline constexpr int variants=2;
inline const char* name(int v){return v==0?"p30.attention.sg32":"p30.attention.score_softmax";}
inline void validate(ng::Shape s,int variant){
 ng::validate(s);
 if(s.op!=ng::attention_score||s.tokens!=1||s.extra<0||s.extra>std::min(s.capacity,s.budget+3)||variant<0||variant>=variants)
  throw std::invalid_argument("p30 attention decode shape/variant/admitted bound");
}
inline void validate(ng::Shape s,ng::Args a,const std::array<size_t,19>& extents,int v){
 validate(s,v);auto n=ng::required_bytes(s);
 for(int slot:{0,1,2,3,4,5,6,7,15,17,18}){
  if(!a.p[slot]||extents[slot]<n[slot]||reinterpret_cast<uintptr_t>(a.p[slot])+n[slot]<reinterpret_cast<uintptr_t>(a.p[slot])||reinterpret_cast<uintptr_t>(a.p[slot])%((slot<=3||slot==5)?2:4))throw std::invalid_argument("attention binding extent/alignment");
 }
 for(int w:{5,6,7,15})for(int r:{0,1,2,3,4,5,6,7,15,17,18})if(w!=r){
  auto wb=reinterpret_cast<uintptr_t>(a.p[w]),rb=reinterpret_cast<uintptr_t>(a.p[r]);
  if(wb<rb+n[r]&&rb<wb+n[w])throw std::invalid_argument("attention overlapping output");
 }
}
inline float tree(float* x,int n){for(int step=1;step<n;step*=2)for(int i=0;i<n;i+=2*step)x[i]=x[i]+(i+step<n?x[i+step]:0.f);return x[0];}
inline int count(ng::Shape s,ng::Args a){int n=0,S=s.budget+3;while(n<S&&a.i(4)[n]!=-1){int id=a.i(4)[n];if(id<0||id>=s.capacity||id>a.i(17)[0]||n>=s.extra){a.i(15)[0]=1;return -1;}++n;}return n;}
// Independent register-layout mirror, not the incumbent ng::group.
inline float blocked_tree(const float* leaves,int n){
 if(n==1)return leaves[0];float partial[65]{};
 for(int c=0;c<(n+31)/32;++c){float lanes[32]{};int len=std::min(32,n-c*32);for(int l=0;l<len;++l)lanes[l]=leaves[c*32+l];
  // Every existing odd-tail node includes +0, but no levels above the
  // original global ceil(log2(n)) are evaluated.
  for(int stride=1;stride<32&&stride<n;stride*=2)for(int l=0;l<len;l+=2*stride)lanes[l]=lanes[l]+(l+stride<len?lanes[l+stride]:0.f);
  partial[c]=lanes[0];
 }
 int chunks=(n+31)/32;return chunks==1?partial[0]:tree(partial,chunks);
}
inline void cpu(ng::Shape s,ng::Args a,int variant){
 validate(s,variant);if(!a.i(18)[0]||a.i(15)[0])return;
 if(a.i(17)[0]<0||a.i(17)[0]>=s.capacity){a.i(15)[0]=1;return;}int n=count(s,a);if(n<=0)return;
 const int S=s.budget+3;std::vector<float> terms(std::max(n,256));
 for(int h=0;h<24;++h){
  for(int j=0;j<n;++j){int id=a.i(4)[j];for(int k=0;k<256;++k)terms[k]=a.b(2,(id*2+h/12)*256+k)*a.b(0,h*256+k);a.f(6)[h*S+j]=(variant==0?blocked_tree(terms.data(),256):tree(terms.data(),256))/detmath::sqrt(256.f);}
  float m=-INFINITY;for(int j=0;j<n;++j)m=std::max(m,a.f(6)[h*S+j]);
  for(int j=0;j<n;++j)terms[j]=detmath::exp(a.f(6)[h*S+j]-m);
  float den=blocked_tree(terms.data(),n);for(int j=0;j<n;++j)a.f(7)[h*S+j]=terms[j]/den;
  for(int k=0;k<256;++k){for(int j=0;j<n;++j)terms[j]=a.f(7)[h*S+j]*a.b(3,(a.i(4)[j]*2+h/12)*256+k);a.put(5,h*256+k,ng::Args::bf(blocked_tree(terms.data(),n))*ng::sigmoid(a.b(1,h*256+k)));}
 }
}
struct Fixture {
 ng::Shape shape{};std::array<std::vector<uint32_t>,19> data;
 Fixture(int position,int admitted,int budget=2048,int capacity=4096):shape{ng::attention_score,1,2560,4,admitted,0,capacity,budget}{
  auto n=ng::required_bytes(shape);for(int i=0;i<19;++i)data[i].resize((n[i]+3)/4);
  auto a=args();for(int slot:{0,1,2,3})for(size_t j=0;j<n[slot]/2;++j)a.put(slot,j,float(int((j*17+slot*11)%127)-63)/64.f);
  std::fill_n(a.i(4),budget+3,-1);for(int j=0;j<admitted;++j)a.i(4)[j]=admitted-1-j;
  // Deliberately selected-order rather than context order.
  a.i(15)[0]=0;a.i(17)[0]=position;a.i(18)[0]=1;
 }
 ng::Args args(){ng::Args a;for(int i=0;i<19;++i)a.p[i]=data[i].data();return a;}
 std::array<size_t,19> extents()const{std::array<size_t,19> n;for(int i=0;i<19;++i)n[i]=data[i].size()*4;return n;}
};
}
#ifndef HOST_ONLY
#include <sycl/sycl.hpp>
namespace p30::attention {
std::vector<sycl::event> submit(sycl::queue&,ng::Shape,ng::Args,float*,int,const std::vector<sycl::event>& = {});
}
#endif
