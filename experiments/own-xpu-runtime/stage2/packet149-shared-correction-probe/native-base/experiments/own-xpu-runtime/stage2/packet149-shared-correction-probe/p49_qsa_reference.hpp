#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet149-shared-correction-probe/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/p49_qsa_reference.hpp"
#pragma once
// Independently written scalar arithmetic specification. No device scheduling
// helpers are called here. The inherited types/math are the lab's own code.
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet149-shared-correction-probe/build/checked/experiments/own-xpu-runtime/stage2/packet149-shared-correction-probe/kernels.hpp"
#include <numeric>
#include <cstring>

namespace p47ref {
inline constexpr int split_size=32;
inline constexpr char old_identity[]="iq3-p17-detmath-v2:qsa-adjacent-prob-before-pv";
inline constexpr char split_identity[]="iq3-p47-qsa-split32-v1";

inline float adjacent(std::vector<float> x) {
 if(x.empty())throw std::invalid_argument("empty reduction");
 for(size_t step=1;step<x.size();step*=2)
  for(size_t j=0;j<x.size();j+=step*2)x[j]=x[j]+(j+step<x.size()?x[j+step]:0.f);
 return x[0];
}
inline int count(ng::Shape s,ng::Args a,int row) {
 int n=0;while(n<s.budget+3&&a.i(4)[row*(s.budget+3)+n]!=-1){
  int id=a.i(4)[row*(s.budget+3)+n];
  if(id<0||id>=s.capacity||id>a.i(17)[0]+row||n>=ng::launch_slots(s))throw std::invalid_argument("invalid selected id");
  ++n;
 }return n;
}
inline float score(ng::Shape s,ng::Args a,int row,int head,int j) {
 int id=a.i(4)[row*(s.budget+3)+j];std::vector<float> products(256);
 for(int d=0;d<256;++d)products[d]=a.b(0,(row*24+head)*256+d)*a.b(2,(id*2+head/12)*256+d);
 return adjacent(std::move(products))/detmath::sqrt(256.f);
}
inline void store(ng::Args a,int at,float value,float* pre_gate) {
 if(pre_gate)pre_gate[at]=value;
 a.put(5,at,ng::Args::bf(value)*ng::sigmoid(a.b(1,at)));
}
inline void validate(ng::Shape s,ng::Args a) {
 ng::validate(s);
 if(s.tokens>2||a.i(17)[0]<0||a.i(17)[0]>s.capacity-s.tokens)throw std::invalid_argument("decode geometry");
}
// Historical identity: normalize individual probabilities BEFORE multiplying V.
inline void cpu_old(ng::Shape s,ng::Args a,float* pre_gate=nullptr) {
 validate(s,a);if(!a.i(18)[0]||a.i(15)[0])return;const int S=s.budget+3;
 for(int r=0;r<s.tokens;++r){int n=count(s,a,r);if(!n)continue;
  for(int h=0;h<24;++h){std::vector<float> p(n);float maximum=-INFINITY;
   for(int j=0;j<n;++j){p[j]=score(s,a,r,h,j);a.f(6)[(r*24+h)*S+j]=p[j];maximum=std::max(maximum,p[j]);}
   for(int j=n;j<ng::launch_slots(s);++j)a.f(6)[(r*24+h)*S+j]=-INFINITY;
   for(float& x:p)x=detmath::exp(x-maximum);float den=adjacent(p);
   for(int j=0;j<n;++j){p[j]=p[j]/den;a.f(7)[(r*24+h)*S+j]=p[j];}
   for(int d=0;d<256;++d){std::vector<float> terms(n);
    for(int j=0;j<n;++j)terms[j]=p[j]*a.b(3,(a.i(4)[r*S+j]*2+h/12)*256+d);
    store(a,(r*24+h)*256+d,adjacent(std::move(terms)),pre_gate);
   }
  }
 }
}
// New identity. Fixed split boundaries depend only on selected-token index.
// Every lower tree is exactly 32 leaves, including explicit +0 padding.
inline void cpu_split(ng::Shape s,ng::Args a,float* pre_gate=nullptr) {
 validate(s,a);if(!a.i(18)[0]||a.i(15)[0])return;const int S=s.budget+3;
 for(int r=0;r<s.tokens;++r){int n=count(s,a,r);if(!n)continue;int splits=(n+31)/32;
  for(int h=0;h<24;++h){std::vector<float> maxima(splits),sums(splits),values(splits*256);
   for(int b=0;b<splits;++b){int end=std::min(n,(b+1)*32);std::vector<float> p(32,0.f);float maximum=-INFINITY;
    for(int j=b*32;j<end;++j){p[j-b*32]=score(s,a,r,h,j);maximum=std::max(maximum,p[j-b*32]);}
    maxima[b]=maximum;
    for(int j=b*32;j<end;++j)p[j-b*32]=detmath::exp(p[j-b*32]-maximum);
    sums[b]=adjacent(p);
    for(int d=0;d<256;++d){std::vector<float> terms(32,0.f);
     for(int j=b*32;j<end;++j)terms[j-b*32]=p[j-b*32]*a.b(3,(a.i(4)[r*S+j]*2+h/12)*256+d);
     values[b*256+d]=adjacent(std::move(terms));
    }
   }
   float maximum=-INFINITY;for(float m:maxima)maximum=std::max(maximum,m);
   std::vector<float> factors(splits),den_terms(splits);
   for(int b=0;b<splits;++b){factors[b]=detmath::exp(maxima[b]-maximum);den_terms[b]=sums[b]*factors[b];}
   float den=adjacent(std::move(den_terms));
   for(int d=0;d<256;++d){std::vector<float> terms(splits);
    for(int b=0;b<splits;++b)terms[b]=values[b*256+d]*factors[b];
    store(a,(r*24+h)*256+d,adjacent(std::move(terms))/den,pre_gate);
   }
  }
 }
}
// Exact blocked implementation of the historical tree. A short root stops at
// its original depth; tail subtrees retain all original +0 operations.
inline float blocked(const std::vector<float>& x) {
 if(x.empty())throw std::invalid_argument("empty reduction");
 std::vector<float> partial((x.size()+31)/32);
 for(size_t b=0;b<partial.size();++b){float lane[32]{};int len=std::min(size_t(32),x.size()-32*b);
  for(int l=0;l<len;++l)lane[l]=x[b*32+l];
  for(int step=1;step<32&&size_t(step)<x.size();step*=2)
   for(int l=0;l<len;l+=2*step)lane[l]=lane[l]+(l+step<len?lane[l+step]:0.f);
  partial[b]=lane[0];
 }return partial.size()==1?partial[0]:adjacent(std::move(partial));
}

struct Fixture {
 ng::Shape shape{};std::array<std::vector<uint32_t>,19> data;
 // Context is the occupied count of the LAST verification row. At M=2 the
 // first row is context-1. No future KV row is selected by that first row.
 Fixture(int context,int rows,uint32_t seed,int pattern=0):shape{ng::attention_score,rows,2560,4,0,0,context,2048}{
  if(context<rows||context>32768)throw std::invalid_argument("fixture context");
  auto n=ng::required_bytes(shape);n[16]=4; // attention never consumes RoPE.
  for(int slot=0;slot<19;++slot)data[slot].resize((n[slot]+3)/4);
  auto a=args();uint32_t state=seed?seed:1;
  auto random=[&](){state^=state<<13;state^=state>>17;state^=state<<5;return state;};
  for(int slot:{0,1,2,3})for(size_t j=0;j<n[slot]/2;++j){
   float x=float(int(random()%2047)-1023)/1024.f;
   if(pattern==1)x=slot==3?((j%2)?-0.f:0.f):0.f;
   if(pattern==2)x=(slot==0||slot==2)?float(int(j%17)-8)*4.f:x;
   a.put(slot,j,x);
  }
  std::fill_n(a.i(4),rows*2051,-1);
  for(int r=0;r<rows;++r){int occupied=context-rows+r+1,blocks=occupied/4;std::vector<int> ids(blocks);std::iota(ids.begin(),ids.end(),0);
   for(int i=blocks-1;i>0;--i)std::swap(ids[i],ids[random()%uint32_t(i+1)]);
   int at=0;for(int j=0;j<std::min(blocks,512);++j)for(int d=0;d<4;++d)a.i(4)[r*2051+at++]=ids[j]*4+d;
   for(int j=blocks*4;j<occupied;++j)a.i(4)[r*2051+at++]=j;
  }
  a.i(15)[0]=0;a.i(17)[0]=context-rows;a.i(18)[0]=1;
 }
 ng::Args args(){ng::Args a;for(int slot=0;slot<19;++slot)a.p[slot]=data[slot].data();return a;}
 std::array<size_t,19> extents()const {std::array<size_t,19> n{};for(int slot=0;slot<19;++slot)n[slot]=data[slot].size()*4;return n;}
};
} // namespace p47ref
