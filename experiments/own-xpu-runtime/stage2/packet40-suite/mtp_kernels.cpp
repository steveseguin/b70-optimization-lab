#include "mtp_kernels.hpp"
#include "p28/dense.hpp"
#include "specialised.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "sycl_operation.hpp"
#endif
namespace mtp36 {
using ownrt::Allocation;using integrated::Launch;
template<class F> F checked(F f){static_assert(sizeof(F)<=1024,"draft capture exceeds 1024 bytes");return f;}
struct Bound {const uint8_t *w,*peer;const uint16_t *x;uint16_t *y,*py;const iq3::Route *route;uint32_t *status,*ps;unsigned rows,batch,experts;};
static_assert(sizeof(Bound)<=1024);
template<unsigned K,bool Int8> inline float lane(const uint8_t* w,const uint16_t* x,unsigned l){
 if constexpr(!Int8)return p28::dense_lane<iq3::Type::BF16,K>(w,x,0,K,l);
 else {float sum=0;for(unsigned tile=l*8;tile<K;tile+=256)for(unsigned k=tile;k<std::min(tile+8,K);++k){
  const auto* s=w+K+(k/16)*4;uint32_t u=uint32_t(s[0])|(uint32_t(s[1])<<8)|(uint32_t(s[2])<<16)|(uint32_t(s[3])<<24);
  float value=iq3::bits_float(u)*float(iq3::signed8(w[k]));float product=value*iq3::bits_float(uint32_t(x[k])<<16);sum=sum+product;}return sum;}
}
template<unsigned K,bool Int8,bool Pair> struct Dense final:
#ifdef OWN_RT_HOST_ONLY
 integrated::HostOperation
#else
 ownrt::SyclOperation
#endif
{
 Linear a;Bound bind(std::span<void*const> p)const{return {static_cast<const uint8_t*>(p[0]),static_cast<const uint8_t*>(p[1]),static_cast<const uint16_t*>(p[2]),static_cast<uint16_t*>(p[3]),static_cast<uint16_t*>(p[4]),a.routes?static_cast<const iq3::Route*>(p[5]):nullptr,static_cast<uint32_t*>(p[6]),static_cast<uint32_t*>(p[7]),a.rows,a.batch,a.experts};}
 static constexpr size_t rb=Int8?K+4*((K+15)/16):K*2;
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const> p)const override{auto b=bind(p);
  #pragma omp parallel for num_threads(2) schedule(static)
  for(unsigned i=0;i<b.rows*b.batch;++i){unsigned slot=i/b.rows,row=i%b.rows;auto r=b.route?b.route[slot]:iq3::Route{0,0,b.rows};bool valid=iq3::valid_route(r,b.experts,b.rows,b.rows)&&row<r.row_count;
   if(row==0&&b.route){b.status[slot]=!valid;if constexpr(Pair)b.ps[slot]=!valid;}
   float sums[2][32]{};if(valid)for(unsigned l=0;l<32;++l){size_t off=(size_t(r.expert_id)*b.rows+r.row_begin+row)*rb;auto x=b.x+(Pair?0:size_t(slot)*K);sums[0][l]=lane<K,Int8>(b.w+off,x,l);if constexpr(Pair)sums[1][l]=lane<K,Int8>(b.peer+off,x,l);}
   b.y[i]=iq3::bf16_bits(valid?iq3::tree32(sums[0]):iq3::bits_float(0x7fc00000));if constexpr(Pair)b.py[i]=iq3::bf16_bits(valid?iq3::tree32(sums[1]):iq3::bits_float(0x7fc00000));
  }
 }
#else
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override{auto b=bind(p);size_t n=size_t(b.rows)*b.batch;
  return q.submit([&](sycl::handler& h){h.depends_on(deps);h.parallel_for(sycl::nd_range<1>(((n+3)/4)*128,128),checked([=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{
   auto sg=it.get_sub_group();unsigned l=sg.get_local_linear_id();size_t i=it.get_global_linear_id()/32;if(i>=n)return;unsigned slot=i/b.rows,row=i%b.rows;
   auto r=b.route?b.route[slot]:iq3::Route{0,0,b.rows};bool valid=iq3::valid_route(r,b.experts,b.rows,b.rows)&&row<r.row_count;float sum=0,peer=0;
   if(valid){size_t off=(size_t(r.expert_id)*b.rows+r.row_begin+row)*rb;auto x=b.x+(Pair?0:size_t(slot)*K);sum=lane<K,Int8>(b.w+off,x,l);if constexpr(Pair)peer=lane<K,Int8>(b.peer+off,x,l);}
   for(unsigned width=1;width<32;width*=2){float rhs=sycl::select_from_group(sg,sum,(l+width)%32);float pr=sycl::select_from_group(sg,peer,(l+width)%32);if(l%(2*width)==0){sum=sum+rhs;peer=peer+pr;}}
   if(l==0){b.y[i]=iq3::bf16_bits(valid?sum:iq3::bits_float(0x7fc00000));if constexpr(Pair)b.py[i]=iq3::bf16_bits(valid?peer:iq3::bits_float(0x7fc00000));if(row==0&&b.route){b.status[slot]=!valid;if constexpr(Pair)b.ps[slot]=!valid;}}
  }));});
 }
#endif
};
static void extent(ownrt::Device& d,Allocation a,size_t n){auto r=d.arena.row(a);if(!r.live||r.bytes<n||r.memory!=ownrt::Memory::device)throw std::invalid_argument("draft allocation extent");}
template<unsigned K,bool I,bool Pair> Launch issue(ownrt::Device& d,const Linear& a){Dense<K,I,Pair> op;op.a=a;std::array<Allocation,8> ids{a.w,Pair?a.peer:a.w,a.x,a.y,Pair?a.py:a.y,a.routes?a.routes:a.x,a.status?a.status:a.y,a.ps?a.ps:a.y};auto e=d.compute(op,ids,{});return {e,e,1};}
template<unsigned K> Launch typed(ownrt::Device& d,const Linear& a){if(a.int8)return a.paired?issue<K,true,true>(d,a):issue<K,true,false>(d,a);return a.paired?issue<K,false,true>(d,a):issue<K,false,false>(d,a);}
Launch linear(ownrt::Device& d,const Linear& a){
 if(!a.rows||!a.batch||a.batch>10||!a.experts||a.experts>512||a.rows>248320||(!a.routes&&a.experts!=1)||(a.paired&&!a.routes))throw std::invalid_argument("draft linear geometry");
 size_t rb=a.int8?a.columns+4*((a.columns+15)/16):a.columns*2;
 extent(d,a.w,size_t(a.experts)*a.rows*rb);extent(d,a.x,size_t(a.paired?1:a.batch)*a.columns*2);extent(d,a.y,size_t(a.batch)*a.rows*2);
 if(a.routes){extent(d,a.routes,a.batch*sizeof(iq3::Route));extent(d,a.status,a.batch*4);}if(a.paired){extent(d,a.peer,size_t(a.experts)*a.rows*rb);extent(d,a.py,size_t(a.batch)*a.rows*2);extent(d,a.ps,a.batch*4);}
 switch(a.columns){
#define K(n) case n:return typed<n>(d,a)
 K(4);K(8);K(16);K(64);K(320);K(640);K(2560);K(6144);K(10240);
#undef K
 default:throw std::invalid_argument("draft uncompiled K");}
}
template<unsigned Width,int Stage> struct Norm final:
#ifdef OWN_RT_HOST_ONLY
 integrated::HostOperation
#else
 ownrt::SyclOperation
#endif
{
 static void body(std::span<void*const> p,unsigned i){auto x=static_cast<const uint16_t*>(p[0]);auto gain=static_cast<const float*>(p[1]);auto y=static_cast<uint16_t*>(p[2]);auto scratch=static_cast<float*>(p[3]);constexpr unsigned chunks=(Width+31)/32;
  if constexpr(Stage==0)scratch[i]=specialised::subtree(Width,i,[&](int k){float v=iq3::bits_float(uint32_t(x[k])<<16);return v*v;});
  else {float inv=detmath::rsqrt(specialised::upper(scratch,chunks)/float(Width)+1e-6f);for(unsigned k=i*4;k<std::min(Width,i*4+4);++k)y[k]=iq3::bf16_bits((iq3::bits_float(uint32_t(x[k])<<16)*inv)*gain[k]);}}
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const> p)const override{for(unsigned i=0;i<(Stage==0?(Width+31)/32:(Width+3)/4);++i)body(p,i);}
#else
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override{std::array<void*,4> args{};std::copy_n(p.begin(),4,args.begin());return q.submit([&](sycl::handler& h){h.depends_on(deps);h.parallel_for(sycl::range<1>(Stage==0?(Width+31)/32:(Width+3)/4),checked([=](sycl::id<1> i){body(args,i[0]);}));});}
#endif
};
template<unsigned W> Launch norm_typed(ownrt::Device& d,std::array<Allocation,4> args){Norm<W,0> a;Norm<W,1> b;auto first=d.compute(a,args,{});auto last=d.compute(b,args,{});return {first,last,2};}
Launch norm_hidden(ownrt::Device& d,Allocation x,Allocation gain,Allocation y,Allocation scratch,unsigned width){extent(d,x,width*2);extent(d,gain,width*4);extent(d,y,width*2);extent(d,scratch,((width+31)/32)*4);std::array args{x,gain,y,scratch};if(width==10240)return norm_typed<10240>(d,args);if(width==64)return norm_typed<64>(d,args);throw std::invalid_argument("draft hidden norm width");}
struct Merge final:
#ifdef OWN_RT_HOST_ONLY
 integrated::HostOperation
#else
 ownrt::SyclOperation
#endif
{unsigned width;
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const> p)const override{auto h=static_cast<const uint16_t*>(p[0]),e=static_cast<const uint16_t*>(p[1]);auto y=static_cast<uint16_t*>(p[2]);for(unsigned k=0;k<4*width;++k)y[k]=iq3::bf16_bits(iq3::bits_float(uint32_t(h[k])<<16)+iq3::bits_float(uint32_t(e[k%width])<<16));}
#else
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override{auto x=static_cast<const uint16_t*>(p[0]),e=static_cast<const uint16_t*>(p[1]);auto y=static_cast<uint16_t*>(p[2]);auto w=width;return q.submit([&](sycl::handler& h){h.depends_on(deps);h.parallel_for(sycl::range<1>(4*w),checked([=](sycl::id<1> i){y[i]=iq3::bf16_bits(iq3::bits_float(uint32_t(x[i])<<16)+iq3::bits_float(uint32_t(e[i%w])<<16));}));});}
#endif
};
Launch merge(ownrt::Device& d,Allocation h,Allocation e,Allocation y,unsigned width){if(width!=16&&width!=2560)throw std::invalid_argument("draft merge width");extent(d,h,4*width*2);extent(d,e,width*2);extent(d,y,4*width*2);Merge op;op.width=width;std::array args{h,e,y};auto event=d.compute(op,args,{});return {event,event,1};}
}

namespace mtp36 {
enum class Element { activation_low,activation_product,mix,moe };
template<Element Code> struct Elements final:
#ifdef OWN_RT_HOST_ONLY
 integrated::HostOperation
#else
 ownrt::SyclOperation
#endif
{
 integrated::Spec s;
 struct Args {std::array<void*,4> in{};uint16_t* out;const uint32_t* error;const uint32_t* active;unsigned width,count;};
 Args bind(std::span<void*const> p)const{Args a{};for(int j=0;j<std::min(4,s.ni);++j)a.in[j]=p[j];a.out=static_cast<uint16_t*>(p[s.ni]);a.error=static_cast<const uint32_t*>(p[s.ni+s.no+s.nw+1]);a.active=static_cast<const uint32_t*>(p[s.ni+s.no+s.nw+3]);a.width=(Code==Element::activation_low||Code==Element::activation_product)?unsigned(s.sizes[0]):unsigned(s.site.shape[1]);a.count=s.site.shape[0];return a;}
 static void body(Args a,unsigned k){if(!*a.active||*a.error)return;auto b=[&](int slot,size_t i){return iq3::bits_float(uint32_t(static_cast<const uint16_t*>(a.in[slot])[i])<<16);};float v=0;
  if constexpr(Code==Element::activation_low)v=ng::silu(b(0,k)/4.f);
  else if constexpr(Code==Element::activation_product)v=ng::silu(b(0,k))*b(1,k);
  else if constexpr(Code==Element::mix){for(unsigned h=0;h<4;++h)v=v+ng::sigmoid(b(1,h*a.width+k))*b(0,h*a.width+k);v=v/4.f;}
  else {for(unsigned j=0;j<a.count;++j)v=v+b(0,j*a.width+k)*static_cast<const float*>(a.in[1])[j];v=ng::Args::bf(v)+ng::Args::bf(b(2,k)*ng::sigmoid(b(3,0)));}
  a.out[k]=iq3::bf16_bits(v);
 }
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const> p)const override{auto a=bind(p);for(unsigned k=0;k<a.width;++k)body(a,k);}
#else
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override{auto a=bind(p);return q.submit([&](sycl::handler& h){h.depends_on(deps);h.parallel_for(sycl::range<1>(a.width),checked([=](sycl::id<1> i){body(a,i[0]);}));});}
#endif
};
template<Element E> integrated::Launch elements(ownrt::Device& d,const integrated::Spec& s,std::span<const ownrt::Allocation> a){Elements<E> op;op.s=s;auto e=d.compute(op,a,{});return {e,e,1};}
integrated::Launch elementwise(ownrt::Device& d,const integrated::Spec& s,std::span<const ownrt::Allocation> a){
 if(a.size()!=size_t(s.ni+s.no+s.nw+5)||s.no!=1||s.nw||s.ni<1||s.ni>6)throw std::invalid_argument("draft elementwise bindings");
 for(int i=0;i<s.ni+s.no;++i)extent(d,a[i],s.sizes[i]*flash::scalar_bytes(s.types[i]));
 using integrated::Op;
 switch(s.op){case Op::silu_div4:return elements<Element::activation_low>(d,s,a);case Op::silu_product:return elements<Element::activation_product>(d,s,a);case Op::hc_mix:return elements<Element::mix>(d,s,a);case Op::moe_combine:return elements<Element::moe>(d,s,a);default:throw std::invalid_argument("draft elementwise op");}
}
}
