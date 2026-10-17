#pragma once
#include "p49d_recurrence.hpp"
namespace p67rec {
// Materialize exactly the FP32 values formerly stored in each WG's SLM.
// One head prepass replaces 32 identical per-four-row normalizations.
constexpr unsigned pitch=260, scratch_bytes=48*pitch*4;
inline bool enabled(ng::Shape s,ng::Args a){
 if(!a.i(18)[0]||a.i(15)[0])return false;
 const int pos=a.i(17)[0];if(pos<0||pos>s.capacity-s.tokens){a.i(15)[0]=1;return false;}
 return true;
}
inline void head_host(ng::Shape s,ng::Args a,float*out,unsigned h){
 unsigned key=(s.flags&4)?h%16:h/3,qb=key*128,kb=qb+2048;
 float q[128],k[128],qs[32]{},ks[32]{};
 for(unsigned lane=0;lane<32;++lane)for(unsigned z=0;z<4;++z){unsigned i=lane*4+z;q[i]=a.b(0,qb+i);k[i]=a.b(0,kb+i);qs[lane]=qs[lane]+q[i]*q[i];ks[lane]=ks[lane]+k[i]*k[i];}
 float qn=detmath::sqrt(p49drec::recurrence_tree(qs)+1e-6f),kn=detmath::sqrt(p49drec::recurrence_tree(ks)+1e-6f);
 for(unsigned i=0;i<128;++i){out[i]=(q[i]/qn)/detmath::sqrt(float(128));out[128+i]=k[i]/kn;}
 float gate=a.b(1,h)+a.weight(4,h,s.flags),sp=gate<20.f?detmath::log(1.f+detmath::exp(gate)):gate;
 float av=(s.flags&2)?a.f(3)[h]:-detmath::exp(a.weight(3,h,s.flags));out[256]=detmath::exp(av*sp);out[257]=ng::sigmoid(a.b(2,h));
}
inline void update_host(ng::Shape,ng::Args a,const float*heads,unsigned g){
 unsigned h=g/128,j=g%128,state=g*128;auto p=heads+h*pitch;
 float v[128],pred[32]{},y[32]{};
 for(unsigned lane=0;lane<32;++lane)for(unsigned z=0;z<4;++z){unsigned i=lane*4+z;v[i]=a.b(5,state+i)*p[256];pred[lane]=pred[lane]+v[i]*p[128+i];}
 float delta=(a.b(0,4096+h*128+j)-p49drec::recurrence_tree(pred))*p[257];
 for(unsigned lane=0;lane<32;++lane)for(unsigned z=0;z<4;++z){unsigned i=lane*4+z;v[i]=v[i]+delta*p[128+i];y[lane]=y[lane]+v[i]*p[i];}
 a.put(6,g,p49drec::recurrence_tree(y));for(unsigned i=0;i<128;++i)a.put(7,state+i,v[i]);
}
inline void host(ng::Shape s,ng::Args a,float*scratch){
 if(s.tokens!=1)throw std::invalid_argument("packet67 recurrence requires serial single-token calls");
 if(!enabled(s,a))return;
 for(unsigned h=0;h<48;++h)head_host(s,a,scratch+h*pitch,h);
 for(unsigned g=0;g<6144;++g)update_host(s,a,scratch,g);
}
#ifndef OWN_RT_HOST_ONLY
template<bool Head>struct Kernel final:ownrt::SyclOperation {
 ng::Shape shape;
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override{
  ng::Args a;std::copy_n(p.begin(),19,a.p.begin());auto tmp=static_cast<float*>(p[19]);auto s=shape;
  return q.submit([&](sycl::handler&h){h.depends_on(deps);
   h.parallel_for(sycl::nd_range<1>((Head?48:6144)*32,Head?32:128),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
    unsigned g=it.get_global_linear_id()/32,lane=it.get_local_linear_id()%32;auto sg=it.get_sub_group();
    if(!a.i(18)[0]||p49drec::recurrence_error(a))return;
    int pos=a.i(17)[0];if(pos<0||pos>s.capacity-s.tokens){if(!g&&!lane)p49drec::recurrence_fail(a);return;}
    if constexpr(Head){
     unsigned key=(s.flags&4)?g%16:g/3,qb=key*128,kb=qb+2048;float q[4],k[4],qs=0.f,ks=0.f;
     for(unsigned z=0;z<4;++z){q[z]=a.b(0,qb+4*lane+z);k[z]=a.b(0,kb+4*lane+z);qs=qs+q[z]*q[z];ks=ks+k[z]*k[z];}
     p49drec::recurrence_norm_trees(sg,qs,ks);
     float qn=detmath::sqrt(qs+1e-6f),kn=detmath::sqrt(ks+1e-6f);auto out=tmp+g*pitch;
     for(unsigned z=0;z<4;++z){out[4*lane+z]=(q[z]/qn)/detmath::sqrt(float(128));out[128+4*lane+z]=k[z]/kn;}
     if(!lane){float gate=a.b(1,g)+a.weight(4,g,s.flags),sp=gate<20.f?detmath::log(1.f+detmath::exp(gate)):gate;
      float av=(s.flags&2)?a.f(3)[g]:-detmath::exp(a.weight(3,g,s.flags));out[256]=detmath::exp(av*sp);out[257]=ng::sigmoid(a.b(2,g));}
    }else{
     unsigned head=g/128,j=g%128,state=g*128;auto in=tmp+head*pitch;float q[4],k[4],v[4],pred=0.f;
     float decay=in[256],beta=in[257];sycl::vec<uint16_t,4> raw;raw.load(0,static_cast<const uint16_t*>(a.p[5])+state+lane*4);
     for(unsigned z=0;z<4;++z){q[z]=in[lane*4+z];k[z]=in[128+lane*4+z];v[z]=std::bit_cast<float>(uint32_t(raw[z])<<16)*decay;pred=pred+v[z]*k[z];}
     pred=p49drec::recurrence_tree_device(sg,pred);float delta=(a.b(0,4096+head*128+j)-pred)*beta,y=0.f;
     for(unsigned z=0;z<4;++z){v[z]=v[z]+delta*k[z];y=y+v[z]*q[z];raw[z]=ng::Args::bits(v[z]);}
     y=p49drec::recurrence_tree_device(sg,y);if(!lane)a.put(6,g,y);raw.store(0,static_cast<uint16_t*>(a.p[7])+state+lane*4);
    }
   });
  });
 }
};
#else
struct HostKernel final:integrated::HostOperation {ng::Shape shape;void run(std::span<void*const>p)const override{ng::Args a;std::copy_n(p.begin(),19,a.p.begin());host(shape,a,static_cast<float*>(p[19]));}};
#endif
}
