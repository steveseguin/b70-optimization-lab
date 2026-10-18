#pragma once
// Independent draft-only schedules. Target code never calls these operations.
#include "mtp_kernels.hpp"
#include "specialised.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "sycl_operation.hpp"
#endif
namespace p59 {
#ifdef OWN_RT_HOST_ONLY
using Base=integrated::HostOperation;
#else
using Base=ownrt::SyclOperation;
#endif
using ownrt::Allocation;
enum Tail {none,low,product,merge_add,attention};
struct Linear : mtp36::Linear {Allocation out{},other{},inject{};Tail tail=none;};
struct Bound {const uint8_t*w,*peer;const uint16_t*x;uint16_t*y,*py,*out;const uint16_t*other,*inject;const iq3::Route*route;uint32_t*status,*ps;unsigned rows,batch,experts;Tail tail;};
inline Bound bind(const Linear&a,std::span<void*const>p){return {static_cast<const uint8_t*>(p[0]),static_cast<const uint8_t*>(p[1]),static_cast<const uint16_t*>(p[2]),static_cast<uint16_t*>(p[3]),static_cast<uint16_t*>(p[4]),static_cast<uint16_t*>(p[8]),static_cast<const uint16_t*>(p[9]),static_cast<const uint16_t*>(p[10]),a.routes?static_cast<const iq3::Route*>(p[5]):nullptr,static_cast<uint32_t*>(p[6]),static_cast<uint32_t*>(p[7]),a.rows,a.batch,a.experts,a.tail};}
inline float widen(uint16_t b){return iq3::bits_float(uint32_t(b)<<16);}
inline void tail(Bound b,unsigned i,uint16_t value,uint16_t peer){
 b.y[i]=value;
 if(b.tail==low)b.out[i]=iq3::bf16_bits(ng::silu(widen(value)/4.f));
 if(b.tail==product)b.out[i]=iq3::bf16_bits(ng::silu(widen(peer))*widen(value));
 if(b.tail==merge_add)b.out[i]=iq3::bf16_bits(widen(value)+widen(b.other[i%b.rows]));
 if(b.tail==attention)for(unsigned stream=0;stream<4;++stream){unsigned j=stream*b.rows+i;b.out[j]=iq3::bf16_bits(widen(b.out[j])+widen(value)*(2.f*ng::sigmoid(widen(b.inject[stream])/4.f)));}
}
// Eight-wide explicit loads, as in p51; packed draft INT8 is not target IQ2/IQ4.
template<unsigned K,bool I>inline float lane(const uint8_t*w,const uint16_t*x,unsigned l,unsigned begin=0,unsigned end=K){
 float sum=0;
 for(unsigned k=begin+l*8;k<end;k+=256){
#if defined(__SYCL_DEVICE_ONLY__)
  sycl::vec<uint16_t,8> xv;if constexpr(K>=8)xv.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(x+k));
  sycl::vec<uint16_t,8> wv;
  if constexpr(!I&&K>=8)wv.load(0,sycl::address_space_cast<sycl::access::address_space::global_space,sycl::access::decorated::no>(reinterpret_cast<const uint16_t*>(w)+k));
#endif
  float scale=1;uint32_t codes[2]{};
  if constexpr(I){std::memcpy(&scale,w+K+4*(k/16),4);std::memcpy(codes,w+k,8);}
  for(unsigned j=0;j<8&&k+j<end;++j){float v;uint16_t xb;
#if defined(__SYCL_DEVICE_ONLY__)
   if constexpr(K>=8){xb=xv[j];if constexpr(!I)v=widen(wv[j]);}else{xb=x[k+j];if constexpr(!I)v=widen(reinterpret_cast<const uint16_t*>(w)[k+j]);}
#else
   xb=x[k+j];if constexpr(!I){uint16_t wb;std::memcpy(&wb,w+2*(k+j),2);v=widen(wb);}
#endif
   if constexpr(I)v=scale*float(iq3::signed8(uint8_t(codes[j/4]>>(8*(j%4)))));
   float p=v*widen(xb);sum=sum+p;
  }
 }
 return sum;
}
template<unsigned K,bool I,bool Pair,unsigned V,unsigned Split>struct Dense final:Base {
 Linear a;static constexpr size_t rb=I?K+4*((K+15)/16):K*2;
 static constexpr unsigned lanes=32/V;
 static float chain(const uint8_t*w,const uint16_t*x,unsigned physical,unsigned part){
  float sums[V]{};unsigned begin=(K/256*part/Split)*256,end=part+1==Split?K:(K/256*(part+1)/Split)*256;
  for(unsigned c=0;c<V;++c)sums[c]=lane<K,I>(w,x,physical*V+c,begin,end);
  for(unsigned width=1;width<V;width*=2)for(unsigned c=0;c<V;c+=2*width)sums[c]=sums[c]+sums[c+width];return sums[0];
 }
 static void output(Bound b,unsigned i,bool valid,float s,float peer){unsigned row=i%b.rows,slot=i/b.rows;
  uint16_t y=iq3::bf16_bits(valid?s:iq3::bits_float(0x7fc00000)),py=iq3::bf16_bits(valid?peer:iq3::bits_float(0x7fc00000));
  if constexpr(Pair)b.py[i]=py;
  uint16_t other=Pair?y:(b.tail==product?b.other[i]:0);
  // Paired expert activation consumes gate=y and up=py.
  if constexpr(Pair){b.y[i]=y;if(b.tail==product)b.out[i]=iq3::bf16_bits(ng::silu(widen(y))*widen(py));}
  else tail(b,i,y,other);
  if(!row&&b.route){b.status[slot]=!valid;if constexpr(Pair)b.ps[slot]=!valid;}
 }
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>p)const override {auto b=bind(a,p);
  for(unsigned i=0;i<b.rows*b.batch;++i){unsigned row=i%b.rows,slot=i/b.rows;auto r=b.route?b.route[slot]:iq3::Route{0,0,b.rows};bool valid=iq3::valid_route(r,b.experts,b.rows,b.rows)&&row<r.row_count;float sums[Split]{},peers[Split]{};
   if(valid)for(unsigned part=0;part<Split;++part){float s[lanes]{},pr[lanes]{};auto off=(size_t(r.expert_id)*b.rows+r.row_begin+row)*rb;auto x=b.x+(Pair?0:size_t(slot)*K);for(unsigned l=0;l<lanes;++l){s[l]=chain(b.w+off,x,l,part);if constexpr(Pair)pr[l]=chain(b.peer+off,x,l,part);}for(unsigned w=1;w<lanes;w*=2)for(unsigned l=0;l<lanes;l+=2*w){s[l]+=s[l+w];pr[l]+=pr[l+w];}sums[part]=s[0];peers[part]=pr[0];}
   for(unsigned w=1;w<Split;w*=2)for(unsigned l=0;l<Split;l+=2*w){sums[l]+=sums[l+w];peers[l]+=peers[l+w];}output(b,i,valid,sums[0],peers[0]);
  }
 }
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override {auto b=bind(a,p);size_t n=size_t(b.rows)*b.batch;
  constexpr unsigned wg=Split>1?Split*32:256;
  const size_t global=Split>1?n*wg:((n*lanes+wg-1)/wg)*wg;
  return q.submit([&](sycl::handler&h){h.depends_on(deps);sycl::local_accessor<float,1> partial(2*Split,h);
   h.parallel_for(sycl::nd_range<1>(global,wg),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
    auto sg=it.get_sub_group();unsigned physical=it.get_local_linear_id()%lanes,part=Split>1?it.get_local_linear_id()/32:0;size_t i=Split>1?it.get_group_linear_id():it.get_global_linear_id()/lanes;
    if(i>=n)return;unsigned row=i%b.rows,slot=i/b.rows;auto r=b.route?b.route[slot]:iq3::Route{0,0,b.rows};bool valid=iq3::valid_route(r,b.experts,b.rows,b.rows)&&row<r.row_count;float sum=0,peer=0;
    if(valid){auto off=(size_t(r.expert_id)*b.rows+r.row_begin+row)*rb;auto x=b.x+(Pair?0:size_t(slot)*K);sum=chain(b.w+off,x,physical,part);if constexpr(Pair)peer=chain(b.peer+off,x,physical,part);}
    unsigned base=sg.get_local_linear_id()-physical;
    for(unsigned w=1;w<lanes;w*=2){float r=sycl::select_from_group(sg,sum,base+(physical+w)%lanes),pr=sycl::select_from_group(sg,peer,base+(physical+w)%lanes);if(physical%(2*w)==0){sum+=r;peer+=pr;}}
    if constexpr(Split>1){if(!physical){partial[part]=sum;partial[Split+part]=peer;}it.barrier(sycl::access::fence_space::local_space);if(it.get_local_linear_id()==0){for(unsigned w=1;w<Split;w*=2)for(unsigned j=0;j<Split;j+=2*w){partial[j]+=partial[j+w];partial[Split+j]+=partial[Split+j+w];}output(b,i,valid,partial[0],partial[Split]);}}
    else if(!physical)output(b,i,valid,sum,peer);
   });});
 }
#endif
};
inline void extent(ownrt::Device&d,Allocation a,size_t n){const auto&r=d.arena.row(a);if(!r.live||r.memory!=ownrt::Memory::device||r.bytes<n)throw std::invalid_argument("p59 draft extent/lifetime");}
template<unsigned K,bool I,bool Pair,unsigned V=1,unsigned Split=1>inline integrated::Launch issue(ownrt::Device&d,const Linear&a){Dense<K,I,Pair,V,Split>op;op.a=a;std::array<Allocation,11>ids{a.w,Pair?a.peer:a.w,a.x,a.y,Pair?a.py:a.y,a.routes?a.routes:a.x,a.status?a.status:a.y,a.ps?a.ps:a.y,a.out?a.out:a.y,a.other?a.other:a.x,a.inject?a.inject:a.x};auto e=d.compute(op,ids,{});return {e,e,1};}
template<unsigned K>inline integrated::Launch typed(ownrt::Device&d,const Linear&a){
 if(a.int8){if constexpr(K==2560)return a.paired?issue<K,true,true,8>(d,a):issue<K,true,false,8>(d,a);if constexpr(K==640)return issue<K,true,false,16>(d,a);throw std::invalid_argument("p59 INT8 shape");}
 if(a.paired)return issue<K,false,true>(d,a);
 if constexpr(K>=6144)return issue<K,false,false,1,4>(d,a);
 if constexpr(K==320||K==640)return issue<K,false,false,4>(d,a);
 return issue<K,false,false>(d,a);
}
inline integrated::Launch linear(ownrt::Device&d,const Linear&a){
 if(!a.rows||!a.batch||a.batch>10||!a.experts||a.experts>512||(!a.routes&&a.experts!=1)||(a.paired&&!a.routes))throw std::invalid_argument("p59 draft shape");
 size_t rb=a.int8?a.columns+4*((a.columns+15)/16):2*a.columns,n=size_t(a.rows)*a.batch;
 extent(d,a.w,size_t(a.experts)*a.rows*rb);extent(d,a.x,size_t(a.paired?1:a.batch)*a.columns*2);extent(d,a.y,n*2);
 if(a.routes){extent(d,a.routes,a.batch*sizeof(iq3::Route));extent(d,a.status,a.batch*4);}if(a.paired){extent(d,a.peer,size_t(a.experts)*a.rows*rb);extent(d,a.py,n*2);extent(d,a.ps,a.batch*4);}
 if(a.tail!=none)extent(d,a.out,n*2*(a.tail==attention?4:1));
 if(a.tail==product&&!a.paired)extent(d,a.other,n*2);if(a.tail==merge_add)extent(d,a.other,a.rows*2);if(a.tail==attention)extent(d,a.inject,8);
 switch(a.columns){
#define K(n) case n:return typed<n>(d,a)
 K(4);K(8);K(16);K(64);K(320);K(640);K(2560);K(6144);K(10240);
#undef K
 default:throw std::invalid_argument("p59 draft K");}
}
// One fixed 256-lane tree per row; deterministic proposal arithmetic.
struct Norm final:Base {unsigned rows,width;
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>p)const override {auto x=static_cast<const uint16_t*>(p[0]);auto gain=static_cast<const float*>(p[1]);auto y=static_cast<uint16_t*>(p[2]);for(unsigned row=0;row<rows;++row){float s[256]{};for(unsigned l=0;l<256;++l)for(unsigned k=l;k<width;k+=256){float v=widen(x[row*width+k]);s[l]+=v*v;}for(unsigned w=1;w<256;w*=2)for(unsigned l=0;l<256;l+=2*w)s[l]+=s[l+w];float inv=detmath::rsqrt(s[0]/float(width)+1e-6f);for(unsigned k=0;k<width;++k)y[row*width+k]=iq3::bf16_bits((widen(x[row*width+k])*inv)*gain[row*width+k]);}}
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override {auto x=static_cast<const uint16_t*>(p[0]);auto gain=static_cast<const float*>(p[1]);auto y=static_cast<uint16_t*>(p[2]);auto nr=rows,n=width;return q.submit([&](sycl::handler&h){h.depends_on(deps);sycl::local_accessor<float,1>s(256,h);h.parallel_for(sycl::nd_range<1>(nr*256,256),[=](sycl::nd_item<1>it){unsigned l=it.get_local_linear_id(),row=it.get_group_linear_id();float sum=0;for(unsigned k=l;k<n;k+=256){float v=widen(x[row*n+k]);sum+=v*v;}s[l]=sum;it.barrier(sycl::access::fence_space::local_space);for(unsigned w=1;w<256;w*=2){if(l%(2*w)==0)s[l]+=s[l+w];it.barrier(sycl::access::fence_space::local_space);}float inv=detmath::rsqrt(s[0]/float(n)+1e-6f);for(unsigned k=l;k<n;k+=256)y[row*n+k]=iq3::bf16_bits((widen(x[row*n+k])*inv)*gain[row*n+k]);});});}
#endif
};
inline integrated::Launch norm(ownrt::Device&d,Allocation x,Allocation gain,Allocation y,unsigned rows,unsigned width){if(!rows||!width||width>10240)throw std::invalid_argument("p59 norm shape");extent(d,x,rows*width*2);extent(d,gain,rows*width*4);extent(d,y,rows*width*2);Norm op;op.rows=rows;op.width=width;std::array ids{x,gain,y};auto e=d.compute(op,ids,{});return {e,e,1};}
}
