#include "sycl_operation.hpp"
#include "route42.hpp"
namespace route42 {
template<unsigned Stage>struct Kernel final:ownrt::SyclOperation{Spec spec;
 sycl::event submit(sycl::queue&q,std::span<void*const>p,const std::vector<sycl::event>&deps)const override{auto a=bind(spec,p);return q.submit([&](sycl::handler&h){h.depends_on(deps);
 if constexpr(Stage!=2)h.parallel_for(sycl::range<1>(Stage==4?1:32),p28::checked([=](sycl::id<1>id){phase<Stage,512,10>(a,id[0]);}));
 else h.parallel_for(sycl::nd_range<1>(512*32,32),p28::checked([=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{if(!*a.active||a.failed())return;unsigned j=it.get_group_linear_id(),lane=it.get_local_linear_id();auto sg=it.get_sub_group();unsigned rank=rank_lane<512>(a,j,lane);for(unsigned stride=1;stride<32;stride*=2){unsigned rhs=sycl::select_from_group(sg,rank,(lane+stride)%32);if(lane%(2*stride)==0)rank+=rhs;}if(lane==0)output<512,10>(a,j,rank);}));});}
};
integrated::Launch submit(ownrt::Device&d,const Spec&s,std::span<const ownrt::Allocation>a,std::span<const ownrt::Event>deps){unsigned tail=s.ni+s.no+s.nw;if(s.op!=Op::route||s.special!=Special::normal||s.sizes[0]!=512||s.site.shape[1]!=10||s.nw||!(s.ni==1||s.ni==3)||!(s.no==2||s.no==4)||a.size()!=tail+5)throw std::invalid_argument("route42 specialized ABI");
 for(unsigned j=0;j<s.no;++j)if(s.sizes[s.ni+j]<(j<2?10u:30u))throw std::invalid_argument("route42 output logical extent");
 for(unsigned j=tail;j<tail+4;++j)for(unsigned k=tail;k<j;++k)if(a[j]==a[k])throw std::invalid_argument("route42 scratch/control alias");
 for(unsigned j=0;j<a.size();++j){const auto&r=d.arena.row(a[j]);size_t bytes=j<tail?s.sizes[j]*flash::scalar_bytes(s.types[j]):j==tail?(64+1024)*4:j==tail+4?1:4;if(!r.live||r.memory!=ownrt::Memory::device||r.bytes<bytes||reinterpret_cast<uintptr_t>(r.pointer)%4)throw std::invalid_argument("route42 binding extent/memory/alignment");}
 for(unsigned j=0;j<s.no;++j){unsigned o=s.ni+j;for(unsigned k=0;k<s.ni;++k)if(a[o]==a[k])throw std::invalid_argument("route42 output/input alias");if(a[o]==a[0]||a[o]==a[tail]||a[o]==a[tail+1]||a[o]==a[tail+2]||a[o]==a[tail+3])throw std::invalid_argument("route42 output aliases input/control/scratch");for(unsigned k=0;k<j;++k)if(a[o]==a[s.ni+k])throw std::invalid_argument("route42 output alias");}
 for(unsigned j=0;j<tail;++j)if(a[j]==a[tail])throw std::invalid_argument("route42 scratch alias");
 Launch result{};auto issue=[&]<unsigned Stage>(){Kernel<Stage>k;k.spec=s;std::array after{result.last};auto e=d.compute(k,a,result.last?std::span<const ownrt::Event>(after):deps);if(!result.first)result.first=e;result.last=e;++result.passes;};issue.template operator()<0>();issue.template operator()<1>();issue.template operator()<2>();issue.template operator()<4>();return result;}
}
