#include "stage2/packet194-expert-diet-engine/kernel_guard.hpp"
// Packet183 S1 submissions: production validations and bindings, S1 kernel structs.
#include "stage2/packet194-expert-diet-engine/s1_kernels.hpp"
namespace p183 {
template<unsigned K,unsigned Split> integrated::Launch seg_issue(ownrt::Device& d,const std::vector<integrated::Matrix>& ms){
 const auto& m=ms[0];const auto& peer=ms.size()==2?ms[1]:m;SegKernel<K,Split> k;
 k.b.rb=integrated::arithmetic::row_bytes(Type::Q6_K,K,Split==4?7:6);k.b.rows=m.rows;k.b.count=m.count;k.b.experts=m.experts;k.b.has_routes=bool(m.routes);
 if(uint64_t(m.experts)*m.rows*k.b.rb>UINT32_MAX)throw std::invalid_argument("p183 32-bit row offset overflow");
 std::array<ownrt::Allocation,9> ids{m.w,peer.w,m.x,m.y,peer.y,m.routes?m.routes:m.x,m.status?m.status:m.y,peer.status?peer.status:peer.y,m.workspace};auto e=d.compute(k,ids,{});integrated::Launch r{e,e,1};
#ifndef OWN_RT_HOST_ONLY
 if constexpr(Split==4){SegFinish f;f.n=m.rows*m.count;std::array a{m.workspace,m.y};std::array after{e};r.last=d.compute(f,a,after);r.passes=2;}
#endif
 return r;
}
integrated::Launch segment(ownrt::Device& d,const std::vector<integrated::Matrix>& m,bool shared,unsigned variant){
 p28::validate(d,m,"p28.dense.wg32",shared,variant);
 if(m.size()!=1||m[0].type!=Type::Q6_K||!integrated::arithmetic::is_expanded(variant))throw std::invalid_argument("p183 segment requires one expanded Q6_K matrix");
 const bool split4=variant==7;
 switch(m[0].columns){
 case 2560:return split4?seg_issue<2560,4>(d,m):seg_issue<2560,1>(d,m);
 case 6144:return split4?seg_issue<6144,4>(d,m):seg_issue<6144,1>(d,m);
 case 10240:return split4?seg_issue<10240,4>(d,m):seg_issue<10240,1>(d,m);
 }
 throw std::invalid_argument("p183 segment uncompiled shape");
}
integrated::Launch attention(ownrt::Device&d,const integrated::Matrix&m,const p39::Bindings&b){
 constexpr Type T=Type::Q6_K;constexpr unsigned K=6144,Split=4;constexpr p39::Kind E=p39::Kind::attention_combine;
 if(m.type!=T||m.columns!=K)throw std::invalid_argument("p183 attention requires Q6_K K6144");
 p28::validate(d,{m},"p28.dense.wg32",false,7);
 std::array<ownrt::Allocation,19> ids{m.w,m.w,m.x,m.y,m.y,m.x,m.y,m.y,m.workspace,m.x,b.out?b.out:m.y,b.streams?b.streams:m.y,b.inject?b.inject:m.x,m.x,m.x,m.x,b.error,b.active,b.position};
 AttnKernel op;op.shape.rows=m.rows;op.shape.count=m.count;op.shape.experts=m.experts;op.shape.capacity=b.capacity;op.shape.rb=integrated::arithmetic::row_bytes(T,K,7);
 std::array<void*,19> pointers;
 for(size_t i=0;i<ids.size();++i){const auto&r=d.arena.row(ids[i]);if(!r.live||r.memory!=ownrt::Memory::device)throw std::invalid_argument("p183 attention dead/nondevice binding");pointers[i]=r.pointer;}
 auto bound=op.bind(pointers);
 auto extent=[&](ownrt::Allocation id,size_t bytes){if(d.arena.row(id).bytes<bytes)throw std::invalid_argument("p183 attention allocation extent");};
 extent(b.error,4);extent(b.active,4);extent(b.position,4);
 p39::validate<T,K,E,Split>(bound);
 extent(b.streams,size_t(m.rows)*8);extent(b.inject,8);
 auto first=d.compute(op,ids,{});integrated::Launch result{first,first,1};
#ifndef OWN_RT_HOST_ONLY
 // Stage 1 reads only the partial scratch: production p49c finish, unchanged.
 {p49c::DenseKernel<T,K,Split,E,1> finish;finish.shape=op.shape;std::array after{first};result.last=d.compute(finish,ids,after);result.passes=2;}
#endif
 return result;
}
integrated::Launch small(ownrt::Device&d,std::string_view name,std::span<const integrated::Matrix>ms,std::span<const unsigned>variants){
 if(name!="small.ffn.q6")throw std::invalid_argument("p183 only banked small.ffn.q6 tuple");packet27::small::validate(d,name,ms,variants);
 if(ms.size()!=4||variants.size()!=4)throw std::invalid_argument("p183 small tuple size");
 for(unsigned i:{1u,2u})if(ms[i].type!=Type::Q6_K||ms[i].columns!=2560||!integrated::arithmetic::is_expanded(variants[i]))throw std::invalid_argument("p183 small tuple requires expanded Q6_K shared gate/up");
 SmallKernel<4>k;std::array<ownrt::Allocation,12>ids{};
 for(unsigned i=0;i<4;++i){const auto&m=ms[i];k.shapes[i].rows=m.rows;k.shapes[i].rb=integrated::arithmetic::row_bytes(m.type,m.columns,variants[i]);ids[3*i]=m.w;ids[3*i+1]=m.x;ids[3*i+2]=m.y;}
 auto e=d.compute(k,ids,{});return {e,e,1};
}
} // namespace p183
