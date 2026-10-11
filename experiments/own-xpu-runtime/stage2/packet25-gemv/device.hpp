#pragma once
#include "fixtures.hpp"
#include <sycl/sycl.hpp>
namespace p25 {
template<class F> inline const unsigned char capture_size[sizeof(F)] __attribute__((used)) = {};
template<class F> F checked(F f){static_assert(sizeof(F)<=1024,"device kernel capture exceeds 1024 bytes");(void)capture_size<F>;return f;}
struct Share {sycl::sub_group sg;unsigned lane;template<class F>auto operator()(unsigned owner,F f)const{using R=decltype(f(owner));R v{};if(lane==owner)v=f(owner);return sycl::select_from_group(sg,v,owner);}};
struct Tables:kopt3::ConstantTables {sycl::sub_group sg;explicit Tables(sycl::sub_group g):sg(g){};int iq4(unsigned i)const{unsigned l=sg.get_local_linear_id();int v=l<16?kopt3::iq4_levels[l]:0;return sycl::select_from_group(sg,v,i);}};
struct Params {
 const uint8_t *w,*peer;const uint16_t* x;const float *half,*peer_half;
 uint8_t *stage,*peer_stage;Result* y;const unsigned* routes;
 size_t rb,erb;unsigned rows,k,count,split;bool paired,exceptional;
};
static_assert(sizeof(Params)<=1024);
template<Type T> sycl::event decode_stage(sycl::queue&q,const Params* parameters,const Params& host){
 size_t n=size_t(host.rows)*host.count*host.k;return q.submit([&](sycl::handler&h){
 h.parallel_for(sycl::range<1>(n),checked([=](sycl::id<1> id){auto d=*parameters;size_t logical=id[0]/d.k,i=id[0]%d.k,row=logical%d.rows,slot=logical/d.rows;
 size_t sr=(d.count>1?size_t(d.routes[slot])*d.rows:0)+row;constexpr auto f=layout(T);
 for(unsigned p=0;p<(d.paired?2u:1u);++p){const auto src=(p?d.peer:d.w)+sr*d.rb;auto out=(p?d.peer_stage:d.stage)+logical*d.erb;const auto b=src+(i/f.elements)*f.bytes;
 out[i]=uint8_t(expanded::quant(T,b,i%f.elements));
 if(i%expanded::group_size(T)==0){float s=expanded::scale(T,b,i%f.elements);auto bits=std::bit_cast<uint32_t>(s);auto off=d.k+4*(i/expanded::group_size(T));for(unsigned j=0;j<4;++j)out[off+j]=bits>>(8*j);}
 if(i%f.elements==0)expanded::metadata(T,b,out+d.k+4*(d.k/expanded::group_size(T))+(i/f.elements)*expanded::metadata_size(T));
 }return;
 }));});
}
template<Type T,C V> sycl::event gemv(sycl::queue&q,const Params* parameters,const Params& host){
 unsigned rpg=rows_per_group(V,host.split),wg=local_size(V,host.split);size_t groups=(size_t(host.rows)*host.count+rpg-1)/rpg;
 return q.submit([&](sycl::handler&h){sycl::local_accessor<float,1> partial(rpg*2*host.split,h);
 h.parallel_for(sycl::nd_range<1>(groups*wg,wg),checked([=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
 auto d=*parameters;auto sg=it.get_sub_group();unsigned l=sg.get_local_linear_id(),sub=sg.get_group_linear_id();unsigned rr=sub/d.split,part=sub%d.split;
 size_t logical=it.get_group_linear_id()*rpg+rr,row=logical%d.rows,slot=logical/d.rows;bool active=rr<rpg&&logical<size_t(d.rows)*d.count;
 std::array<float,2> value{};
 if(active){size_t sr=(d.count>1?size_t(d.routes[slot])*d.rows:0)+row;
 const auto w=V==C::staged?d.stage+logical*d.erb:d.w+sr*d.rb;
 const auto peer=V==C::staged?d.peer_stage+logical*d.erb:d.peer+sr*d.rb;
 const auto x=d.x+slot*d.k;auto bounds=kopt2::bounds(d.k,part,d.split);size_t blocks=d.k/layout(T).elements;
 value=lane<T,V>(w,peer,x,d.half+(V==C::half_table?sr*blocks:0),d.peer_half+(V==C::half_table?sr*blocks:0),d.k,bounds.first,bounds.second,l,d.paired,Tables(sg),Share{sg,l});}
 for(unsigned p=0;p<(d.paired?2u:1u);++p){for(unsigned width=1;width<32;width*=2){float rhs=sycl::select_from_group(sg,value[p],(l+width)%32);if(l%(2*width)==0)value[p]=value[p]+rhs;}
 if(rr<rpg&&l==0)partial[(rr*2+p)*d.split+part]=value[p];}
 it.barrier(sycl::access::fence_space::local_space);
 if(active&&l==0&&part==0){std::array<float,2> out{};for(unsigned p=0;p<(d.paired?2u:1u);++p){auto off=(rr*2+p)*d.split;out[p]=d.split==1?partial[off]:(partial[off]+partial[off+1])+(partial[off+2]+partial[off+3]);}d.y[logical]=result(out);}return;
 }));});
}
struct Events {std::array<sycl::event,2> event;unsigned count;};
inline Events submit(sycl::queue&q,const Params* parameters,const Params& host,Type t,C c){
 if(host.exceptional)c=C::current;
 return select_type(t,[&]<Type T>(){return select_candidate(c,[&]<C V>(){Events out{};
 if constexpr(V==C::staged&&expert(T))out.event[out.count++]=decode_stage<T>(q,parameters,host);
 out.event[out.count++]=gemv<T,V>(q,parameters,host);return out;});});
}
}
