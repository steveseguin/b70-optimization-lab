#pragma once
#ifdef OWN_RT_HOST_ONLY
#error P208 requires actual SYCL compilation, not HOST_ONLY fallback
#endif
#include "selected_headers.hpp"
#include <array>
namespace p208 {
inline void require(bool value,const char* message){if(!value)throw std::invalid_argument(message);}
template<unsigned Rows> class NativePairKernel;
template<unsigned Rows> struct PairOperation final:ownrt::SyclOperation {
  static_assert(Rows==10240 || Rows==6144);
  sycl::event submit(sycl::queue& q,std::span<void*const> p,
                     const std::vector<sycl::event>& deps)const override {
    require(deps.empty(),"p208 standalone prepared fixture requires empty external dependencies");
    // Prepared callbacks do not retain issue-time dependency vectors. This
    // standalone fixture therefore explicitly requires the selected ordered
    // queue; it does not infer an Engine-wide dependency/cache admission.
    require(q.has_property<sycl::property::queue::in_order>(),"p208 requires ordered native queue");
    const auto* weights=static_cast<const uint8_t*>(p[0]);
    const auto* x0=static_cast<const uint16_t*>(p[1]);
    const auto* x1=static_cast<const uint16_t*>(p[2]);
    auto* y0=static_cast<uint16_t*>(p[3]);auto* y1=static_cast<uint16_t*>(p[4]);
    // Only pointer values survive preparation; neither this, span p nor a
    // reference to submit's locals appears in either stored capture.
    return ownrt::prepared_submit(q,[=](sycl::handler& h) {
      h.parallel_for<NativePairKernel<Rows>>(sycl::nd_range<1>(size_t(Rows)*32,32),
        packet26::checked([=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]] {
          auto sg=it.get_sub_group();unsigned lane=sg.get_local_linear_id();
          size_t row=it.get_group_linear_id();const auto* w=weights+row*3380;
          float sums[2]{};
          for(unsigned tile=lane*8;tile<2560;tile+=256) {
            const float scale=iq3::bits_float(iq3::u32(w+2560+4*(tile/16)));
            #pragma unroll
            for(unsigned j=0;j<8;++j) {
              const float weight=scale*float(iq3::signed8(w[tile+j]));
              const float p0=weight*iq3::bits_float(uint32_t(x0[tile+j])<<16);
              const float p1=weight*iq3::bits_float(uint32_t(x1[tile+j])<<16);
              sums[0]=sums[0]+p0;sums[1]=sums[1]+p1;
            }
          }
          // Frozen p33 tree; do not substitute a generic subgroup reduction.
          for(unsigned r=0;r<2;++r) {
            for(unsigned width=1;width<32;width*=2) {
              float rhs=sycl::select_from_group(sg,sums[r],(lane+width)%32);
              if(lane%(2*width)==0)sums[r]=sums[r]+rhs;
            }
            if(lane==0)(r?y1:y0)[row]=iq3::bf16_bits(sums[r]);
          }
        }));
    });
  }
};
inline integrated::Launch paired_projection(ownrt::Device& d,const integrated::Matrix& a,
                                             const integrated::Matrix& b,unsigned variant) {
  require(a.type==iq3::Type::Q6_K && b.type==a.type && a.w==b.w && a.rows==b.rows && a.columns==2560 && b.columns==2560 && variant==6 && (a.rows==10240 || a.rows==6144),"p208 Q6 K2560 variant6 shape only");
  require(a.count==1 && b.count==1 && a.experts==1 && b.experts==1 && !a.routes && !b.routes && !a.fp32 && !b.fp32 && a.activation==iq3::Type::BF16 && b.activation==iq3::Type::BF16 && a.output_type==iq3::Type::BF16 && b.output_type==iq3::Type::BF16,"p208 pair matrix identity");
  require(integrated::arithmetic::row_bytes(a.type,2560,variant)==3380,"p208 expanded stride");
  std::array<ownrt::Allocation,7> ids{a.w,a.x,b.x,a.y,b.y,a.workspace,b.workspace};
  const size_t needed[]{a.rows*3380,5120,5120,a.rows*2,a.rows*2,4,4};
  for(size_t i=0;i<ids.size();++i) {
    const auto& r=d.arena.row(ids[i]);require(r.live && r.memory==ownrt::Memory::device && r.bytes>=needed[i] && uintptr_t(r.pointer)%(i>=1&&i<=4?2:4)==0,"p208 binding extent/alignment");
    for(size_t j=0;j<i;++j)if(i>=3 || j>=3)require(ids[i]!=ids[j],"p208 writable alias");
  }
  require(a.x!=b.x && a.w!=a.x && a.w!=b.x,"p208 distinct weight and row allocations");
  ownrt::Event event;
  if(a.rows==10240){PairOperation<10240> op;event=d.compute(op,ids,{});}
  else {PairOperation<6144> op;event=d.compute(op,ids,{});}
  return {event,event,1};
}
} // namespace p208
