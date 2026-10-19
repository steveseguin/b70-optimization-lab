#pragma once
#include "native_headers.hpp"
#ifndef OWN_RT_HOST_ONLY
namespace p166hc {using namespace p60;
inline sycl::event norm_kernel(sycl::queue&q,std::array<p60::Bound,2> bb,unsigned batch,const std::vector<sycl::event>&deps){
 return q.submit([&](sycl::handler&h){h.depends_on(deps);sycl::local_accessor<float,1> partial(132,h);sycl::local_accessor<uint32_t,1> control(1,h);
  h.parallel_for(sycl::nd_range<1>(batch*40*256,256),packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
 auto b=bb[it.get_group_linear_id()/40];unsigned local_group=it.get_group_linear_id()%40;

   unsigned local=it.get_local_linear_id(),stream=local_group/10,tile=local_group%10;auto sg=it.get_sub_group();unsigned lane=local%32,group=local/32;
   if(!local)control[0]=uint32_t(*b.active&&!failed(b));it.barrier(sycl::access::fence_space::local_space);if(!control[0])return;
   if(*b.position>=b.capacity){if(!local&&!stream&&!tile)fail(b);return;}
   // Each subgroup computes a complete aligned original 32-leaf subtree.
   for(unsigned c=group;c<80;c+=8){float x=get(b.x,stream*H+c*32+lane);float sum=tree(sg,x*x);if(!lane){partial[c]=sum;if(!tile)b.scratch[stream*80+c]=sum;}}
   if(local>=80&&local<128)partial[local]=0.f;
   it.barrier(sycl::access::fence_space::local_space);
   float upper=local<128?partial[local]:0.f;upper=tree(sg,upper);
   if(!lane&&group<4)partial[128+group]=upper;
   it.barrier(sycl::access::fence_space::local_space);
   float total=(partial[128]+partial[129])+(partial[130]+partial[131]);
   float inv=detmath::rsqrt(total/float(H)+1e-6f);
   norm_output(b,stream,tile*256+local,inv);
  }));
 });
}
inline sycl::event low_inject_kernel(sycl::queue&q,std::array<p60::Bound,2> bb,unsigned batch,const std::vector<sycl::event>&deps){
 const size_t rb=iq3::expanded::row_bytes(Type::Q8_0,K);
 return q.submit([&](sycl::handler&h){h.depends_on(deps);sycl::local_accessor<float,1> partial(4,h);
  h.parallel_for(sycl::nd_range<1>(batch*(L+S)*128,128),packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
 auto b=bb[it.get_group_linear_id()/324];unsigned local_group=it.get_group_linear_id()%324;

   unsigned row=local_group,part=it.get_local_linear_id()/32,lane=it.get_local_linear_id()%32;auto bounds=iq3::kopt2::bounds(K,part,4);float value;
   if(row<L)value=p49c::dense_lane<Type::Q8_0,K>(b.low_w+row*rb,b.norm,bounds.first,bounds.second,lane);
   else value=p49c::dense_lane<Type::F32,K>(b.inject_w+(row-L)*K*4,b.norm,bounds.first,bounds.second,lane);
   value=tree(it.get_sub_group(),value);if(!lane){partial[part]=value;if(row>=L)b.workspace[(row-L)*8+part]=value;}
   it.barrier(sycl::access::fence_space::local_space);
   if(!it.get_local_linear_id()){uint16_t y=iq3::bf16_bits((partial[0]+partial[1])+(partial[2]+partial[3]));
    if(row<L){b.low[row]=y;if(*b.active&&!failed(b)&&*b.position<b.capacity)b.act[row]=p39::hc_activation(y);}else b.inject[row-L]=y;
   }
  }));
 });
}
inline sycl::event gate_mix(sycl::queue&q,std::array<p60::Bound,2> bb,unsigned batch,const std::vector<sycl::event>&deps){
 const auto rb=iq3::expanded::row_bytes(iq3::Type::Q8_0,320);
 return q.submit([&](sycl::handler&h){h.depends_on(deps);sycl::local_accessor<uint16_t,1> gates(16,h);
 h.parallel_for(sycl::nd_range<1>(batch*640*256,256),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
 auto b=bb[it.get_group_linear_id()/640];unsigned local_group=it.get_group_linear_id()%640;

  unsigned local=it.get_local_linear_id(),sub=local/32,lane=local%32,stream=sub%4,base=local_group*4+(sub/4)*2,r=stream*2560+base;auto sg=it.get_sub_group();
  auto sums=p73hc::chains(b.gate_w+r*rb,b.act,lane);
  float v0=sums[0],v1=sums[1];
  for(unsigned s=1;s<32;s*=2){float rhs0=sycl::select_from_group(sg,v0,(lane+s)%32),rhs1=sycl::select_from_group(sg,v1,(lane+s)%32);if(lane%(2*s)==0){v0=v0+rhs0;v1=v1+rhs1;}}
  if(!lane){uint16_t y0=iq3::bf16_bits(v0),y1=iq3::bf16_bits(v1);b.gate[r]=y0;b.gate[r+1]=y1;gates[(sub/4)*8+stream]=y0;gates[(sub/4)*8+4+stream]=y1;}
  it.barrier(sycl::access::fence_space::local_space);
  auto error=sycl::atomic_ref<uint32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(*b.error);
  if(local<4&&*b.active&&!error.load()&&*b.position<b.capacity){unsigned out=local_group*4+local;float sum=0.f;for(unsigned s=0;s<4;++s)sum=sum+ng::sigmoid(p39::widen(gates[local*4+s]))*p60::get(b.norm,s*2560+out);b.mix[out]=iq3::bf16_bits(sum/4.f);}
 });});
}
}
namespace p166route {using namespace p109route;
  inline sycl::event submit(integrated::Spec spec,unsigned batch,sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps){
    const unsigned stride=p.size()/batch;std::array<route42::Args,2> aa{};std::array<const uint32_t*,2> positions{};std::array<std::array<void*,3>,2> activations{};for(unsigned r=0;r<batch;++r){auto row=p.subspan(r*stride,stride);aa[r]=route42::bind(spec,row.first(stride-3));positions[r]=static_cast<const uint32_t*>(row[spec.ni+spec.no+spec.nw+2]);for(unsigned j=0;j<3;++j)activations[r][j]=row[stride-3+j];}
    auto pos=static_cast<const uint32_t*>(p[spec.ni+spec.no+spec.nw+2]);unsigned capacity=spec.g.context;
    std::array<void*,3> activation_args{p[p.size()-3],p[p.size()-2],p[p.size()-1]};
    return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(batch*512,512)](sycl::handler& h){h.depends_on(deps);
      
      sycl::local_accessor<float,1> cache(513,h);
      sycl::local_accessor<unsigned,1> ids(512,h);
      sycl::local_accessor<uint32_t,1> control(1,h);
      h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{auto a=aa[it.get_group_linear_id()];auto pos=positions[it.get_group_linear_id()];auto activation_args=activations[it.get_group_linear_id()];
        unsigned tid=it.get_local_linear_id(),lane=tid%32;auto sg=it.get_sub_group();
        if(!tid)control[0]=uint32_t(*a.active&&!a.failed());
        it.barrier(sycl::access::fence_space::local_space);if(!control[0])return;
        if(tid<32)route42::phase<0,512,10>(a,tid);
        it.barrier(sycl::access::fence_space::global_and_local);
        if(!tid)control[0]=!a.failed();
        it.barrier(sycl::access::fence_space::local_space);if(!control[0])return;
        if(!tid){float m=-INFINITY;for(unsigned c=0;c<32;++c)m=std::max(m,a.scratch[c]);cache[512]=m;}
        it.barrier(sycl::access::fence_space::local_space);
        float maximum=cache[512];
        for(unsigned offset=0;offset<512;offset+=512){
          unsigned j=offset+tid;float v=detmath::exp(a.in().get(j)-maximum);a.scratch[64+j]=v;
          for(unsigned width=1;width<16;width*=2){float r=sycl::select_from_group(sg,v,(lane+width)%32);if(lane%(2*width)==0)v=v+r;}
          if(lane%16==0)a.scratch[32+j/16]=v;
        }
        it.barrier(sycl::access::fence_space::global_and_local);
        if(!tid)cache[512]=route42::subtree<256>(32,0,[&](int j){return a.scratch[32+j];});
        it.barrier(sycl::access::fence_space::local_space);
        float den=cache[512];
        float value=a.scratch[64+tid]/den;unsigned index=tid;
        // 45 compare-exchange rounds, 35 within SG32. Only ten exchange
        // rounds cross subgroup boundaries; those use bounded WG barriers.
        for(unsigned size=2;size<=512;size*=2)for(unsigned distance=size/2;distance;distance/=2){
          float other;unsigned other_index;
          if(distance<32){other=sycl::select_from_group(sg,value,lane^distance);other_index=sycl::select_from_group(sg,index,lane^distance);}
          else{
            cache[tid]=value;ids[tid]=index;it.barrier(sycl::access::fence_space::local_space);
            other=cache[tid^distance];other_index=ids[tid^distance];
            it.barrier(sycl::access::fence_space::local_space);
          }
          bool want_best=((tid&size)==0)==((tid&distance)==0);
          bool take=want_best?better(other,other_index,value,index):better(value,index,other,other_index);
          if(take){value=other;index=other_index;}
        }
        if(tid<10)route42::output<512,10>(a,index,tid);
        it.barrier(sycl::access::fence_space::global_and_local);
        if(!tid)route42::phase<4,512,10>(a,0);
        it.barrier(sycl::access::fence_space::global_and_local);
        for(unsigned i=tid;i<640;i+=512)activation(a,activation_args.data(),i,pos,capacity);
      }));
    });
  }
}
namespace p166down {using namespace p100;
 inline sycl::event submit(unsigned batch,sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps){
  p100::Kernel<2> op;const unsigned rows=2560,count=10,RowsPerGroup=32,WG=64,P=2,K=640;constexpr bool paired=false;std::array<p39::Bound,2> bounds{op.bind(p.first(19)),op.bind(p.subspan(batch==2?19:0,19))};unsigned total=rows*count,groups=(total+RowsPerGroup-1)/RowsPerGroup;
  return q.submit([&](sycl::handler&h){h.depends_on(deps);
   h.parallel_for(sycl::nd_range<1>(size_t(groups)*WG*batch,WG),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{auto b=bounds[it.get_group_linear_id()/groups];unsigned group=it.get_group_linear_id()%groups;
    auto sg=it.get_sub_group();unsigned lane=sg.get_local_linear_id(),sub=it.get_local_linear_id()/32,physical=lane%P,stream=paired?sub%2:0;
    unsigned logical=p100::Kernel<2>::logical_row(group,sub,lane),row=logical%b.rows,slot=logical/b.rows;bool in_range=logical<total;
    iq3::Route route{};if(in_range)route=b.routes[slot];bool ok=in_range&&iq3::valid_route(route,b.experts,b.rows,b.rows),valid=ok&&row<route.row_count;
    float value=0;if(valid){size_t source=size_t(route.expert_id)*b.rows+route.row_begin+row;
     value=p49dvirtual::local_tree<16>(p100::Kernel<2>::chains((stream?b.peer:b.w),source,b.x+(paired?0:slot*K),physical));
    }
    for(unsigned width=1;width<P;width*=2){float rhs=sycl::select_from_group(sg,value,(lane+width)%32);if(physical%(2*width)==0)value=value+rhs;}
    if(in_range&&!physical){(stream?b.py:b.y)[logical]=iq3::bf16_bits(valid?value:iq3::bits_float(0x7fc00000));
     if(!row){(stream?b.peer_status:b.status)[slot]=!ok;if(!ok&&*b.active){uint32_t expected=0;sycl::atomic_ref<uint32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(*b.error).compare_exchange_strong(expected,1);}}
    }
   });
  });
 }
}
#endif
