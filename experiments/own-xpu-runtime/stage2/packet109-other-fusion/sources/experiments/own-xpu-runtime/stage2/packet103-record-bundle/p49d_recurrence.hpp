#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet103-record-bundle/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet103-record-bundle/p49d_recurrence.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet109-other-fusion/sources/experiments/own-xpu-runtime/stage2/packet103-record-bundle/prepared_submission.hpp"
#endif
#line 1
#pragma once
// Packet54 independently written scheduling experiment. Numerical definitions
// and the unchanged scalar oracle are read-only packet49c dependencies.
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet109-other-fusion/sources/experiments/own-xpu-runtime/stage2/packet103-record-bundle/adapter.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet109-other-fusion/sources/experiments/own-xpu-runtime/stage2/packet103-record-bundle/round2.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet109-other-fusion/sources/experiments/own-xpu-runtime/stage1/packet3-prep/src/sycl_operation.hpp"
#endif
#include <algorithm>
#include <array>
#include <span>
#include <stdexcept>

namespace p49drec {
// Adjacent 32-leaf tree, following four left-to-right products per leaf.
inline float recurrence_tree(const float* leaves) {
 float v[32];std::copy_n(leaves,32,v);
 for(unsigned stride=1;stride<32;stride*=2)
  for(unsigned i=0;i<32;i+=2*stride)v[i]=v[i]+v[i+stride];
 return v[0];
}
inline void recurrence_reference(ng::Shape shape,ng::Args args) {
 round2::gdn_host(shape,args);
}
// CPU mirror computes shared inputs once per tile. State and output arithmetic
// are deliberately separate from the production scalar oracle above.
template<unsigned RowsPerWG> inline void recurrence_host_rows(ng::Shape s,ng::Args a,
 unsigned first,unsigned count) {
 static_assert(RowsPerWG==4||RowsPerWG==8);
 if(!a.i(18)[0]||a.i(15)[0])return;
 int pos=a.i(17)[0];if(pos<0||pos>s.capacity-s.tokens){a.i(15)[0]=1;return;}
 if(first%RowsPerWG||count%RowsPerWG||first+count>6144)throw std::invalid_argument("p54 recurrence row tile");
 for(unsigned base=first;base<first+count;base+=RowsPerWG) {
  const unsigned h=base/128,key=(s.flags&4)?h%16:h/3;
  for(int r=0;r<s.tokens;++r) {
   const unsigned qb=r*10240+key*128,kb=qb+2048;
   float q[128],k[128],qs[32]{},ks[32]{};
   for(unsigned lane=0;lane<32;++lane)for(unsigned z=0;z<4;++z) {
    unsigned x=lane*4+z;q[x]=a.b(0,qb+x);k[x]=a.b(0,kb+x);
    qs[lane]=qs[lane]+q[x]*q[x];ks[lane]=ks[lane]+k[x]*k[x];
   }
   const float qn=detmath::sqrt(recurrence_tree(qs)+1e-6f);
   const float kn=detmath::sqrt(recurrence_tree(ks)+1e-6f);
   const float gate=a.b(1,r*48+h)+a.weight(4,h,s.flags);
   const float sp=gate<20.f?detmath::log(1.f+detmath::exp(gate)):gate;
   const float av=(s.flags&2)?a.f(3)[h]:-detmath::exp(a.weight(3,h,s.flags));
   const float decay=detmath::exp(av*sp),beta=ng::sigmoid(a.b(2,r*48+h));
   for(unsigned x=0;x<128;++x) {
    q[x]=(q[x]/qn)/detmath::sqrt(float(128));k[x]=k[x]/kn;
   }
   for(unsigned row=0;row<RowsPerWG;++row) {
    const unsigned g=base+row,j=g%128,state=g*128;
    float v[128],pred[32]{},y[32]{};
    for(unsigned lane=0;lane<32;++lane)for(unsigned z=0;z<4;++z) {
     unsigned x=lane*4+z;v[x]=a.b(r?7:5,state+x)*decay;
     pred[lane]=pred[lane]+v[x]*k[x];
    }
    const float delta=(a.b(0,r*10240+4096+h*128+j)-recurrence_tree(pred))*beta;
    for(unsigned lane=0;lane<32;++lane)for(unsigned z=0;z<4;++z) {
     unsigned x=lane*4+z;v[x]=v[x]+delta*k[x];y[lane]=y[lane]+v[x]*q[x];
    }
    a.put(6,(r*48+h)*128+j,recurrence_tree(y));
    for(unsigned x=0;x<128;++x)a.put(7,state+x,v[x]);
   }
  }
 }
}
template<unsigned RowsPerWG> inline void recurrence_host(ng::Shape s,ng::Args a) {
 recurrence_host_rows<RowsPerWG>(s,a,0,6144);
}
#ifndef OWN_RT_HOST_ONLY
inline float recurrence_tree_device(sycl::sub_group sg,float value) {
 const unsigned lane=sg.get_local_linear_id();
 for(unsigned stride=1;stride<32;stride*=2) {
  const float right=sycl::select_from_group(sg,value,sycl::id<1>((lane+stride)%32));
  if(lane%(stride*2)==0)value=value+right;
 }
 return sycl::select_from_group(sg,value,sycl::id<1>(0));
}
// Both independent normalization reductions advance through the SAME trees,
// interleaved rather than completing q's shuffle chain before starting k's.
inline void recurrence_norm_trees(sycl::sub_group sg,float& q,float& k) {
 const unsigned lane=sg.get_local_linear_id();
 for(unsigned stride=1;stride<32;stride*=2) {
  float qr=sycl::select_from_group(sg,q,sycl::id<1>((lane+stride)%32));
  float kr=sycl::select_from_group(sg,k,sycl::id<1>((lane+stride)%32));
  if(lane%(stride*2)==0){q=q+qr;k=k+kr;}
 }
 q=sycl::select_from_group(sg,q,sycl::id<1>(0));
 k=sycl::select_from_group(sg,k,sycl::id<1>(0));
}
inline int recurrence_error(ng::Args a) {
 return sycl::atomic_ref<int32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,
  sycl::access::address_space::global_space>(a.i(15)[0]).load();
}
inline void recurrence_fail(ng::Args a) {
 sycl::atomic_ref<int32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,
  sycl::access::address_space::global_space>(a.i(15)[0]).store(1);
}
template<unsigned RowsPerWG> inline void recurrence_device(ng::Shape s,ng::Args a,
 sycl::nd_item<1> it,float* shared) {
 const unsigned lid=it.get_local_linear_id(),lane=lid%32,row=lid/32;
 const unsigned base=it.get_group_linear_id()*RowsPerWG,g=base+row;
 const unsigned h=base/128,j=g%128,key=(s.flags&4)?h%16:h/3,state=g*128;
 const auto sg=it.get_sub_group();
 // Uniform decision before the first local-memory rendezvous. All subsequent
 // workgroups preserve an already-set sticky error and inactive output bytes.
 if(lid==0)shared[258]=float(!a.i(18)[0]||recurrence_error(a));
 it.barrier(sycl::access::fence_space::local_space);
 if(shared[258])return;
 const int pos=a.i(17)[0];
 if(pos<0||pos>s.capacity-s.tokens) {
  if(base==0&&lid==0)recurrence_fail(a);return;
 }
 for(int r=0;r<s.tokens;++r) {
  const unsigned qb=r*10240+key*128,kb=qb+2048;
  if(row==0) {
   float q[4],k[4],qs=0.f,ks=0.f;
   for(unsigned z=0;z<4;++z) {
    q[z]=a.b(0,qb+4*lane+z);k[z]=a.b(0,kb+4*lane+z);
    qs=qs+q[z]*q[z];ks=ks+k[z]*k[z];
   }
   recurrence_norm_trees(sg,qs,ks);
   const float qn=detmath::sqrt(qs+1e-6f),kn=detmath::sqrt(ks+1e-6f);
   for(unsigned z=0;z<4;++z) {
    shared[4*lane+z]=(q[z]/qn)/detmath::sqrt(float(128));
    shared[128+4*lane+z]=k[z]/kn;
   }
   if(lane==0) {
    const float gate=a.b(1,r*48+h)+a.weight(4,h,s.flags);
    const float sp=gate<20.f?detmath::log(1.f+detmath::exp(gate)):gate;
    const float av=(s.flags&2)?a.f(3)[h]:-detmath::exp(a.weight(3,h,s.flags));
    shared[256]=detmath::exp(av*sp);shared[257]=ng::sigmoid(a.b(2,r*48+h));
   }
  }
  it.barrier(sycl::access::fence_space::local_space);
  float q[4],k[4],v[4],pred=0.f;
  const float decay=shared[256],beta=shared[257];
  sycl::vec<uint16_t,4> raw;
  raw.load(0,static_cast<const uint16_t*>(a.p[r?7:5])+state+lane*4);
  for(unsigned z=0;z<4;++z) {
   q[z]=shared[lane*4+z];k[z]=shared[128+lane*4+z];
   v[z]=std::bit_cast<float>(uint32_t(raw[z])<<16)*decay;
   pred=pred+v[z]*k[z];
  }
  pred=recurrence_tree_device(sg,pred);
  const float delta=(a.b(0,r*10240+4096+h*128+j)-pred)*beta;
  float y=0.f;
  for(unsigned z=0;z<4;++z) {
   v[z]=v[z]+delta*k[z];y=y+v[z]*q[z];raw[z]=ng::Args::bits(v[z]);
  }
  y=recurrence_tree_device(sg,y);if(lane==0)a.put(6,(r*48+h)*128+j,y);
  raw.store(0,static_cast<uint16_t*>(a.p[7])+state+lane*4);
  // Token r+1 consumes the rounded BF16 bytes. Never carry FP32 state across
  // token rows. This also prevents the producer SG overwriting shared q/k while
  // another SG still consumes the previous token's shared values.
  if(r+1<s.tokens)it.barrier(sycl::access::fence_space::global_and_local);
 }
}
#endif
#ifdef OWN_RT_HOST_ONLY
using RecurrenceBase=integrated::HostOperation;
#else
using RecurrenceBase=ownrt::SyclOperation;
#endif
template<unsigned RowsPerWG> struct RecurrenceKernel final:RecurrenceBase {
 static_assert(RowsPerWG==4||RowsPerWG==8);
 ng::Shape shape{};
 static ng::Args bind(std::span<void*const> p) {
  if(p.size()!=19)throw std::invalid_argument("p54 recurrence binding count");
  ng::Args a;std::copy_n(p.begin(),19,a.p.begin());return a;
 }
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const> p)const override {recurrence_host<RowsPerWG>(shape,bind(p));}
#else
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override {
  const auto a=bind(p);const auto s=shape;
  return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(6144*32,RowsPerWG*32)](sycl::handler& handler) {
   sycl::local_accessor<float,1> shared(259,handler);
   handler.parallel_for(p35_range0,
    packet26::checked([=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]] {
     recurrence_device<RowsPerWG>(s,a,it,shared.get_multi_ptr<sycl::access::decorated::no>().get());
    }));
  });
 }
#endif
};
template<class T> struct RecurrenceBindingSet {ng::Shape shape;std::array<T,19> ids;};
using RecurrenceBindings=RecurrenceBindingSet<ownrt::Allocation>;
template<class T> inline RecurrenceBindingSet<T> recurrence_bindings_impl(const integrated::Spec& s,
 std::span<const T> bindings) {
 if(s.op!=integrated::Op::gdn||(s.ni!=4&&s.ni!=6)||s.no!=2||s.nw!=2||
    bindings.size()<size_t(s.ni+s.no+s.nw+4))
  throw std::invalid_argument("p54 recurrence requires production GDN bindings");
 if(s.grids[0]!=iq3::Type::F32)throw std::invalid_argument("p54 stored GDN decay must be F32");
 if(s.ni==6&&(bindings[4]!=bindings[s.ni+s.no+s.nw+3]||bindings[5]!=bindings[s.ni+s.no+s.nw+1]))throw std::invalid_argument("p54 recurrence duplicate controls");
 RecurrenceBindingSet<T> out;out.shape.op=ng::gdn;out.shape.capacity=s.g.context;
 out.shape.flags=2|(s.packed_heads?4:0)|(s.grids[1]==iq3::Type::F32?8:0);
 out.ids.fill(bindings.back());
 for(unsigned slot=0;slot<3;++slot)out.ids[slot]=bindings[slot];
 out.ids[3]=bindings[s.ni+s.no];out.ids[4]=bindings[s.ni+s.no+1];
 out.ids[5]=bindings[3];out.ids[6]=bindings[s.ni];out.ids[7]=bindings[s.ni+1];
 out.ids[15]=bindings[s.ni+s.no+s.nw+1];out.ids[17]=bindings[s.ni+s.no+s.nw+2];
 out.ids[18]=bindings[s.ni+s.no+s.nw+3];return out;
}
inline RecurrenceBindings recurrence_bindings(const integrated::Spec& s,
 std::span<const ownrt::Allocation> bindings) {return recurrence_bindings_impl(s,bindings);}
inline ng::Args recurrence_args(const integrated::Spec& s,std::span<void*const> p) {
 auto b=recurrence_bindings_impl<void*>(s,p);ng::Args a;a.p=b.ids;return a;
}
inline void recurrence_control(const integrated::Spec& s,std::span<void*const> p) {
 auto b=recurrence_bindings_impl<void*>(s,p);ng::Args a;a.p=b.ids;recurrence_reference(b.shape,a);
}
} // namespace p49drec
