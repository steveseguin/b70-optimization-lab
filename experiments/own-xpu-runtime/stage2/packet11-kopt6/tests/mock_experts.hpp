#pragma once
#include "expert_case.hpp"
#include "mock_device.hpp"

namespace expert_test {
// CPU backend executes reference operations through the real owner and Arena.
// The shared case still owns every upload, readback, allocation and release.
struct CpuOperation:ownrt::Operation {
  std::function<void(std::span<void* const>)> run;
};
struct CpuDevice:ownrt::MockDevice {
  unsigned launches=0;
  ownrt::Event copy(void* dst,const void* src,size_t n,std::span<const ownrt::Event> deps) override {
    auto e=MockDevice::copy(dst,src,n,deps);finish(e);return e;
  }
  ownrt::Event compute(const ownrt::Operation& op,std::span<void* const> ptrs,std::span<const ownrt::Event> deps) override {
    for(auto e:deps)require(complete(e),"pending CPU dependency");
    dynamic_cast<const CpuOperation&>(op).run(ptrs);++launches;return marker(deps);
  }
};
struct CpuKernels {
  kopt6::Variant variant=kopt6::Variant::baseline;
  kopt6::Launch project(ownrt::Device& d,std::vector<kopt6::Matrix> matrices,unsigned split,bool shared) {
    std::vector<ownrt::Allocation> ids;
    for(const auto& m:matrices)for(auto id:{m.w,m.x,m.y,m.routes,m.status,m.fp32})ids.push_back(id);
    auto selected_variant=variant;CpuOperation op;
    op.run=[=](std::span<void* const> p){
      for(size_t i=0;i<matrices.size();++i) {
        const auto& m=matrices[i];size_t base=i*6;auto l=layout(m.type);size_t rb=m.columns/l.elements*l.bytes;
        auto routes=static_cast<const Route*>(p[base+3]);
        for(unsigned slot=0;slot<m.count;++slot) {
          bool valid=valid_route(routes[slot],m.experts,m.rows,m.span);
          static_cast<uint32_t*>(p[base+4])[slot]=valid?0:1;
          for(unsigned r=0;r<m.span;++r) {
            float v=bits_float(0x7fc00000);
            if(valid && r<routes[slot].row_count) {
              auto w=static_cast<const uint8_t*>(p[base])+(size_t(routes[slot].expert_id)*m.rows+routes[slot].row_begin+r)*rb;
              auto x=static_cast<const uint16_t*>(p[base+1])+(shared?0:size_t(slot)*m.columns);
              v=kopt6::candidate_row(m.type,w,x,m.activation,m.columns,split,selected_variant);
            }
            size_t at=size_t(slot)*m.span+r;
            static_cast<uint16_t*>(p[base+2])[at]=output_bits(v,m.output_type);
            static_cast<float*>(p[base+5])[at]=v;
          }
        }
      }
    };
    auto e=d.compute(op,ids,{});return {e,e,1};
  }
  kopt6::Launch expert_gate_up(ownrt::Device& d,const kopt6::Matrix& gate,const kopt6::Matrix& up,unsigned split){return project(d,{gate,up},split,true);}
  kopt6::Launch expert_down(ownrt::Device& d,const kopt6::Matrix& down,unsigned split){return project(d,{down},split,false);}
  kopt6::Launch epilogue(ownrt::Device& d,ownrt::Allocation down,ownrt::Allocation weights,ownrt::Allocation output,unsigned rows,ownrt::Allocation fp) {
    CpuOperation op;op.run=[=](std::span<void* const> p){
      for(unsigned r=0;r<rows;++r){float v=kopt6::combine(static_cast<const uint16_t*>(p[0]),static_cast<const float*>(p[1]),rows,r);
        static_cast<uint16_t*>(p[2])[r]=bf16_bits(v);static_cast<float*>(p[3])[r]=v;}
    };
    std::array ids{down,weights,output,fp};auto e=d.compute(op,ids,{});return {e,e,1};
  }
};
inline unsigned mock_experts(const std::filesystem::path& fixtures) {
  unsigned checks=0;
  for(unsigned variant=0;variant<4;++variant) {
    unsigned split=1;
    auto backend=std::make_unique<CpuDevice>();auto* mock=backend.get();ownrt::Device d(std::move(backend));
    for(const auto* name:{"random0-IQ2_S.fixture","random1-IQ3_S.fixture","random0-IQ4_NL.fixture"}) {
      Fixture f((fixtures/name).string());
      for(unsigned mutation=0;mutation<8;++mutation){exercise(CpuKernels{kopt6::Variant(variant)},d,f,mutation,split);++checks;}
    }
    Fixture f((fixtures/"random1-IQ3_S.fixture").string());
    for(unsigned mutation:{0u,1u}){exercise(CpuKernels{kopt6::Variant(variant)},d,f,mutation,split,true);++checks;}
    require(mock->launches==78,"three launches per expert case");
    require(!d.arena.total(ownrt::Memory::device) && !d.arena.total(ownrt::Memory::pinned) && !d.in_flight(),"expert case leaked ownership");
    auto receipt=d.shutdown(std::chrono::seconds(10));
    require(receipt.safe_to_exit && receipt.idle_marker_complete && !receipt.live_bytes && !receipt.in_flight && mock->context_closed,"expert teardown");
  }
  return checks;
}
}
