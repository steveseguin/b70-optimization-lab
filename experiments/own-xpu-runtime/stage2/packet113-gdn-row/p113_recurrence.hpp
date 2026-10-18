#pragma once
#include "p82b_recurrence.hpp"
namespace p113rec {
using p82brec::entry_decision;
 inline void host(ng::Shape s,ng::Args a) {
 const int decision=entry_decision(a.i(18)[0],a.i(15)[0],a.i(17)[0],s.capacity,s.tokens);
 if(decision){if(decision==2)a.i(15)[0]=1;return;}
 for(unsigned base=0;base<6144;base+=1)for(int r=0;r<s.tokens;++r) {
  const unsigned h=base/128,key=(s.flags&4)?h%16:h/3,qb=r*10240+key*128,kb=qb+2048;
  float shared[258];
  // Same operations as each device producer, evaluated in dependency order on CPU.
  for(unsigned role=0;role<2;++role){float val[128],leaf[32]{};
   for(unsigned lane=0;lane<32;++lane)for(unsigned z=0;z<4;++z){unsigned x=4*lane+z;val[x]=a.b(0,(role?kb:qb)+x);leaf[lane]=leaf[lane]+val[x]*val[x];}
   const float norm=detmath::sqrt(p49drec::recurrence_tree(leaf)+1e-6f);
   for(unsigned x=0;x<128;++x)shared[role*128+x]=role?val[x]/norm:(val[x]/norm)/detmath::sqrt(float(128));
  }
  const float gate=a.b(1,r*48+h)+a.weight(4,h,s.flags);
  const float sp=gate<20.f?detmath::log(1.f+detmath::exp(gate)):gate;
  const float av=(s.flags&2)?a.f(3)[h]:-detmath::exp(a.weight(3,h,s.flags));
  shared[256]=detmath::exp(av*sp);shared[257]=ng::sigmoid(a.b(2,r*48+h));
  for(unsigned row=0;row<1;++row){unsigned g=base+row,state=g*128;float v[128],pred[32]{},y[32]{};
   for(unsigned lane=0;lane<32;++lane)for(unsigned z=0;z<4;++z){unsigned x=lane*4+z;v[x]=a.b(r?7:5,state+x)*shared[256];pred[lane]=pred[lane]+v[x]*shared[128+x];}
   const float delta=(a.b(0,r*10240+4096+g)-p49drec::recurrence_tree(pred))*shared[257];
   for(unsigned lane=0;lane<32;++lane)for(unsigned z=0;z<4;++z){unsigned x=lane*4+z;v[x]=v[x]+delta*shared[128+x];y[lane]=y[lane]+v[x]*shared[x];}
   a.put(6,r*6144+g,p49drec::recurrence_tree(y));for(unsigned x=0;x<128;++x)a.put(7,state+x,v[x]);
  }
 }
}

#ifndef OWN_RT_HOST_ONLY
inline void device(ng::Shape s,ng::Args a,sycl::nd_item<1> it) {
 const unsigned lane=it.get_local_linear_id(),g=it.get_group_linear_id();
 const unsigned h=g/128,j=g%128,key=(s.flags&4)?h%16:h/3,state=g*128;
 const auto sg=it.get_sub_group();
 int decision=0;
 if(lane==0)decision=p82brec::entry_decision(a.i(18)[0],p49drec::recurrence_error(a),a.i(17)[0],s.capacity,s.tokens);
 decision=sycl::select_from_group(sg,decision,sycl::id<1>(0));
 if(decision){if(decision==2&&g==0&&lane==0)p49drec::recurrence_fail(a);return;}
 for(int r=0;r<s.tokens;++r) {
  const unsigned qb=r*10240+key*128,kb=qb+2048;
  float q[4],k[4];
  for(unsigned role=0;role<2;++role){
   float values[4],sum=0.f;
   for(unsigned z=0;z<4;++z){values[z]=a.b(0,(role?kb:qb)+4*lane+z);sum=sum+values[z]*values[z];}
   sum=p49drec::recurrence_tree_device(sg,sum);
   const float norm=detmath::sqrt(sum+1e-6f);
   for(unsigned z=0;z<4;++z){float value=role?values[z]/norm:(values[z]/norm)/detmath::sqrt(float(128));if(role)k[z]=value;else q[z]=value;}
  }
  float decay=0.f,beta=0.f;
  if(lane==0){
   const float gate=a.b(1,r*48+h)+a.weight(4,h,s.flags);
   const float sp=gate<20.f?detmath::log(1.f+detmath::exp(gate)):gate;
   const float av=(s.flags&2)?a.f(3)[h]:-detmath::exp(a.weight(3,h,s.flags));
   decay=detmath::exp(av*sp);
  }
  if(lane==1)beta=ng::sigmoid(a.b(2,r*48+h));
  decay=sycl::select_from_group(sg,decay,sycl::id<1>(0));
  beta=sycl::select_from_group(sg,beta,sycl::id<1>(1));
  float v[4],pred=0.f;sycl::vec<uint16_t,4> raw;
  raw.load(0,static_cast<const uint16_t*>(a.p[r?7:5])+state+lane*4);
  for(unsigned z=0;z<4;++z){
   v[z]=std::bit_cast<float>(uint32_t(raw[z])<<16)*decay;
   pred=pred+v[z]*k[z];
  }
  pred=p49drec::recurrence_tree_device(sg,pred);
  const float delta=(a.b(0,r*10240+4096+h*128+j)-pred)*beta;
  float y=0.f;
  for(unsigned z=0;z<4;++z){v[z]=v[z]+delta*k[z];y=y+v[z]*q[z];raw[z]=ng::Args::bits(v[z]);}
  y=p49drec::recurrence_tree_device(sg,y);if(lane==0)a.put(6,(r*48+h)*128+j,y);
  raw.store(0,static_cast<uint16_t*>(a.p[7])+state+lane*4);
  // Each lane exclusively owns these same four state elements at every r.
  // Next r reloads their rounded BF16 bytes; no cross-lane state dependency.
 }
}
#endif
struct Kernel final:p49drec::RecurrenceBase {
 ng::Shape shape{};
#ifdef OWN_RT_HOST_ONLY
 void run(std::span<void*const> p)const override {host(shape,p82brec::Kernel<true>::bind(p));}
#else
 sycl::event submit(sycl::queue& q,std::span<void*const> p,const std::vector<sycl::event>& deps)const override {
  const auto a=p82brec::Kernel<true>::bind(p);const auto s=shape;
  return q.submit([&](sycl::handler& handler){handler.depends_on(deps);
   handler.parallel_for(sycl::nd_range<1>(6144*32,32),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{device(s,a,it);});
  });
 }
#endif
};

}
