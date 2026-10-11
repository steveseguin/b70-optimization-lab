#include "device.hpp"
#include "sycl_operation.hpp"
#include <array>
#include <limits>
#include <set>
namespace iq3 {
namespace {
size_t product(size_t a,size_t b) {if(b && a>std::numeric_limits<size_t>::max()/b)throw std::overflow_error("kernel extent");return a*b;}
void check(ownrt::Device& d,ownrt::Allocation id,size_t n) {
  auto& r=d.arena.row(id);if(!n || !r.live || r.memory!=ownrt::Memory::device || n>r.bytes)throw std::invalid_argument("kernel binding extent/residency");
}
void unique(std::initializer_list<ownrt::Allocation> ids) {if(std::set<ownrt::Allocation>(ids).size()!=ids.size())throw std::invalid_argument("aliased kernel buffers");}
void types(Type t,Type a,Type o,unsigned sg) {
  if(!layout(t).elements || (a!=Type::BF16 && a!=Type::F16) || (o!=Type::BF16 && o!=Type::F16) || (sg!=16 && sg!=32))throw std::invalid_argument("kernel type/subgroup");
}
size_t row_size(Type t,size_t k) {auto l=layout(t);if(!l.elements || !k || k%l.elements)throw std::invalid_argument("packed row width");return product(k/l.elements,l.bytes);}
struct Decode : ownrt::SyclOperation {
  Type type;size_t elements;unsigned subgroup;
  template<unsigned SG> sycl::event run(sycl::queue& q,std::span<void* const> p,const std::vector<sycl::event>& deps) const {
    auto input=static_cast<const uint8_t*>(p[0]);auto output=static_cast<float*>(p[1]);auto t=type;auto n=elements;
    return q.submit([&](sycl::handler& h) {
      h.depends_on(deps);
      h.parallel_for(sycl::nd_range<1>(sycl::range<1>((n+SG-1)/SG*SG),sycl::range<1>(SG)),[=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(SG)]] {
        auto i=it.get_global_linear_id();if(i<n)output[i]=element(t,input,i);
      });
    });
  }
  sycl::event submit(sycl::queue& q,std::span<void* const> p,const std::vector<sycl::event>& deps) const override {return subgroup==16?run<16>(q,p,deps):run<32>(q,p,deps);}
};
struct Multiply : ownrt::SyclOperation {
  Type type,activation,output_type;size_t columns,row_bytes;uint32_t rows,experts,count,span;unsigned subgroup;bool routed,diagnostic;
  template<unsigned SG> sycl::event run(sycl::queue& q,std::span<void* const> p,const std::vector<sycl::event>& deps) const {
    const auto bank=static_cast<const uint8_t*>(p[0]);const auto x=static_cast<const uint16_t*>(p[1]);const auto y=static_cast<uint16_t*>(p[2]);
    const auto route=routed?static_cast<const Route*>(p[3]):nullptr;const auto status=routed?static_cast<uint32_t*>(p[4]):nullptr;
    const auto fp32=diagnostic?static_cast<float*>(p[routed?5:3]):nullptr;
    auto t=type,a=activation,o=output_type;auto k=columns,rb=row_bytes;auto nr=rows,ne=experts,nc=count,rs=span;auto is_routed=routed;
    return q.submit([&](sycl::handler& h) {
      h.depends_on(deps);sycl::local_accessor<float,1> sums(32,h);
      h.parallel_for(sycl::nd_range<1>(sycl::range<1>(size_t(nc)*rs*32),sycl::range<1>(32)),[=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(SG)]] {
        auto group=it.get_group_linear_id(),lane=it.get_local_linear_id();auto slot=group/rs,row=group%rs;
        Route r=is_routed?route[slot]:Route{0,0,nr}; // only device allocation may supply route
        bool valid=valid_route(r,ne,nr,rs),active=valid && row<r.row_count;
        if(is_routed && row==0 && lane==0)status[slot]=valid?0:1;
        float acc=0;
        if(active)acc=lane_dot(t,bank+(size_t(r.expert_id)*nr+r.row_begin+row)*rb,x+slot*k,a,k,lane);
        sums[lane]=acc;it.barrier(sycl::access::fence_space::local_space);
        for(unsigned width=1;width<32;width*=2) {
          if(lane%(2*width)==0)sums[lane]=sums[lane]+sums[lane+width];
          it.barrier(sycl::access::fence_space::local_space);
        }
        if(lane==0) {
          float value=active?sums[0]:bits_float(0x7fc00000);
          y[group]=output_bits(value,o);if(fp32)fp32[group]=value;
        }
      });
    });
  }
  sycl::event submit(sycl::queue& q,std::span<void* const> p,const std::vector<sycl::event>& deps) const override {return subgroup==16?run<16>(q,p,deps):run<32>(q,p,deps);}
};
}
ownrt::Event dequant(ownrt::Device& d,Type t,ownrt::Allocation input,ownrt::Allocation output,size_t n,unsigned sg) {
  types(t,Type::BF16,Type::BF16,sg);auto bytes=row_size(t,n);unique({input,output});check(d,input,bytes);check(d,output,product(n,4));
  Decode op;op.type=t;op.elements=n;op.subgroup=sg;std::array ids{input,output};return d.compute(op,ids,{});
}
ownrt::Event gemv(ownrt::Device& d,Type t,ownrt::Allocation w,ownrt::Allocation x,ownrt::Allocation y,size_t rows,size_t k,Type a,Type o,unsigned sg,ownrt::Allocation fp32) {
  types(t,a,o,sg);auto rb=row_size(t,k);if(!rows || rows>UINT32_MAX)throw std::invalid_argument("row count");
  unique({w,x,y});check(d,w,product(rows,rb));check(d,x,product(k,2));check(d,y,product(rows,2));
  Multiply op;op.type=t;op.activation=a;op.output_type=o;op.columns=k;op.row_bytes=rb;op.rows=rows;op.experts=1;op.count=1;op.span=rows;op.subgroup=sg;op.routed=false;
  op.diagnostic=fp32!=0;
  std::vector ids{w,x,y};if(fp32){unique({w,x,y,fp32});check(d,fp32,product(rows,4));ids.push_back(fp32);}return d.compute(op,ids,{});
}
ownrt::Event routed_gemv(ownrt::Device& d,Type t,ownrt::Allocation w,ownrt::Allocation x,ownrt::Allocation y,ownrt::Allocation r,ownrt::Allocation status,uint32_t experts,uint32_t rows,size_t k,uint32_t count,uint32_t span,Type a,Type o,unsigned sg,ownrt::Allocation fp32) {
  types(t,a,o,sg);auto rb=row_size(t,k);if(!experts || !rows || !count || !span || span>rows)throw std::invalid_argument("route geometry");
  unique({w,x,y,r,status});check(d,w,product(product(experts,rows),rb));check(d,x,product(product(count,k),2));check(d,y,product(product(count,span),2));check(d,r,product(count,sizeof(Route)));check(d,status,product(count,4));product(product(count,span),32);
  Multiply op;op.type=t;op.activation=a;op.output_type=o;op.columns=k;op.row_bytes=rb;op.rows=rows;op.experts=experts;op.count=count;op.span=span;op.subgroup=sg;op.routed=true;
  op.diagnostic=fp32!=0;
  std::vector ids{w,x,y,r,status};if(fp32){unique({w,x,y,r,status,fp32});check(d,fp32,product(product(count,span),4));ids.push_back(fp32);}return d.compute(op,ids,{});
}
}
