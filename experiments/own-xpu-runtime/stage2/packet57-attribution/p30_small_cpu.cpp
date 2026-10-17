#include "p30_small.hpp"
#include <cstdio>
#include <cstdlib>
// Independent packed-byte reference preserving the core split/lane expression.
float reference(p30::small::Shape s,const uint8_t* w,const uint16_t* x){float parts[4]{};for(unsigned p=0;p<s.split;++p){unsigned tiles=(s.cols+255)/256;unsigned begin=std::min(s.cols,(tiles*p/s.split)*256),end=std::min(s.cols,(tiles*(p+1)/s.split)*256);float lanes[32]{};
 for(unsigned l=0;l<32;++l)for(unsigned tile=begin+l*8;tile<end;tile+=256)for(unsigned i=tile;i<std::min(end,tile+8);++i){float product=iq3::element(s.type,w,i)*iq3::bits_float(uint32_t(x[i])<<16);lanes[l]=lanes[l]+product;}
 for(unsigned stride=1;stride<32;stride*=2)for(unsigned l=0;l<32;l+=stride*2)lanes[l]=lanes[l]+lanes[l+stride];parts[p]=lanes[0];}return s.split==1?parts[0]:(parts[0]+parts[1])+(parts[2]+parts[3]);}
template<unsigned K> size_t odd(){std::vector<uint8_t> w(K*4);std::vector<uint16_t>x(K);for(unsigned k=0;k<K;++k){float v=float(int(k%17)-8)/64;std::memcpy(w.data()+k*4,&v,4);x[k]=uint16_t(0x3d00+k%97);}size_t n=0;for(unsigned split:{1u,4u}){p30::small::Shape s{"odd",iq3::Type::F32,1,K,split};float a=p28::dense_row<iq3::Type::F32,K>(w.data(),x.data(),split),b=reference(s,w.data(),x.data()),c=iq3::expanded::row(iq3::Type::F32,w.data(),x.data(),iq3::Type::BF16,K,split);if(std::bit_cast<uint32_t>(a)!=std::bit_cast<uint32_t>(b)||std::bit_cast<uint32_t>(a)!=std::bit_cast<uint32_t>(c))std::exit(9);n+=2;}return n;}
int main(){size_t checks=odd<1>()+odd<3>()+odd<33>()+odd<257>(),validation=0;for(auto name:{"hc.gate","small.hc","small.ffn.q6","small.ffn.q8","shexpdown"}){p30::small::Fixture f(name);auto shapes=p30::small::shapes(name);for(auto variant:{"sg32","rows4"}){
 p30::small::cpu(name,f.bound,variant);for(size_t j=0;j<shapes.size();++j){auto s=shapes[j];auto fmt=iq3::layout(s.type);size_t rb=size_t(s.cols)/fmt.elements*fmt.bytes;
 for(unsigned r=0;r<s.rows;++r){auto ref=iq3::bf16_bits(reference(s,f.packed[j].data()+r*rb,f.inputs[j].data()));auto incumbent=iq3::bf16_bits(iq3::expanded::row(s.type,f.weights[j].data()+r*p30::small::row_bytes(s),f.inputs[j].data(),iq3::Type::BF16,s.cols,s.split));if(f.outputs[j][r]!=ref||ref!=incumbent){std::fprintf(stderr,"FAIL %s %zu %u\n",name,j,r);return 1;}checks+=2;}}
 auto invalid=f.bound;invalid[0].weight_bytes=1;try{p30::small::validate(name,invalid,variant);return 2;}catch(const std::invalid_argument&){++validation;}
 invalid=f.bound;invalid[0].x=reinterpret_cast<const uint16_t*>(reinterpret_cast<uintptr_t>(invalid[0].x)+1);try{p30::small::validate(name,invalid,variant);return 4;}catch(const std::invalid_argument&){++validation;}
 invalid=f.bound;invalid[0].w=reinterpret_cast<const uint8_t*>(UINTPTR_MAX-1);try{p30::small::validate(name,invalid,variant);return 5;}catch(const std::invalid_argument&){++validation;}
 invalid=f.bound;invalid[0].y=const_cast<uint16_t*>(invalid[0].x);try{p30::small::validate(name,invalid,variant);return 3;}catch(const std::invalid_argument&){++validation;}
 }}std::printf("{\"passed\":true,\"checks\":%zu,\"validation_rejections\":%zu}\n",checks,validation);return 0;}
