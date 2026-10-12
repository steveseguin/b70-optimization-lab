#pragma once
#include "../packet27-round2/specialised.hpp"
#include <string_view>
#include <cstring>
#ifndef OWN_RT_HOST_ONLY
#include <sycl/sycl.hpp>
#endif
namespace p30::fusion {
inline void validate(ng::Shape s,ng::Args a,const std::array<size_t,19>& sizes,std::string_view v){
 ng::validate(s);if(s.tokens!=1||s.heads!=4||s.width>2560||(s.flags&~9)||(s.op!=ng::norm&&s.op!=ng::combine_norm&&s.op!=ng::mix)||(v!="sg32"&&v!="tiled"))throw std::invalid_argument("p30 fusion shape/variant");
 auto n=ng::required_bytes(s);std::vector<int> slots=s.op==ng::combine_norm?std::vector<int>{0,1,2,3,4,5,15,17,18}:std::vector<int>{0,1,2,15,17,18};
 for(int i:slots){uintptr_t address=reinterpret_cast<uintptr_t>(a.p[i]);int gain=s.op==ng::combine_norm?3:1;size_t alignment=(i>=15||((s.flags&8)&&s.op!=ng::mix&&i==gain))?4:2;if(!address||sizes[i]<n[i]||address%alignment||n[i]>UINTPTR_MAX-address)throw std::invalid_argument("p30 fusion extent/alignment/overflow");}
 auto output=[&](int i){return i==15||(s.op==ng::combine_norm?(i==4||i==5):i==2);};
 for(int i:slots)for(int j:slots)if(i!=j&&output(i)){uintptr_t x=reinterpret_cast<uintptr_t>(a.p[i]),y=reinterpret_cast<uintptr_t>(a.p[j]);if(x<y+n[j]&&y<x+n[i])throw std::invalid_argument("p30 fusion alias");}
}
inline bool active(ng::Shape s,ng::Args a){if(!a.i(18)[0]||a.i(15)[0])return false;int p=a.i(17)[0];if(p<0||p>s.capacity-s.tokens){a.i(15)[0]=1;return false;}return true;}
template<bool Combine> inline float value(ng::Shape s,ng::Args a,unsigned row,unsigned k){if constexpr(Combine)return ng::Args::bf(a.b(0,row*s.width+k)+a.b(1,k)*(2.f*ng::sigmoid(a.b(2,row)/4.f)));else return a.b(0,row*s.width+k);}
template<bool Combine> inline void cpu_norm(ng::Shape s,ng::Args a){for(unsigned row=0;row<4;++row){float partial[80];unsigned chunks=(s.width+31)/32;
 for(unsigned c=0;c<chunks;++c)partial[c]=specialised::subtree(s.width,c,[&](int k){float x=value<Combine>(s,a,row,k);return x*x;});
 float inv=detmath::rsqrt(specialised::upper(partial,chunks)/float(s.width)+1e-6f);
 for(unsigned k=0;k<unsigned(s.width);++k){float x=value<Combine>(s,a,row,k);float y=(x*inv)*(a.weight(Combine?3:1,row*s.width+k,s.flags)+float(s.flags&1));a.put(Combine?5:2,row*s.width+k,y);if constexpr(Combine)a.put(4,row*s.width+k,x);}
}}
inline void cpu(ng::Shape s,ng::Args a,const std::array<size_t,19>& sizes,std::string_view v){validate(s,a,sizes,v);if(!active(s,a))return;
 if(s.op==ng::combine_norm)cpu_norm<true>(s,a);else if(s.op==ng::norm)cpu_norm<false>(s,a);else for(int k=0;k<s.width;++k){float sum=0;for(int h=0;h<4;++h)sum=sum+ng::sigmoid(a.b(1,h*s.width+k))*a.b(0,h*s.width+k);a.put(2,k,sum/4.f);}}
struct Fixture {ng::Shape shape;ng::Args args;std::array<size_t,19> sizes;std::array<std::vector<uint8_t>,19> storage;
 explicit Fixture(ng::Shape s):shape(s),sizes(ng::required_bytes(s)){for(int i=0;i<19;++i){storage[i].resize(sizes[i]);args.p[i]=storage[i].data();for(size_t j=0;j+1<sizes[i];j+=2){uint16_t v=uint16_t(0x3c00+(j/2+i*17)%768);std::memcpy(storage[i].data()+j,&v,2);}}
  int gain=s.op==ng::combine_norm?3:1;if((s.flags&8)&&s.op!=ng::mix)for(size_t j=0;j<sizes[gain]/4;++j)args.f(gain)[j]=0.5f+float(j%17)/32;
  args.i(15)[0]=0;args.i(17)[0]=3;args.i(18)[0]=1;
 }
};
#ifndef OWN_RT_HOST_ONLY
std::vector<sycl::event> submit(sycl::queue&,ng::Shape,ng::Args,const std::array<size_t,19>&,std::string_view,const std::vector<sycl::event>& = {});
#endif
}
