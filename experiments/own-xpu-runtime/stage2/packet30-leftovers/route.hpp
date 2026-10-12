#pragma once
#include "../packet27-round2/kernels.hpp"
#include <string_view>
#include <cstring>
namespace p30::route {
inline constexpr const char* variants[]={"p30.route.two.g1.wg32","p30.route.two.g16.wg32","p30.route.two.g16.wg64","p30.route.single.sg32"};
inline size_t scratch_bytes(ng::Shape){return 512*sizeof(float);}
// Folded gather: slots 2,3,5,6 retain IDs, weights and descriptor outputs.
// Slot 4 is absent: downstream expert consumers read source row zero.
inline void validate(ng::Shape s,ng::Args a,const std::array<size_t,19>& bytes,void* scratch,size_t sb,std::string_view variant){
 if(s.op!=ng::route_gather||s.tokens!=1||s.width<1||s.width>512||s.extra<1||s.extra>10||s.extra>s.width||s.flags!=0)throw std::invalid_argument("p30 route geometry");
 bool valid=false;for(auto v:variants)valid|=variant==v;if(!valid)throw std::invalid_argument("p30 route variant");
 std::array<size_t,19> need{};need[0]=s.width*2;need[2]=need[3]=s.extra*4;need[5]=need[6]=s.extra*12;need[15]=need[18]=4;
 std::vector<std::pair<uintptr_t,size_t>> spans;
 for(int j=0;j<19;++j)if(need[j]){auto p=reinterpret_cast<uintptr_t>(a.p[j]);if(!p||p%4||bytes[j]<need[j]||p+need[j]<p)throw std::invalid_argument("p30 route binding extent/alignment");spans.emplace_back(p,need[j]);}
 auto p=reinterpret_cast<uintptr_t>(scratch);if(!p||p%4||sb<scratch_bytes(s)||p+sb<p)throw std::invalid_argument("p30 route scratch");spans.emplace_back(p,sb);
 for(size_t i=0;i<spans.size();++i)for(size_t j=0;j<i;++j)if(spans[i].first<spans[j].first+spans[j].second&&spans[j].first<spans[i].first+spans[i].second)throw std::invalid_argument("p30 route aliases");
}
inline float read(ng::Shape s,ng::Args a,int i){(void)s;return a.b(0,i);}
inline bool before(float a,int ai,float b,int bi){return a>b||(a==b&&ai<bi);}
inline float tree(float* v,int n){for(int d=1;d<n;d*=2)for(int i=0;i<n;i+=2*d)v[i]=v[i]+(i+d<n?v[i+d]:0.f);return v[0];}
inline void write(ng::Args a,int rank,int id,float p){a.i(2)[rank]=id;a.f(3)[rank]=p;for(int j=0;j<3;++j){a.i(5)[3*rank+j]=j==0?id:j==1?0:640;a.i(6)[3*rank+j]=j==0?id:j==1?0:2560;}}
struct Fixture {
 ng::Shape s{ng::route_gather,1,512,4,10,0,512,2048};ng::Args a;std::array<size_t,19> bytes{};std::array<std::vector<uint32_t>,19> buffers;std::vector<float> scratch=std::vector<float>(512);
 explicit Fixture(int n=512,int top=10,int mode=0){s.width=n;s.extra=top;bytes=ng::required_bytes(s);for(int j=0;j<19;++j){buffers[j].resize((bytes[j]+3)/4);a.p[j]=buffers[j].data();}*a.i(18)=1;for(int j=0;j<n;++j)a.put(0,j,mode==1?0.f:float((j*37)%113-56)/7.f);if(mode==2)a.put(0,n/2,NAN);}
 Fixture(const Fixture&)=delete;Fixture& operator=(const Fixture&)=delete;
};
void cpu(ng::Shape,ng::Args,std::string_view);
int cpu_gate();
}
#if !defined(OWN_RT_HOST_ONLY) && !defined(HOST_ONLY)
#include <sycl/sycl.hpp>
namespace p30::route {
std::vector<sycl::event> submit(sycl::queue&,ng::Shape,ng::Args,float*,std::string_view,const std::vector<sycl::event>& deps={});
}
#endif
