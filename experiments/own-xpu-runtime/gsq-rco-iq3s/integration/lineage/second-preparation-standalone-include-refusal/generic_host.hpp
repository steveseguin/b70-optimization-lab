#pragma once
// Same independent kopt scalar row used by the original native generic kernel.
// Synthetic Host execution only; actual native submission uses kopt::gemv.
namespace gsq_integration {
#ifdef OWN_RT_HOST_ONLY
struct GenericHost final:integrated::HostOperation {
  integrated::Matrix m;
  void run(std::span<void*const> p)const override {
    auto w=static_cast<const uint8_t*>(p[0]);auto x=static_cast<const uint16_t*>(p[1]);
    auto y=static_cast<uint16_t*>(p[2]);auto r=static_cast<const iq3::Route*>(p[3]);auto status=static_cast<uint32_t*>(p[4]);
    const auto fmt=iq3::layout(m.type);const size_t rb=m.columns/fmt.elements*fmt.bytes;
    for(unsigned slot=0;slot<m.count;++slot){auto route=m.routes?r[slot]:iq3::Route{0,0,uint32_t(m.rows)};
      const bool valid=iq3::valid_route(route,m.experts,m.rows,m.rows);if(m.routes)status[slot]=!valid;
      for(size_t row=0;row<m.rows;++row){float value=iq3::bits_float(0x7fc00000);
        if(valid&&row<route.row_count)value=iq3::kopt::gemv_row(m.type,w+(size_t(route.expert_id)*m.rows+route.row_begin+row)*rb,x+slot*m.columns,m.activation,m.columns,32);
        y[slot*m.rows+row]=iq3::bf16_bits(value);
      }
    }
  }
};
inline integrated::Launch host_generic(ownrt::Device&d,const integrated::Matrix&m){
  const auto fmt=iq3::layout(m.type);if(!fmt.elements||!m.rows||!m.columns||m.columns%fmt.elements||!m.count||!m.experts||m.activation!=iq3::Type::BF16||m.output_type!=iq3::Type::BF16)throw std::invalid_argument("GSQ generic Host geometry");
  const size_t sizes[]={size_t(m.experts)*m.rows*(m.columns/fmt.elements)*fmt.bytes,size_t(m.count)*m.columns*2,size_t(m.count)*m.rows*2,size_t(m.count)*sizeof(iq3::Route),size_t(m.count)*4};
  std::array<ownrt::Allocation,5>ids{m.w,m.x,m.y,m.routes?m.routes:m.x,m.status?m.status:m.y};
  for(size_t i=0;i<(m.routes?5:3);++i)if(d.arena.row(ids[i]).bytes<sizes[i])throw std::invalid_argument("GSQ generic Host extent");
  GenericHost op;op.m=m;auto e=d.compute(op,ids,{});return {e,e,1};
}
#endif
}
