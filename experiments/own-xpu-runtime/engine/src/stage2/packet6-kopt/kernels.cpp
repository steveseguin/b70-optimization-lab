#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
#ifndef OWN_RT_HOST_ONLY
#include "stage2/packet194-expert-diet-engine/prepared_submission.hpp"
#endif
#include "stage2/packet6-kopt/kernels.hpp"
#include "stage2/packet6-kopt/reference.hpp"
#include "stage2/packet194-expert-diet-engine/prefill_switches.hpp"
#include "stage1/packet3-prep/src/sycl_operation.hpp"
#include <algorithm>
#include <array>
#include <limits>
#include <set>
#include <sstream>

namespace iq3::kopt {
namespace {
constexpr size_t rows_per_group=4;
std::string properties="null";
size_t mul(size_t a,size_t b) {
  if(b && a>std::numeric_limits<size_t>::max()/b)throw std::overflow_error("kopt extent");
  return a*b;
}
void check(ownrt::Device& d,ownrt::Allocation id,size_t bytes) {
  auto& r=d.arena.row(id);
  if(!bytes || !r.live || r.memory!=ownrt::Memory::device || bytes>r.bytes)
    throw std::invalid_argument("kopt device binding extent");
  if(reinterpret_cast<uintptr_t>(r.pointer)%16)throw std::invalid_argument("kopt allocation must be aligned16");
}
void geometry(Type t,Type a,Type o,size_t rows,size_t k,unsigned sg) {
  auto l=layout(t);
  if(!l.elements || !rows || rows>UINT32_MAX || !k || k>16384 || k%l.elements ||
     (!(a==Type::F32 && o==Type::F32) && ((a!=Type::BF16 && a!=Type::F16) || (o!=Type::BF16 && o!=Type::F16))) || (sg!=16 && sg!=32))
    throw std::invalid_argument("kopt geometry/type/subgroup");
}
struct Descriptor {
  Type type,activation,output;size_t rows,k,rb,first_group,groups;
  uint32_t experts,count,span;bool routed;
  unsigned w,x,y,r,status,fp32;bool diagnostic;
  // Dense token rows (gemv_tokens): slots are tokens, ordered row-major so tokens sharing a weight row run together.
  bool row_major=false;
};
// A fully aligned interior is read exactly once in 16-byte chunks per row.
// Edges are scalar and bounded to that row. No block-start alignment fiction.
template<unsigned SG> inline void stage_row(const uint8_t* src,uint8_t* dst,size_t n,unsigned lane) {
  size_t prefix=(16-(reinterpret_cast<uintptr_t>(src)&15))&15;
  prefix=prefix<n?prefix:n;
  for(size_t i=lane;i<prefix;i+=SG)dst[i]=src[i];
  size_t vectors=(n-prefix)/16;
  auto aligned=reinterpret_cast<const sycl::vec<uint32_t,4>*>(src+prefix);
  for(size_t j=lane;j<vectors;j+=SG) {
    auto bytes=aligned[j].template as<sycl::vec<uint8_t,16>>();
    for(unsigned i=0;i<16;++i)dst[prefix+j*16+i]=bytes[i];
  }
  for(size_t i=prefix+vectors*16+lane;i<n;i+=SG)dst[i]=src[i];
}
template<Type T,unsigned SG> inline float dot(const uint8_t* row,const uint16_t* x,Type a,size_t k,unsigned lane) {
  if constexpr(layout(T).elements!=1)return lane_dot<T>(row,x,a,k,lane,SG);
  else {
    // Raw formats bypass SLM; consecutive lanes consume consecutive 16/32 B.
    float acc=0;
    // F32 activations with 16-byte aligned row and input: every full chunk below takes the vector branch (its
    // alignment test is the same for all chunks), so run those chunks as a fixed-trip unrolled body with a 32-bit
    // index, then the ragged chunk exactly as below. Same values, same order.
    if(a==Type::F32 && reinterpret_cast<uintptr_t>(row)%16==0 && reinterpret_cast<uintptr_t>(x)%16==0) {
      const float* xf=reinterpret_cast<const float*>(x);const uint32_t k32=uint32_t(k);uint32_t base=lane*8u;
      #pragma unroll 2
      for(;base+8u<=k32;base+=SG*8u) {
        float values[8],wide[8];
        #pragma unroll
        for(unsigned j=0;j<8;++j)wide[j]=xf[base+j];
        if constexpr(T==Type::F32) {
          auto w=reinterpret_cast<const sycl::vec<uint32_t,4>*>(row+size_t(base)*4);
          auto lo=w[0],hi=w[1];
          #pragma unroll
          for(unsigned j=0;j<4;++j){values[j]=bits_float(lo[j]);values[j+4]=bits_float(hi[j]);}
        } else {
          auto w=*reinterpret_cast<const sycl::vec<uint16_t,8>*>(row+size_t(base)*2);
          #pragma unroll
          for(unsigned j=0;j<8;++j) {
            // BF16: no explicit NaN-quieting here. Finite weights are bit-identical; a NaN weight's product below is the
            // same quiet NaN either way (the multiply quiets it). HC low+inject microbench, cold: 24.9 -> 23.1 us.
            if constexpr(T==Type::F16)values[j]=half(w[j]);
            else values[j]=bits_float(uint32_t(w[j])<<16);
          }
        }
        #pragma unroll
        for(unsigned j=0;j<8;++j){float product=values[j]*wide[j];acc=acc+product;}
      }
      if(base<k32) {
        float values[8],wide[8];
        for(unsigned j=0;base+j<k32;++j){values[j]=element(T,row,base+j);wide[j]=xf[base+j];}
        for(unsigned j=0;base+j<k32;++j){float product=values[j]*wide[j];acc=acc+product;}
      }
      return acc;
    }
    for(size_t base=size_t(lane)*8;base<k;base+=SG*8) {
      float values[8];uint16_t inputs[8];float wide[8];const bool f32=a==Type::F32;
      if(base+8<=k && reinterpret_cast<uintptr_t>(row+base*layout(T).bytes)%16==0 &&
         reinterpret_cast<uintptr_t>(x+base)%16==0) {
        if(f32){for(unsigned j=0;j<8;++j)wide[j]=reinterpret_cast<const float*>(x)[base+j];}
        else{auto xv=*reinterpret_cast<const sycl::vec<uint16_t,8>*>(x+base);
        for(unsigned j=0;j<8;++j)inputs[j]=xv[j];}
        if constexpr(T==Type::F32) {
          auto w=reinterpret_cast<const sycl::vec<uint32_t,4>*>(row+base*4);
          auto lo=w[0],hi=w[1];
          for(unsigned j=0;j<4;++j){values[j]=bits_float(lo[j]);values[j+4]=bits_float(hi[j]);}
        } else {
          auto w=*reinterpret_cast<const sycl::vec<uint16_t,8>*>(row+base*2);
          for(unsigned j=0;j<8;++j) {
            if constexpr(T==Type::F16)values[j]=half(w[j]);
            else {auto bits=uint32_t(w[j])<<16;if((bits&0x7fffffff)>0x7f800000)bits|=0x400000;values[j]=bits_float(bits);}
          }
        }
      } else for(unsigned j=0;j<8 && base+j<k;++j){values[j]=element(T,row,base+j);if(f32)wide[j]=reinterpret_cast<const float*>(x)[base+j];else inputs[j]=x[base+j];}
      for(unsigned j=0;j<8 && base+j<k;++j) {
        float input=f32?wide[j]:a==Type::BF16?bits_float(uint32_t(inputs[j])<<16):half(inputs[j]);
        float product=values[j]*input;acc=acc+product;
      }
    }
    return acc;
  }
}
template<unsigned SG> float dispatch_dot(Type t,const uint8_t* row,const uint16_t* x,Type a,size_t k,unsigned lane) {
#define KOPT_CASE(T) case Type::T:return dot<Type::T,SG>(row,x,a,k,lane)
  switch(t) {
    KOPT_CASE(F32);KOPT_CASE(F16);KOPT_CASE(BF16);KOPT_CASE(Q8_0);KOPT_CASE(Q6_K);
    KOPT_CASE(Q3_K);KOPT_CASE(IQ3_XXS);KOPT_CASE(IQ2_S);KOPT_CASE(IQ3_S);KOPT_CASE(IQ4_NL);
  }
#undef KOPT_CASE
  return bits_float(0x7fc00000);
}
struct Multiply:ownrt::SyclOperation {
  std::array<Descriptor,4> desc{};unsigned matrices=0,subgroup=16;size_t groups=0,local_stride=16;
  template<Type T,unsigned SG> sycl::event run(sycl::queue& q,std::span<void* const> p,const std::vector<sycl::event>& deps) const {
    // Several independent matrices of one type share a launch (sibling fusion): work-groups are partitioned by each
    // descriptor's first_group, and every row runs the unchanged single-matrix code with its own descriptor.
    if(matrices<1||matrices>desc.size())throw std::invalid_argument("kopt matrix count");
    for(unsigned j=1;j<matrices;++j)if(desc[j].type!=desc[0].type||desc[j].activation!=desc[0].activation||desc[j].output!=desc[0].output||desc[j].routed)throw std::invalid_argument("kopt fused matrices must share type/activation/output and be dense");
    auto descriptors=desc;const unsigned count=matrices;auto ng=groups,stride=local_stride;
    std::array<void*,8> pointers{};if(p.size()>pointers.size())throw std::invalid_argument("packet26 capture extent");std::copy(p.begin(),p.end(),pointers.begin());
    return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(sycl::range<1>(ng*SG*rows_per_group),sycl::range<1>(SG*rows_per_group))](sycl::handler& h) {
      sycl::local_accessor<uint8_t,1> storage(stride*rows_per_group,h);
      h.parallel_for(p35_range0,
        packet26::checked([=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(SG)]] {
          auto group=it.get_group_linear_id();auto sg=it.get_sub_group();unsigned lane=sg.get_local_linear_id();
          unsigned row_in_group=sg.get_group_linear_id();
          auto d=descriptors[0];for(unsigned j=1;j<count;++j)if(group>=descriptors[j].first_group)d=descriptors[j];
          size_t logical=(group-d.first_group)*rows_per_group+row_in_group;
          size_t slot=d.row_major?logical%d.count:logical/d.span,row=d.row_major?logical/d.count:logical%d.span;bool in_range=d.row_major?row<d.span:slot<d.count;
          Route r{0,0,uint32_t(d.rows)};
          if(d.routed && in_range)r=static_cast<const Route*>(pointers[d.r])[slot];
          bool valid=in_range && valid_route(r,d.experts,d.rows,d.span),active=valid && row<r.row_count;
          if(d.routed && in_range && row==0 && lane==0)static_cast<uint32_t*>(pointers[d.status])[slot]=valid?0:1;
          const uint8_t* source=nullptr;const uint16_t* x=nullptr;
          auto local=storage.template get_multi_ptr<sycl::access::decorated::no>().get()+row_in_group*stride;
          if(active) {
            source=static_cast<const uint8_t*>(pointers[d.w])+(size_t(r.expert_id)*d.rows+r.row_begin+row)*d.rb;
            x=d.activation==Type::F32?reinterpret_cast<const uint16_t*>(static_cast<const float*>(pointers[d.x])+slot*d.k):static_cast<const uint16_t*>(pointers[d.x])+slot*d.k;
            if(layout(T).elements!=1)stage_row<SG>(source,local,d.rb,lane);
          }
          // All four rows reach the sole workgroup barrier, including invalid/tail rows.
          it.barrier(sycl::access::fence_space::local_space);
          float sum=0;
          if(active)sum=dot<T,SG>(layout(T).elements==1?source:local,x,d.activation,d.k,lane);
          // Explicit adjacent-pair tree. Every lane participates in each shuffle;
          // only the left roots add. Never use implementation-chosen reduce().
          for(unsigned width=1;width<SG;width*=2) {
            float rhs=sycl::select_from_group(sg,sum,(lane+width)%SG);
            if(lane%(2*width)==0)sum=sum+rhs;
          }
          if(lane==0 && in_range) {
            float value=active?sum:bits_float(0x7fc00000);
            const size_t out=slot*d.span+row; // == logical for the slot-major mapping
            if(d.output==Type::F32)static_cast<float*>(pointers[d.y])[out]=value;else static_cast<uint16_t*>(pointers[d.y])[out]=output_bits(value,d.output);
            if(d.diagnostic)static_cast<float*>(pointers[d.fp32])[out]=value;
          }
        }));
    });
  }
  sycl::event submit(sycl::queue& q,std::span<void* const> p,const std::vector<sycl::event>& deps) const override {
    auto dev=q.get_device();auto supported=dev.get_info<sycl::info::device::sub_group_sizes>();
    auto local=dev.get_info<sycl::info::device::local_mem_size>();auto wg=dev.get_info<sycl::info::device::max_work_group_size>();
    if(std::find(supported.begin(),supported.end(),subgroup)==supported.end() || local_stride*rows_per_group>local || subgroup*rows_per_group>wg)
      throw std::invalid_argument("kopt unsupported device subgroup/SLM/workgroup");
    std::ostringstream info;info<<"{\"max_compute_units\":"<<dev.get_info<sycl::info::device::max_compute_units>()
      <<",\"local_mem_bytes\":"<<local<<",\"max_work_group_size\":"<<wg<<",\"subgroup_sizes\":[";
    for(size_t i=0;i<supported.size();++i)info<<(i?",":"")<<supported[i];
    properties=info.str()+"],\"occupancy\":\"not measured\"}";
    switch(desc[0].type){
#define P26_CASE(T) case Type::T:return subgroup==16?run<Type::T,16>(q,p,deps):run<Type::T,32>(q,p,deps)
P26_CASE(F32);P26_CASE(F16);P26_CASE(BF16);P26_CASE(Q8_0);P26_CASE(Q6_K);P26_CASE(Q3_K);P26_CASE(IQ3_XXS);P26_CASE(IQ2_S);P26_CASE(IQ3_S);P26_CASE(IQ4_NL);
#undef P26_CASE
}throw std::invalid_argument("type");
  }
};
// Dense token rows with weight reuse: one subgroup owns one weight row and a tile of R token rows. Each weight value
// is decoded once and applied to every token of the tile; each token keeps Multiply's single-row arithmetic exactly
// (lane k-ranges, decode, product then add, the adjacent-pair subgroup tree). F32 activations only.
template<unsigned R> struct MultiplyRows:ownrt::SyclOperation {
  Descriptor desc{};unsigned subgroup=16;size_t groups=0,local_stride=16;
  template<Type T,unsigned SG> sycl::event run(sycl::queue& q,std::span<void* const> p,const std::vector<sycl::event>& deps) const {
    auto d=desc;auto ng=groups,stride=local_stride;
    std::array<void*,8> pointers{};if(p.size()>pointers.size())throw std::invalid_argument("kopt rows capture extent");std::copy(p.begin(),p.end(),pointers.begin());
    return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(sycl::range<1>(ng*SG*rows_per_group),sycl::range<1>(SG*rows_per_group))](sycl::handler& h) {
      sycl::local_accessor<uint8_t,1> storage(stride*rows_per_group,h);
      h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(SG)]] {
        auto sg=it.get_sub_group();unsigned lane=sg.get_local_linear_id();unsigned row_in_group=sg.get_group_linear_id();
        const size_t tiles=(d.count+R-1)/R,logical=it.get_group_linear_id()*rows_per_group+row_in_group;
        const size_t row=logical/tiles,first=(logical%tiles)*R;const bool active=row<d.span;
        const unsigned n=active?unsigned(std::min<size_t>(R,d.count-first)):0;
        const uint8_t* source=nullptr;auto local=storage.template get_multi_ptr<sycl::access::decorated::no>().get()+row_in_group*stride;
        if(active){source=static_cast<const uint8_t*>(pointers[d.w])+row*d.rb;if(layout(T).elements!=1)stage_row<SG>(source,local,d.rb,lane);}
        it.barrier(sycl::access::fence_space::local_space);
        const float* x=static_cast<const float*>(pointers[d.x])+first*d.k;
        float acc[R];for(unsigned r=0;r<R;++r)acc[r]=0;
        if(active) {
          if constexpr(layout(T).elements==1) {
            for(size_t base=size_t(lane)*8;base<d.k;base+=SG*8) {
              float values[8];
              if(base+8<=d.k && reinterpret_cast<uintptr_t>(source+base*layout(T).bytes)%16==0) {
                if constexpr(T==Type::F32) {
                  auto w=reinterpret_cast<const sycl::vec<uint32_t,4>*>(source+base*4);auto lo=w[0],hi=w[1];
                  for(unsigned j=0;j<4;++j){values[j]=bits_float(lo[j]);values[j+4]=bits_float(hi[j]);}
                } else {
                  auto w=*reinterpret_cast<const sycl::vec<uint16_t,8>*>(source+base*2);
                  for(unsigned j=0;j<8;++j) {
                    if constexpr(T==Type::F16)values[j]=half(w[j]);
                    else {auto bits=uint32_t(w[j])<<16;if((bits&0x7fffffff)>0x7f800000)bits|=0x400000;values[j]=bits_float(bits);}
                  }
                }
              } else for(unsigned j=0;j<8 && base+j<d.k;++j)values[j]=element(T,source,base+j);
              for(unsigned r=0;r<R;++r)if(r<n)for(unsigned j=0;j<8 && base+j<d.k;++j){float input=x[r*d.k+base+j];float product=values[j]*input;acc[r]=acc[r]+product;}
            }
          } else {
            for(size_t k=size_t(lane)*8;k<d.k;k+=size_t(SG)*8) {
              float values[8];
              if(k+8<=d.k)decode8<T>(local,k,values);else for(size_t j=0;j<d.k-k;++j)values[j]=element(T,local,k+j);
              for(unsigned r=0;r<R;++r)if(r<n)for(unsigned j=0;j<8 && k+j<d.k;++j){float input=x[r*d.k+k+j];float product=values[j]*input;acc[r]=acc[r]+product;}
            }
          }
        }
        for(unsigned r=0;r<R;++r){float sum=acc[r];
          for(unsigned width=1;width<SG;width*=2){float rhs=sycl::select_from_group(sg,sum,(lane+width)%SG);if(lane%(2*width)==0)sum=sum+rhs;}
          if(lane==0&&r<n)static_cast<float*>(pointers[d.y])[(first+r)*d.span+row]=sum;}
      }));
    });
  }
  sycl::event submit(sycl::queue& q,std::span<void* const> p,const std::vector<sycl::event>& deps) const override {
    switch(desc.type){
#define ROWS_CASE(T) case Type::T:return subgroup==16?run<Type::T,16>(q,p,deps):run<Type::T,32>(q,p,deps)
ROWS_CASE(F32);ROWS_CASE(F16);ROWS_CASE(BF16);ROWS_CASE(Q8_0);ROWS_CASE(Q6_K);
#undef ROWS_CASE
    default:break;}
    throw std::invalid_argument("kopt token rows: dense F32/F16/BF16/Q8_0/Q6_K only");
  }
};
// Dense token rows, tiled: a work-group of 4 subgroups owns 4*RowsPerSubgroup weight rows and up to Tokens token rows.
// Each 256-column slice of the tokens' F32 activations is staged once in local memory (transposed, so the 32 lanes of a
// subgroup read 32 consecutive floats) and reused by all the work-group's weight rows; each weight value is decoded
// once and applied to every token. Tokens beyond the chunk read zeros and are never written. Every real output (row,
// token) keeps Multiply's single-row arithmetic exactly: lane l owns columns l*8+256*i+j (SG=32), product then add in
// that order, then the adjacent-pair subgroup tree.
template<unsigned RowsPerSubgroup,unsigned Tokens> struct MultiplyTiled:ownrt::SyclOperation {
  static constexpr unsigned SG=32,Subgroups=4,Rows=RowsPerSubgroup*Subgroups,Step=SG*8;
  Descriptor desc{};
  template<Type T> static inline void values8(const uint8_t* source,size_t base,size_t k,float* values) {
    if constexpr(layout(T).elements==1) {
      if(base+8<=k && reinterpret_cast<uintptr_t>(source+base*layout(T).bytes)%16==0) {
        if constexpr(T==Type::F32) {
          auto v=reinterpret_cast<const sycl::vec<uint32_t,4>*>(source+base*4);auto lo=v[0],hi=v[1];
          for(unsigned j=0;j<4;++j){values[j]=bits_float(lo[j]);values[j+4]=bits_float(hi[j]);}
        } else {
          auto v=*reinterpret_cast<const sycl::vec<uint16_t,8>*>(source+base*2);
          for(unsigned j=0;j<8;++j) {
            if constexpr(T==Type::F16)values[j]=half(v[j]);
            else {auto bits=uint32_t(v[j])<<16;if((bits&0x7fffffff)>0x7f800000)bits|=0x400000;values[j]=bits_float(bits);}
          }
        }
      } else for(unsigned j=0;j<8 && base+j<k;++j)values[j]=element(T,source,base+j);
    } else {
      if(base+8<=k)decode8<T>(source,base,values);else for(size_t j=0;j<k-base;++j)values[j]=element(T,source,base+j);
    }
  }
  template<Type T> sycl::event run(sycl::queue& q,std::span<void* const> p,const std::vector<sycl::event>& deps) const {
    auto d=desc;std::array<void*,8> pointers{};if(p.size()>pointers.size())throw std::invalid_argument("kopt tiled capture extent");std::copy(p.begin(),p.end(),pointers.begin());
    const size_t groups=(d.span+Rows-1)/Rows;
    return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(sycl::range<1>(groups*SG*Subgroups),sycl::range<1>(SG*Subgroups))](sycl::handler& h) {
      sycl::local_accessor<float,1> xs(Tokens*Step,h);
      h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
        auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id(),sub=sg.get_group_linear_id(),local=it.get_local_linear_id();
        const size_t row0=it.get_group_linear_id()*Rows+sub*RowsPerSubgroup;const size_t n=std::min<size_t>(Tokens,d.count),k=d.k;
        const float* x=static_cast<const float*>(pointers[d.x]);const uint8_t* w=static_cast<const uint8_t*>(pointers[d.w]);
        float acc[RowsPerSubgroup][Tokens];
        #pragma unroll
        for(unsigned r=0;r<RowsPerSubgroup;++r){
          #pragma unroll
          for(unsigned t=0;t<Tokens;++t)acc[r][t]=0;}
        for(size_t step=0;step<k;step+=Step) {
          it.barrier(sycl::access::fence_space::local_space);
          for(unsigned i=local;i<Tokens*Step;i+=SG*Subgroups){const unsigned t=i/Step,c=i%Step;xs[t*Step+(c%8)*SG+c/8]=(t<n&&step+c<k)?x[t*k+step+c]:0.f;}
          it.barrier(sycl::access::fence_space::local_space);
          const size_t base=step+size_t(lane)*8;
          if(base>=k)continue;
          #pragma unroll
          for(unsigned r=0;r<RowsPerSubgroup;++r) {
            const size_t row=row0+r;if(row>=d.span)continue;
            float values[8];values8<T>(w+row*d.rb,base,k,values);
            if(base+8<=k) {
              #pragma unroll
              for(unsigned t=0;t<Tokens;++t){
                #pragma unroll
                for(unsigned j=0;j<8;++j){float input=xs[t*Step+j*SG+lane];float product=values[j]*input;acc[r][t]=acc[r][t]+product;}}
            } else {
              #pragma unroll
              for(unsigned t=0;t<Tokens;++t)for(unsigned j=0;j<8 && base+j<k;++j){float input=xs[t*Step+j*SG+lane];float product=values[j]*input;acc[r][t]=acc[r][t]+product;}
            }
          }
        }
        #pragma unroll
        for(unsigned r=0;r<RowsPerSubgroup;++r){
          #pragma unroll
          for(unsigned t=0;t<Tokens;++t){float sum=acc[r][t];
            for(unsigned width=1;width<SG;width*=2){float rhs=sycl::select_from_group(sg,sum,(lane+width)%SG);if(lane%(2*width)==0)sum=sum+rhs;}
            if(lane==0&&t<n&&row0+r<d.span)static_cast<float*>(pointers[d.y])[t*d.span+row0+r]=sum;}}
      }));
    });
  }
  sycl::event submit(sycl::queue& q,std::span<void* const> p,const std::vector<sycl::event>& deps) const override {
    switch(desc.type){
#define TILED_CASE(T) case Type::T:return run<Type::T>(q,p,deps)
TILED_CASE(F32);TILED_CASE(F16);TILED_CASE(BF16);TILED_CASE(Q8_0);TILED_CASE(Q6_K);
#undef TILED_CASE
    default:break;}
    throw std::invalid_argument("kopt tiled token rows: dense F32/F16/BF16/Q8_0/Q6_K only");
  }
};
// Several rows per subgroup (F32 activations, decode8 formats): one subgroup owns R consecutive rows of one slot, decodes
// each row straight from global memory (no local staging, no barrier) and shares each 8-column activation chunk across
// its rows. Every row keeps Multiply's single-row arithmetic exactly: lane l owns columns l*8+SG*8*i, the same decode8
// values, product then add in that order, the same adjacent-pair subgroup tree, and NaN for inactive rows.
template<unsigned R> struct MultiplyBlockRows:ownrt::SyclOperation {
  static constexpr unsigned Subgroups=4;
  Descriptor desc{};unsigned subgroup=32;
  template<Type T,unsigned SG> sycl::event run(sycl::queue& q,std::span<void* const> p,const std::vector<sycl::event>& deps) const {
    auto d=desc;std::array<void*,8> pointers{};if(p.size()>pointers.size())throw std::invalid_argument("kopt block-rows capture extent");std::copy(p.begin(),p.end(),pointers.begin());
    const size_t blocks=(d.span+R-1)/R,total=blocks*d.count,groups=(total+Subgroups-1)/Subgroups;
    return ownrt::prepared_submit(q,[=,p35_range0=sycl::nd_range<1>(sycl::range<1>(groups*SG*Subgroups),sycl::range<1>(SG*Subgroups))](sycl::handler& h) {
      h.parallel_for(p35_range0,packet26::checked([=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(SG)]] {
        auto sg=it.get_sub_group();const unsigned lane=sg.get_local_linear_id();
        const size_t logical=it.get_group_linear_id()*Subgroups+sg.get_group_linear_id();if(logical>=total)return;
        const size_t slot=logical/blocks,first=(logical%blocks)*R;
        Route r{0,0,uint32_t(d.rows)};if(d.routed)r=static_cast<const Route*>(pointers[d.r])[slot];
        const bool valid=valid_route(r,d.experts,d.rows,d.span);
        if(d.routed&&first==0&&lane==0)static_cast<uint32_t*>(pointers[d.status])[slot]=valid?0:1;
        const float* x=static_cast<const float*>(pointers[d.x])+slot*d.k;const uint8_t* w=static_cast<const uint8_t*>(pointers[d.w]);
        float acc[R];const uint8_t* rows[R];bool live[R];
        #pragma unroll
        for(unsigned i=0;i<R;++i){acc[i]=0;const size_t row=first+i;live[i]=valid&&row<d.span&&row<r.row_count;
          rows[i]=live[i]?w+(size_t(r.expert_id)*d.rows+r.row_begin+row)*d.rb:w;}
        // Lean loop, same arithmetic: row pointers hoisted, a 32-bit column index, and a fixed-trip unrolled body for
        // every full 8-column chunk; the one ragged chunk per lane (if any) keeps the per-element checks.
        const uint32_t k32=uint32_t(d.k);uint32_t k=lane*8u;
        for(;k+8u<=k32;k+=SG*8u) {
          float input[8];
          #pragma unroll
          for(unsigned j=0;j<8;++j)input[j]=x[k+j];
          #pragma unroll
          for(unsigned i=0;i<R;++i) {
            if(!live[i])continue;float values[8];decode8<T>(rows[i],k,values);
            #pragma unroll
            for(unsigned j=0;j<8;++j){float product=values[j]*input[j];acc[i]=acc[i]+product;}
          }
        }
        if(k<k32) {
          float input[8];for(unsigned j=0;k+j<k32;++j)input[j]=x[k+j];
          #pragma unroll
          for(unsigned i=0;i<R;++i) {
            if(!live[i])continue;float values[8];for(uint32_t j=0;k+j<k32;++j)values[j]=element(T,rows[i],k+j);
            for(unsigned j=0;k+j<k32;++j){float product=values[j]*input[j];acc[i]=acc[i]+product;}
          }
        }
        #pragma unroll
        for(unsigned i=0;i<R;++i) {
          float sum=acc[i];
          for(unsigned width=1;width<SG;width*=2){float rhs=sycl::select_from_group(sg,sum,(lane+width)%SG);if(lane%(2*width)==0)sum=sum+rhs;}
          const size_t row=first+i;
          if(lane==0&&row<d.span)static_cast<float*>(pointers[d.y])[slot*d.span+row]=valid&&row<r.row_count?sum:bits_float(0x7fc00000);
        }
      }));
    });
  }
  sycl::event submit(sycl::queue& q,std::span<void* const> p,const std::vector<sycl::event>& deps) const override {
    switch(desc.type){
#define BLOCK_CASE(T) case Type::T:return run<Type::T,32>(q,p,deps)
BLOCK_CASE(Q8_0);BLOCK_CASE(Q6_K);BLOCK_CASE(IQ2_S);BLOCK_CASE(IQ3_S);BLOCK_CASE(IQ4_NL);
#undef BLOCK_CASE
    default:break;}
    throw std::invalid_argument("kopt block rows: decode8 formats only");
  }
};
inline bool block_rows(){static const bool on=[]{const char* e=std::getenv("OWNRT_KOPT_BLOCK_ROWS");return !e||e[0]!='0';}();return on;}
Descriptor bind_matrix(ownrt::Device& d,Multiply& op,std::vector<ownrt::Allocation>& ids,Matrix m,
                uint32_t experts,uint32_t count,uint32_t span,ownrt::Allocation r=0,ownrt::Allocation status=0) {
  geometry(m.type,m.activation,m.output_type,m.rows,m.columns,op.subgroup);
  if(!experts || !count || !span || span>m.rows)throw std::invalid_argument("kopt routes");
  auto l=layout(m.type);size_t rb=mul(m.columns/l.elements,l.bytes);
  Descriptor v{m.type,m.activation,m.output_type,m.rows,m.columns,rb,op.groups,(mul(count,span)+3)/4,experts,count,span,r!=0,0,0,0,0,0,0,m.fp32!=0};
  auto add=[&](ownrt::Allocation id,size_t bytes){check(d,id,bytes);unsigned index=ids.size();ids.push_back(id);return index;};
  const size_t ab=m.activation==Type::F32?4:2;
  // A shared read-only input (fused siblings) binds once; outputs and weights must stay distinct.
  auto input=[&](ownrt::Allocation id,size_t bytes){for(unsigned i=0;i<ids.size();++i)if(ids[i]==id){check(d,id,bytes);return i;}return add(id,bytes);};
  v.w=add(m.w,mul(mul(experts,m.rows),rb));v.x=input(m.x,mul(mul(count,m.columns),ab));v.y=add(m.y,mul(mul(count,span),ab));
  if(r){v.r=add(r,mul(count,sizeof(Route)));v.status=add(status,mul(count,4));}
  if(m.fp32)v.fp32=add(m.fp32,mul(mul(count,span),4));
  if(l.elements!=1)op.local_stride=std::max(op.local_stride,(rb+15)/16*16);
  op.groups+=v.groups;return v;
}
ownrt::Event finish(ownrt::Device& d,Multiply& op,const std::vector<ownrt::Allocation>& ids) {
  if(std::set<ownrt::Allocation>(ids.begin(),ids.end()).size()!=ids.size())throw std::invalid_argument("kopt aliased bindings");
  mul(mul(op.groups,op.subgroup),rows_per_group);
  return d.compute(op,ids,{});
}
}
std::string device_properties(){return properties;}
ownrt::Event gemv(ownrt::Device& d,Type t,ownrt::Allocation w,ownrt::Allocation x,ownrt::Allocation y,size_t rows,size_t k,Type a,Type o,unsigned sg,ownrt::Allocation fp32) {
  Multiply op;op.subgroup=sg;op.matrices=1;std::vector<ownrt::Allocation> ids;
  op.desc[0]=bind_matrix(d,op,ids,{t,w,x,y,rows,k,a,o,fp32},1,1,rows);return finish(d,op,ids);
}
ownrt::Event gemv_tokens(ownrt::Device& d,Type t,ownrt::Allocation w,ownrt::Allocation x,ownrt::Allocation y,size_t rows,size_t k,uint32_t tokens,Type a,Type o,unsigned sg) {
  if(!tokens||tokens>64)throw std::invalid_argument("kopt token rows 1..64");
  Multiply op;op.subgroup=sg;op.matrices=1;std::vector<ownrt::Allocation> ids;
  op.desc[0]=bind_matrix(d,op,ids,{t,w,x,y,rows,k,a,o,0},1,tokens,rows);op.desc[0].row_major=true;
  if(a!=Type::F32||o!=Type::F32||tokens==1)return finish(d,op,ids);
  if(sg==32&&tokens<=16&&prefill_switches::tiled_rows()){
    // F32 token rows (up to 16): tiled kernel, activations staged once per 16 weight rows.
    if(std::set<ownrt::Allocation>(ids.begin(),ids.end()).size()!=ids.size())throw std::invalid_argument("kopt aliased bindings");
    MultiplyTiled<2,16> tiled;tiled.desc=op.desc[0];return d.compute(tiled,ids,{});
  }
  if(!prefill_switches::small_tile_rows())return finish(d,op,ids);
  // F32 token rows: weight-reuse kernel, 4 token rows per subgroup (small register tile, after vllm-xpu-kernels PR #22).
  constexpr unsigned R=4;MultiplyRows<R> rows_op;rows_op.desc=op.desc[0];rows_op.subgroup=sg;rows_op.local_stride=op.local_stride;
  rows_op.desc.first_group=0;rows_op.groups=(rows*((tokens+R-1)/R)+rows_per_group-1)/rows_per_group;
  if(std::set<ownrt::Allocation>(ids.begin(),ids.end()).size()!=ids.size())throw std::invalid_argument("kopt aliased bindings");
  return d.compute(rows_op,ids,{});
}
ownrt::Event routed_gemv(ownrt::Device& d,Type t,ownrt::Allocation w,ownrt::Allocation x,ownrt::Allocation y,ownrt::Allocation r,ownrt::Allocation status,uint32_t experts,uint32_t rows,size_t k,uint32_t count,uint32_t span,Type a,Type o,unsigned sg,ownrt::Allocation fp32) {
  if(!r || !status)throw std::invalid_argument("kopt routing handles required");
  Multiply op;op.subgroup=sg;op.matrices=1;std::vector<ownrt::Allocation> ids;
  op.desc[0]=bind_matrix(d,op,ids,{t,w,x,y,rows,k,a,o,fp32},experts,count,span,r,status);
  if(a==Type::F32&&o==Type::F32&&sg==32&&!fp32&&block_rows()&&(t==Type::IQ2_S||t==Type::IQ3_S||t==Type::Q8_0||t==Type::Q6_K)) { // not IQ4_NL: K=640 loses parallelism (153 vs ~107 us/layer)
    // F32 routed rows: 4 rows per subgroup, decoded from global memory (OWNRT_KOPT_BLOCK_ROWS=0 keeps one row each).
    if(std::set<ownrt::Allocation>(ids.begin(),ids.end()).size()!=ids.size())throw std::invalid_argument("kopt aliased bindings");
    // OWNRT_SMALLK_ROWS=1|2: rows per subgroup for K <= 640 (same per-row arithmetic); default 4.
    static const int small_k=[]{const char* e=std::getenv("OWNRT_SMALLK_ROWS");return e?std::atoi(e):4;}();
    if(k<=640&&small_k==2){MultiplyBlockRows<2> block;block.desc=op.desc[0];return d.compute(block,ids,{});}
    if(k<=640&&small_k==1){MultiplyBlockRows<1> block;block.desc=op.desc[0];return d.compute(block,ids,{});}
    MultiplyBlockRows<4> block;block.desc=op.desc[0];return d.compute(block,ids,{});
  }
  if(a==Type::F32&&o==Type::F32&&sg==32&&!fp32&&block_rows()&&t==Type::IQ4_NL) {
    // IQ4_NL (K=640): one row per subgroup straight from global memory with the word decoder (microbench 99 -> 73 us).
    if(std::set<ownrt::Allocation>(ids.begin(),ids.end()).size()!=ids.size())throw std::invalid_argument("kopt aliased bindings");
    // Rows per subgroup (same per-row arithmetic). With the lean loop 2 is fastest (engine profile, IQ4_NL down per
    // step: 1 row 1135 us, 2 rows 1049, 4 rows 1123); OWNRT_IQ4NL_ROWS=1|4 overrides.
    static const int rows=[]{const char* e=std::getenv("OWNRT_IQ4NL_ROWS");return e?std::atoi(e):2;}();
    if(rows==2){MultiplyBlockRows<2> block;block.desc=op.desc[0];return d.compute(block,ids,{});}
    if(rows==4){MultiplyBlockRows<4> block;block.desc=op.desc[0];return d.compute(block,ids,{});}
    MultiplyBlockRows<1> block;block.desc=op.desc[0];return d.compute(block,ids,{});
  }
  return finish(d,op,ids);
}
ownrt::Event fused_gemv(ownrt::Device& d,const std::vector<Matrix>& matrices,unsigned sg) {
  if(matrices.empty() || matrices.size()>4)throw std::invalid_argument("kopt fused matrix count1..4");
  Multiply op;op.subgroup=sg;op.matrices=matrices.size();std::vector<ownrt::Allocation> ids;
  for(size_t i=0;i<matrices.size();++i)op.desc[i]=bind_matrix(d,op,ids,matrices[i],1,1,matrices[i].rows);
  return finish(d,op,ids);
}
}
