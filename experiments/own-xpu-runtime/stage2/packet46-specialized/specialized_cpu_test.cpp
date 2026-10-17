#include "specialized.hpp"
#include "../packet45-merged3/p30_small.hpp"
#include <iostream>
#include <bit>
#include <cstring>
namespace {
size_t checks=0;
void need(bool v,const char*what){if(!v)throw std::runtime_error(what);++checks;}
void same(float a,float b,const char*what){need(std::bit_cast<uint32_t>(a)==std::bit_cast<uint32_t>(b),what);}
template<iq3::Type T,unsigned K,unsigned Split>void dense_parts(){
 auto fmt=iq3::layout(T);size_t raw_stride=K/fmt.elements*fmt.bytes;std::vector<uint8_t>packed(3*raw_stride);
 for(size_t k=0;k<packed.size();++k)packed[k]=uint8_t(k*37+11);
 for(size_t off=0;off<packed.size();off+=fmt.bytes){if constexpr(T==iq3::Type::BF16){uint16_t v=uint16_t(0x3c00+(off%511));std::memcpy(packed.data()+off,&v,2);}else{uint16_t scale=0x2400;std::memcpy(packed.data()+off+(T==iq3::Type::Q6_K?208:0),&scale,2);}}
 auto expanded=iq3::expanded::expand(T,packed.data(),packed.size(),K);size_t rb=iq3::expanded::row_bytes(T,K);need(expanded.size()==rb*3,"multirow expanded stride");std::vector<uint16_t>x(K);
 for(unsigned seed=0;seed<3;++seed){for(unsigned k=0;k<K;++k)x[k]=iq3::bf16_bits(float(int((k*43+seed*13)%257)-128)/128.f);x[0]=0x8000;x[1]=0x0001; // signed zero and BF16 subnormal
  for(unsigned r=0;r<3;++r){float parts[Split];for(unsigned p=0;p<Split;++p){auto b=iq3::kopt2::bounds(K,p,Split);float old[32],now[32];for(unsigned l=0;l<32;++l){old[l]=p28::dense_lane<T,K>(expanded.data()+r*rb,x.data(),b.first,b.second,l);now[l]=p46::Member<T,3,K,Split>::lane(expanded.data()+r*rb,x.data(),p,l);same(now[l],old[l],"FP32 lane accumulator");}parts[p]=iq3::tree32(now);same(parts[p],iq3::tree32(old),"FP32 split partial");}
   float v=parts[0];if constexpr(Split==4)v=(parts[0]+parts[1])+(parts[2]+parts[3]);same(v,p28::dense_row<T,K>(expanded.data()+r*rb,x.data(),Split),"FP32 split final");same(v,p46::Member<T,3,K,Split>::cpu(expanded.data()+r*rb,x.data()),"specialized FP32 row");}
 }
}
void norms(){std::vector<uint16_t>x(10240),old(10240),now(10240);std::vector<float>w(10240),a(320),b(320);uint32_t error=0,active=1,pos=0;std::array<void*,19>args{};int dummy=0;args.fill(&dummy);args[0]=x.data();args[1]=w.data();args[2]=old.data();args[15]=&error;args[17]=&pos;args[18]=&active;ng::Args n;n.p=args;ng::Shape s;s.op=ng::norm;s.width=2560;s.heads=4;s.capacity=4096;s.flags=8;
 for(unsigned c=0;c<7;++c){for(size_t k=0;k<x.size();++k){x[k]=iq3::bf16_bits(float(int((k*17+c*41)%257)-128)/512.f);w[k]=float(int(k%17)-8)/128.f+1.f;}w[0]=-0.f;x[0]=0x8000;active=c==3?0:1;error=c==4?1:0;pos=c==5?4096:c==6?4095:127;std::fill(old.begin(),old.end(),0x1234);now=old;std::fill(a.begin(),a.end(),-123.f);b=a;unsigned initial_error=error;
  for(size_t k=0;k<specialised::work_items(s,0);++k)specialised::body<ng::norm,0,2560,4>(s,n,k,a.data(),specialised::HostGuard{});
  for(size_t k=0;k<specialised::work_items(s,1);++k)specialised::body<ng::norm,1,2560,4>(s,n,k,a.data(),specialised::HostGuard{});unsigned expected_error=error;error=initial_error;
  std::array<void*,7>p{x.data(),w.data(),now.data(),b.data(),&error,&active,&pos};p46::Norm{}.run(p);
  need(now==old,"norm BF16 raw bytes");need(std::memcmp(a.data(),b.data(),a.size()*4)==0,"norm FP32 partial raw bytes");need(error==expected_error,"norm error bytes");}
}
void gates(){p30::small::Fixture data("hc.gate");auto&b=data.bound[0];std::vector<uint16_t>norm(10240),old(2560),now(2560),expected_gate(10240);uint32_t error=0,active=1,pos=0;int dummy=0;
 for(unsigned c=0;c<4;++c){for(unsigned k=0;k<norm.size();++k)norm[k]=iq3::bf16_bits(float(int((k+c*29)%67)-33)/32.f);for(unsigned k=0;k<320;++k)data.inputs[0][k]=iq3::bf16_bits(float(int((k+c*13)%53)-26)/16.f);for(unsigned r=0;r<10240;++r)expected_gate[r]=iq3::bf16_bits(integrated::arithmetic::row(iq3::Type::Q8_0,b.w+r*p46::Gate::stride(),b.x,320,6));
  active=c==1?0:1;error=c==2?1:0;pos=c==3?4096:4095;std::fill(old.begin(),old.end(),0x1234);now=old;unsigned original_error=error;
  ng::Shape s;s.op=ng::mix;s.width=2560;s.capacity=4096;ng::Args a;a.p.fill(&dummy);a.p[0]=norm.data();a.p[1]=expected_gate.data();a.p[2]=old.data();a.p[15]=&error;a.p[17]=&pos;a.p[18]=&active;ng::cpu(s,a);unsigned expected_error=error;error=original_error;
  std::array<void*,8>p{const_cast<uint8_t*>(b.w),const_cast<uint16_t*>(b.x),b.y,norm.data(),now.data(),&error,&active,&pos};p46::GateMix{}.run(p);
  need(data.outputs[0]==expected_gate,"HC gate intermediate BF16 bytes");need(now==old,"HC mix BF16 bytes");need(error==expected_error,"HC mix error state");}
}
}
int main(){try{dense_parts<iq3::Type::Q6_K,2560,1>();dense_parts<iq3::Type::Q6_K,2560,4>();dense_parts<iq3::Type::BF16,2560,4>();dense_parts<iq3::Type::Q8_0,320,1>();norms();gates();std::cout<<"{\"schema\":\"ownrt.packet46.specialized-cpu.v1\",\"passed\":true,\"device_executed\":false,\"raw_comparisons\":"<<checks<<"}\n";return 0;}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
