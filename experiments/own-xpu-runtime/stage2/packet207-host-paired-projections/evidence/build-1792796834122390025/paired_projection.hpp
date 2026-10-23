#pragma once
#ifndef OWN_RT_HOST_ONLY
#error P207 paired projection is a CPU-only experimental operation
#endif
// Included after the pinned Engine. F32 follows kopt3::dot/variant2; expanded
// Q6 follows p33::dense_lane/variant6 and P202's independently checked pair.
namespace p207 {
struct PairOperation final:integrated::HostOperation {
  iq3::Type type=iq3::Type::F32;
  size_t rows=0,columns=0,stride=0;
  void run(std::span<void*const> p)const override {
    const auto* weights=static_cast<const uint8_t*>(p[0]);
    const uint16_t* x[]{static_cast<const uint16_t*>(p[1]),static_cast<const uint16_t*>(p[2])};
    uint16_t* y[]{static_cast<uint16_t*>(p[3]),static_cast<uint16_t*>(p[4])};
    for(size_t row=0;row<rows;++row) {
      const auto* w=weights+row*stride;float lanes[2][32]{};
      for(unsigned lane=0;lane<32;++lane)for(size_t tile=lane*8;tile<columns;tile+=256) {
        // Q6's shared expanded scale is read once for the two row chains.
        const float scale=type==iq3::Type::Q6_K?iq3::bits_float(iq3::u32(w+columns+4*(tile/16))):0.f;
        for(unsigned j=0;j<8 && tile+j<columns;++j) {
          const float weight=type==iq3::Type::Q6_K?scale*float(iq3::signed8(w[tile+j])):iq3::element(iq3::Type::F32,w,tile+j);
          const float p0=weight*iq3::bits_float(uint32_t(x[0][tile+j])<<16);
          const float p1=weight*iq3::bits_float(uint32_t(x[1][tile+j])<<16);
          lanes[0][lane]=lanes[0][lane]+p0;lanes[1][lane]=lanes[1][lane]+p1;
        }
      }
      for(unsigned r=0;r<2;++r)y[r][row]=iq3::bf16_bits(iq3::tree32(lanes[r]));
    }
  }
};
inline integrated::Launch paired_projection(ownrt::Device& d,const Matrix& a,const Matrix& b,unsigned variant) {
  require(a.type==b.type && a.w==b.w && a.rows==b.rows && a.columns==b.columns && a.count==1 && b.count==1 && a.experts==1 && b.experts==1 && !a.routes && !b.routes && !a.fp32 && !b.fp32 && a.activation==iq3::Type::BF16 && b.activation==iq3::Type::BF16 && a.output_type==iq3::Type::BF16 && b.output_type==iq3::Type::BF16,"p207 pair matrix identity");
  const bool mini=a.type==iq3::Type::F32 && variant==2 && a.columns==16 && (a.rows==20 || a.rows==12);
  const bool q6=a.type==iq3::Type::Q6_K && variant==6 && a.columns==2560 && (a.rows==10240 || a.rows==6144);
  require(mini||q6,"p207 unsupported paired type/shape/layout");
  size_t stride=arithmetic::row_bytes(a.type,a.columns,variant);
  require(stride==(mini?64u:3380u),"p207 pair resident row stride");
  std::array<Allocation,7> ids{a.w,a.x,b.x,a.y,b.y,a.workspace,b.workspace};
  const size_t needed[]{a.rows*stride,a.columns*2,a.columns*2,a.rows*2,a.rows*2,4,4};
  for(size_t i=0;i<ids.size();++i) {
    const auto& r=d.arena.row(ids[i]);
    require(r.live && r.memory==Memory::device && r.bytes>=needed[i] && uintptr_t(r.pointer)%(i>=1&&i<=4?2:4)==0,"p207 pair binding extent/alignment");
    for(size_t j=0;j<i;++j)if(i>=3 || j>=3)require(ids[i]!=ids[j],"p207 pair writable alias");
  }
  require(a.x!=b.x,"p207 pair row inputs must be distinct allocations");
  PairOperation op;op.type=a.type;op.rows=a.rows;op.columns=a.columns;op.stride=stride;
  auto event=d.compute(op,ids,{});return {event,event,1};
}
} // namespace p207
