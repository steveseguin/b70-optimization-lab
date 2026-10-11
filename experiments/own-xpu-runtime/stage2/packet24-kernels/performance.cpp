#include "performance.hpp"
namespace integrated {
#ifdef OWN_RT_HOST_ONLY
struct Multiply final : HostOperation {
  std::vector<Matrix> matrices;
  unsigned variant;
  bool shared;
  void run(std::span<void* const> p) const override {
    for (size_t i=0;i<matrices.size();++i) {
      const auto& m=matrices[i]; auto b=p.data()+i*5;
      auto w=static_cast<const uint8_t*>(b[0]);
      auto x=static_cast<const uint16_t*>(b[1]);
      auto y=static_cast<uint16_t*>(b[2]);
      auto routes=static_cast<const iq3::Route*>(b[3]);
      auto status=static_cast<uint32_t*>(b[4]);
      size_t rb=arithmetic::row_bytes(m.type,m.columns,variant);
      for(unsigned j=0;j<m.count;++j) {
        auto r=m.routes?routes[j]:iq3::Route{0,0,uint32_t(m.rows)};
        bool valid=iq3::valid_route(r,m.experts,m.rows,m.rows);
        if(m.routes)status[j]=valid?0:1;
        #pragma omp parallel for schedule(static) num_threads(2)
        for(size_t row=0;row<m.rows;++row) {
          float v=iq3::bits_float(0x7fc00000);
          if(valid && row<r.row_count)
            v=arithmetic::row(m.type,w+(size_t(r.expert_id)*m.rows+r.row_begin+row)*rb,
                             x+(shared?0:size_t(j)*m.columns),m.columns,variant);
          y[size_t(j)*m.rows+row]=iq3::bf16_bits(v);
        }
      }
    }
  }
};
// Mirror the frozen device split4's two physical submissions in CPU gates.
// The FP32 workspace keeps the same contiguous-tile partial tree and rounding.
struct SplitMultiply final : HostOperation {
 Matrix split_matrix{};unsigned variant=0;bool split_final=false;
 void run(std::span<void* const> p)const override {
  const auto& m=split_matrix;auto w=static_cast<const uint8_t*>(p[0]);
  auto x=static_cast<const uint16_t*>(p[1]);auto y=static_cast<uint16_t*>(p[2]);
  auto routes=static_cast<const iq3::Route*>(p[3]);auto status=static_cast<uint32_t*>(p[4]);
  auto scratch=static_cast<float*>(p[5]);size_t rb=arithmetic::row_bytes(m.type,m.columns,variant);
  for(unsigned slot=0;slot<m.count;++slot){
   auto route=m.routes?routes[slot]:iq3::Route{0,0,uint32_t(m.rows)};
   bool valid=iq3::valid_route(route,m.experts,m.rows,m.rows);
   if(!split_final&&m.routes)status[slot]=valid?0:1;
   #pragma omp parallel for schedule(static) num_threads(2)
   for(size_t row=0;row<m.rows;++row){size_t index=size_t(slot)*m.rows+row;
    if(split_final){float* parts=scratch+index*4;y[index]=iq3::bf16_bits((parts[0]+parts[1])+(parts[2]+parts[3]));continue;}
    for(unsigned part=0;part<4;++part){float value=iq3::bits_float(0x7fc00000);
     if(valid&&row<route.row_count){
      auto source=w+(size_t(route.expert_id)*m.rows+route.row_begin+row)*rb;
      auto input=x+size_t(slot)*m.columns;auto [begin,end]=iq3::kopt2::bounds(m.columns,part,4);float lanes[32]{};
      for(unsigned lane=0;lane<32;++lane)lanes[lane]=variant==1?
       iq3::kopt2::lane(m.type,source,input,iq3::Type::BF16,begin,end,lane):
       iq3::kopt3::lane(m.type,source,input,iq3::Type::BF16,begin,end,lane);
      value=iq3::tree32(lanes);
     }
     scratch[index*4+part]=value;
    }
   }
  }
 }
};
static Launch multiply(ownrt::Device& d,const std::vector<Matrix>& ms,unsigned v,bool shared) {
  if(v==1||v==4){
    if(ms.size()!=1||shared)throw std::invalid_argument("split4 dense CPU contract");
    const auto& m=ms.front();
    if(d.arena.row(m.w).bytes<size_t(m.experts)*m.rows*arithmetic::row_bytes(m.type,m.columns,v)||
       d.arena.row(m.x).bytes<size_t(m.count)*m.columns*2||d.arena.row(m.y).bytes<size_t(m.count)*m.rows*2||
       d.arena.row(m.workspace).bytes<size_t(m.count)*m.rows*4*sizeof(float))throw std::invalid_argument("split4 CPU extent");
    SplitMultiply op;op.split_matrix=m;op.variant=v;
    std::array ids{m.w,m.x,m.y,m.routes?m.routes:m.x,m.status?m.status:m.y,m.workspace};
    auto first=d.compute(op,ids,{});op.split_final=true;auto last=d.compute(op,ids,{});return {first,last,2};
  }
  Multiply op;op.matrices=ms;op.variant=v;op.shared=shared;
  std::vector<ownrt::Allocation> ids;
  for(auto& m:ms) {
    if(d.arena.row(m.w).bytes<size_t(m.experts)*m.rows*arithmetic::row_bytes(m.type,m.columns,v) ||
       d.arena.row(m.x).bytes<size_t(shared?1:m.count)*m.columns*2 ||
       d.arena.row(m.y).bytes<size_t(m.count)*m.rows*2)
      throw std::invalid_argument("mock matrix extent");
    ids.insert(ids.end(),{m.w,m.x,m.y,m.routes?m.routes:m.x,m.status?m.status:m.y});
  }
  auto e=d.compute(op,ids,{});return {e,e,1};
}
Launch dense(ownrt::Device& d,const Matrix& m,unsigned v){return multiply(d,{m},v,false);}
Launch experts(ownrt::Device& d,const std::vector<Matrix>& m,bool shared){return multiply(d,m,2,shared);}
struct Combine final:HostOperation {
  unsigned rows;
  void run(std::span<void* const> p)const override {
    for(unsigned r=0;r<rows;++r)static_cast<uint16_t*>(p[2])[r]=iq3::bf16_bits(
      iq3::kopt4::combine(static_cast<const uint16_t*>(p[0]),static_cast<const float*>(p[1]),rows,r));
  }
};
Launch mixture(ownrt::Device& d,ownrt::Allocation y,ownrt::Allocation p,ownrt::Allocation o,unsigned n) {
  Combine op;op.rows=n;std::array ids{y,p,o};auto e=d.compute(op,ids,{});return {e,e,1};
}
#else
Launch dense(ownrt::Device& d,const Matrix& m,unsigned v) {
  if(arithmetic::is_expanded(v)) return iq3::expanded::gemv(d,m,v==7?4:1);
  if(v==0){auto e=iq3::kopt::gemv(d,m.type,m.w,m.x,m.y,m.rows,m.columns,m.activation,m.output_type,32);return {e,e,1};}
  if(v==1){auto e=iq3::kopt2::multiply(d,{m},iq3::kopt2::Variant::split4);return {e.first,e.last,e.passes};}
  return iq3::kopt3::multiply(d,{m},v>=4?iq3::kopt3::Variant::constant_split4:iq3::kopt3::Variant::constant);
}
Launch experts(ownrt::Device& d,const std::vector<Matrix>& m,bool shared) {
  if(m[0].type==iq3::Type::F32) // synthetic mini-model, same tree
    return iq3::kopt3::multiply(d,m,iq3::kopt3::Variant::constant);
  return shared?iq3::kopt4::expert_gate_up(d,m.at(0),m.at(1),1):iq3::kopt4::expert_down(d,m.at(0),1);
}
Launch mixture(ownrt::Device& d,ownrt::Allocation y,ownrt::Allocation p,ownrt::Allocation o,unsigned n) {
  return iq3::kopt4::epilogue(d,y,p,o,n);
}
#endif
}
