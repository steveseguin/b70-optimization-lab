#pragma once
#include "p82b_recurrence.hpp"
#include "p49_qsa_reference.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "p49_qsa_kernel.hpp"
#endif
namespace p107 {
// One-token target layers, physical capacity 4096, unchanged BF16 state.
constexpr int capacity=4096, slots=2051, splits=65;
constexpr auto keys=[] {std::array<unsigned,48> a{};for(unsigned h=0;h<48;++h)a[h]=h%16;return a;}();
constexpr auto kv_heads=[] {std::array<unsigned,24> a{};for(unsigned h=0;h<24;++h)a[h]=h/12;return a;}();
constexpr size_t prep_floats=16*256+48*2;
inline ng::Shape gdn_shape(){ng::Shape s{};s.op=ng::gdn;s.capacity=capacity;s.flags=14;return s;}
template<int Extent=4096>inline ng::Shape qsa_shape(){ng::Shape s{};s.op=ng::attention_score;s.capacity=capacity;s.budget=2048;s.extent=Extent;return s;}
inline bool host_admit(ng::Args a){int d=p82brec::entry_decision(a.i(18)[0],a.i(15)[0],a.i(17)[0],capacity,1);if(d==2)a.i(15)[0]=1;return !d;}
inline void gdn_prepare_host(ng::Args a,float* p){
 if(!host_admit(a))return;
 for(unsigned key=0;key<16;++key)for(unsigned role=0;role<2;++role){
  float v[128],leaf[32]{};
  for(unsigned lane=0;lane<32;++lane)for(unsigned z=0;z<4;++z){unsigned x=lane*4+z;v[x]=a.b(0,role*2048+key*128+x);leaf[lane]=leaf[lane]+v[x]*v[x];}
  float norm=detmath::sqrt(p49drec::recurrence_tree(leaf)+1e-6f);
  for(unsigned x=0;x<128;++x)p[key*256+role*128+x]=role?v[x]/norm:(v[x]/norm)/detmath::sqrt(128.f);
 }
 for(unsigned h=0;h<48;++h){float gate=a.b(1,h)+a.weight(4,h,14);float sp=gate<20.f?detmath::log(1.f+detmath::exp(gate)):gate;p[4096+2*h]=detmath::exp(a.f(3)[h]*sp);p[4096+2*h+1]=ng::sigmoid(a.b(2,h));}
}
inline void gdn_update_host(ng::Args a,const float* p){
#if defined(__clang__) && defined(OWN_RT_HOST_ONLY)
 #pragma clang fp exceptions(strict)
#endif
 if(!host_admit(a))return;
 // Retain the production four-row loop structure as well as its expressions.
 // Intel's exceptional operand selection is sensitive to vectorization shape.
 for(unsigned base=0;base<6144;base+=4){
  unsigned h=base/128;float shared[258];std::copy_n(p+keys[h]*256,256,shared);shared[256]=p[4096+2*h];shared[257]=p[4096+2*h+1];
  for(unsigned row=0;row<4;++row){unsigned g=base+row,state=g*128;float v[128],pred[32]{},y[32]{};
   for(unsigned lane=0;lane<32;++lane)for(unsigned z=0;z<4;++z){unsigned x=lane*4+z;v[x]=a.b(5,state+x)*shared[256];pred[lane]=pred[lane]+v[x]*shared[128+x];}
   const float delta=(a.b(0,4096+g)-p49drec::recurrence_tree(pred))*shared[257];
   for(unsigned lane=0;lane<32;++lane)for(unsigned z=0;z<4;++z){unsigned x=lane*4+z;v[x]=v[x]+delta*shared[128+x];y[lane]=y[lane]+v[x]*shared[x];}
   a.put(6,g,p49drec::recurrence_tree(y));for(unsigned x=0;x<128;++x)a.put(7,state+x,v[x]);
  }
 }
}
// Scheduling mirror: load BF16 KV once for four heads, retain all lower FP32
// partials, then run the unchanged upper split tree. No reduction reassociation.
inline void qsa_host(ng::Args a){
 if(!host_admit(a))return;auto s=qsa_shape();int n=p47ref::count(s,a,0);if(!n)return;int C=(n+31)/32;
 for(int first=0;first<24;first+=4){std::vector<float> partial(4*C*258);
  for(int c=0;c<C;++c){uint16_t cache[2][32][256]{};int len=std::min(32,n-c*32);
   for(int j=0;j<len;++j)for(int d=0;d<256;++d)for(int which=0;which<2;++which)cache[which][j][d]=static_cast<const uint16_t*>(a.p[2+which])[(a.i(4)[c*32+j]*2+kv_heads[first])*256+d];
   for(int head=0;head<4;++head){int h=first+head;auto*p=partial.data()+(head*C+c)*258;std::vector<float> prob(32,0.f);float maximum=-INFINITY;
    for(int j=0;j<len;++j){std::vector<float> products(256);for(int d=0;d<256;++d)products[d]=a.b(0,h*256+d)*iq3::bits_float(uint32_t(cache[0][j][d])<<16);prob[j]=p47ref::adjacent(std::move(products))/detmath::sqrt(256.f);maximum=std::max(maximum,prob[j]);}
    p[256]=maximum;for(int j=0;j<len;++j)prob[j]=detmath::exp(prob[j]-maximum);p[257]=p47ref::adjacent(prob);
    for(int d=0;d<256;++d){std::vector<float> terms(32,0.f);for(int j=0;j<len;++j)terms[j]=prob[j]*iq3::bits_float(uint32_t(cache[1][j][d])<<16);p[d]=p47ref::adjacent(std::move(terms));}
   }
  }
  for(int head=0;head<4;++head){int h=first+head;auto*p=partial.data()+head*C*258;float maximum=-INFINITY;for(int c=0;c<C;++c)maximum=std::max(maximum,p[c*258+256]);std::vector<float> factors(C),dens(C);for(int c=0;c<C;++c){factors[c]=detmath::exp(p[c*258+256]-maximum);dens[c]=p[c*258+257]*factors[c];}float den=p47ref::adjacent(std::move(dens));for(int d=0;d<256;++d){std::vector<float> terms(C);for(int c=0;c<C;++c)terms[c]=p[c*258+d]*factors[c];p47ref::store(a,h*256+d,p47ref::adjacent(std::move(terms))/den,nullptr);}}
 }
}
#ifdef OWN_RT_HOST_ONLY
using Base=integrated::HostOperation;
#else
using Base=ownrt::SyclOperation;
inline bool device_admit(ng::Args a){int d=p82brec::entry_decision(a.i(18)[0],p49drec::recurrence_error(a),a.i(17)[0],capacity,1);if(d==2)p49drec::recurrence_fail(a);return !d;}
inline sycl::event gdn_prepare(sycl::queue&q,ng::Args a,float*p,const std::vector<sycl::event>&deps){return q.submit([&](sycl::handler&h){h.depends_on(deps);h.parallel_for(sycl::nd_range<1>(32*32,128),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
 if(!device_admit(a))return;unsigned group=it.get_global_linear_id()/32,lane=it.get_sub_group().get_local_linear_id(),key=group/2,role=group%2;float v[4],sum=0.f;
 for(unsigned z=0;z<4;++z){v[z]=a.b(0,role*2048+key*128+lane*4+z);sum=sum+v[z]*v[z];}sum=p49drec::recurrence_tree_device(it.get_sub_group(),sum);float norm=detmath::sqrt(sum+1e-6f);
 for(unsigned z=0;z<4;++z)p[key*256+role*128+lane*4+z]=role?v[z]/norm:(v[z]/norm)/detmath::sqrt(128.f);
 unsigned head=it.get_global_linear_id();if(head<48){float gate=a.b(1,head)+a.weight(4,head,14);float sp=gate<20.f?detmath::log(1.f+detmath::exp(gate)):gate;p[4096+2*head]=detmath::exp(a.f(3)[head]*sp);p[4096+2*head+1]=ng::sigmoid(a.b(2,head));}
 });});}
inline sycl::event gdn_update(sycl::queue&q,ng::Args a,const float*p,const std::vector<sycl::event>&deps){return q.submit([&](sycl::handler&h){h.depends_on(deps);sycl::local_accessor<float,1> shared(258,h);h.parallel_for(sycl::nd_range<1>(6144*32,128),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
 if(!device_admit(a))return;unsigned g=it.get_global_linear_id()/32,lane=it.get_sub_group().get_local_linear_id(),head=g/128,key=keys[head],base=g*128;unsigned lid=it.get_local_linear_id();for(unsigned x=lid;x<256;x+=128)shared[x]=p[key*256+x];if(lid<2)shared[256+lid]=p[4096+2*head+lid];it.barrier(sycl::access::fence_space::local_space);float v[4],ks[4],qs[4],pred=0.f,y=0.f;
 sycl::vec<uint16_t,4> raw;raw.load(0,static_cast<const uint16_t*>(a.p[5])+base+lane*4);
 for(unsigned z=0;z<4;++z){unsigned x=lane*4+z;qs[z]=shared[x];ks[z]=shared[128+x];v[z]=iq3::bits_float(uint32_t(raw[z])<<16)*shared[256];pred=pred+v[z]*ks[z];}
 pred=p49drec::recurrence_tree_device(it.get_sub_group(),pred);float delta=(a.b(0,4096+g)-pred)*shared[257];
 for(unsigned z=0;z<4;++z){v[z]=v[z]+delta*ks[z];y=y+v[z]*qs[z];raw[z]=ng::Args::bits(v[z]);}y=p49drec::recurrence_tree_device(it.get_sub_group(),y);if(!lane)a.put(6,g,y);raw.store(0,static_cast<uint16_t*>(a.p[7])+base+lane*4);
 });});}
// Four heads per tile, still four score subgroups per head. 32 KiB of shared
// BF16 K/V replaces four separate global reads. Head groups never cross KV head.
template<int Extent>inline sycl::event qsa_tiles(sycl::queue&q,ng::Args a,const int*counts,float*partial,const std::vector<sycl::event>&deps){constexpr int splits=(std::min(Extent,2051)+31)/32;return q.submit([&](sycl::handler&h){h.depends_on(deps);sycl::local_accessor<uint16_t,1>kv(2*32*256,h);sycl::local_accessor<float,1>local(4*66,h);
 h.parallel_for(sycl::nd_range<1>(6*splits*512,512),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
 int group=it.get_group_linear_id(),c=group%splits,first=(group/splits)*4,lid=it.get_local_linear_id(),head=lid/128,hl=lid%128,sub=hl/32,lane=hl%32,start=c*32,n=counts[0];if(n<=0||p47::blocked(a)||start>=n)return;
 for(int x=lid;x<2*32*256;x+=512){int which=x/(32*256),j=(x/256)%32,d=x%256;kv[x]=start+j<n?static_cast<const uint16_t*>(a.p[2+which])[(a.i(4)[start+j]*2+kv_heads[first])*256+d]:0;}
 it.barrier(sycl::access::fence_space::local_space);auto sg=it.get_sub_group();int hh=first+head,offset=head*66;float*p=partial+(hh*splits+c)*258;
 for(int j=sub;j<32;j+=4){float score=-INFINITY;if(start+j<n){float v[8];for(int z=0;z<8;++z)v[z]=p47::bf(kv[j*256+lane*8+z])*a.b(0,hh*256+lane*8+z);for(int step=1;step<8;step*=2)for(int z=0;z<8;z+=2*step)v[z]=v[z]+v[z+step];score=p47::lane_tree(sg,v[0])/detmath::sqrt(256.f);}if(!lane)local[offset+j]=score;}
 it.barrier(sycl::access::fence_space::local_space);if(!hl){float m=-INFINITY;for(int j=0;j<32&&start+j<n;++j)m=std::max(m,local[offset+j]);local[offset+64]=m;p[256]=m;}
 it.barrier(sycl::access::fence_space::local_space);if(hl<32){float v=start+hl<n?detmath::exp(local[offset+hl]-local[offset+64]):0.f;local[offset+32+hl]=v;float den=p47::lane_tree(sg,v);if(!hl)p[257]=den;}
 it.barrier(sycl::access::fence_space::local_space);sycl::vec<float,2>vals[32];for(int j=0;j<32;++j){vals[j]=sycl::vec<float,2>(0.f);if(start+j<n)for(int d=0;d<2;++d)vals[j][d]=local[offset+32+j]*p47::bf(kv[32*256+j*256+hl*2+d]);}
 for(int step=1;step<32;step*=2)for(int j=0;j<32;j+=2*step)vals[j]=vals[j]+vals[j+step];p[hl*2]=vals[0][0];p[hl*2+1]=vals[0][1];
 });});}
#endif
// Capture by value. Fixed plans bind once; changing token/state/selected IDs
// remain device inputs. There is no host synchronization inside either subgraph.
template<int Stage>struct Gdn final:Base {
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const> p)const override{ng::Args a;std::copy_n(p.begin(),19,a.p.begin());auto*f=static_cast<float*>(p[19]);if constexpr(Stage==0)gdn_prepare_host(a,f);else gdn_update_host(a,f);}
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&d)const override{ng::Args a;std::copy_n(p.begin(),19,a.p.begin());auto*f=static_cast<float*>(p[19]);if constexpr(Stage==0)return gdn_prepare(q,a,f,d);else return gdn_update(q,a,f,d);}
#endif
};
template<int Stage,int Extent=4096>struct Qsa final:Base {
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const>p)const override{if constexpr(Stage==0){ng::Args a;std::copy_n(p.begin(),19,a.p.begin());qsa_host(a);}}
#else
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&d)const override{ng::Args a;std::copy_n(p.begin(),19,a.p.begin());auto*counts=static_cast<int*>(p[19]);auto*partial=reinterpret_cast<float*>(static_cast<uint8_t*>(p[19])+16);if constexpr(Stage==0)return p47::admit(q,qsa_shape<Extent>(),a,counts,d);if constexpr(Stage==1)return qsa_tiles<Extent>(q,a,counts,partial,d);if constexpr(Stage==2)return p47::combine<true>(q,qsa_shape<Extent>(),a,counts,partial,d);}
#endif
};
}
