// No runtime backend or device. Full HC shapes, complete state byte comparison.
#include "p94_norm.hpp"
#include "p73_hc.hpp"
#include "p90_hc.hpp"
#include <filesystem>
#include <fstream>
#include <iostream>
#include <cstring>
using iq3::Type;
void require(bool c,const std::string&s){if(!c)throw std::runtime_error(s);}
uint32_t next(uint32_t&s){return s=s*1664525u+1013904223u;}
struct State {
 std::vector<uint16_t> norm=std::vector<uint16_t>(10240,0x3f15),low=std::vector<uint16_t>(320,0x3f16),act=std::vector<uint16_t>(320,0x3f17),gate=std::vector<uint16_t>(10240,0x3f18),mix=std::vector<uint16_t>(2560,0x3f19),inject=std::vector<uint16_t>(4,0x3f20);
 std::vector<float> scratch=std::vector<float>(320,-7.25f),workspace=std::vector<float>(32,-6.25f);
 uint32_t error=0,active=1,position=0;
 p60::Bound bind(const std::vector<uint16_t>&x,const std::vector<float>&gain,const std::vector<uint8_t>&lw,const std::vector<uint8_t>&gw,const std::vector<uint8_t>&iw){return {x.data(),gain.data(),lw.data(),gw.data(),iw.data(),norm.data(),low.data(),act.data(),gate.data(),mix.data(),inject.data(),scratch.data(),workspace.data(),&error,&active,&position,4096};}
 std::vector<uint8_t> bytes()const{
  std::vector<uint8_t> out;auto add=[&](const auto&v){auto*p=reinterpret_cast<const uint8_t*>(v.data());out.insert(out.end(),p,p+v.size()*sizeof(v[0]));};
  for(auto*v:{&norm,&low,&act,&gate,&mix,&inject})add(*v);add(scratch);add(workspace);
  for(auto v:{error,active,position}){auto*p=reinterpret_cast<uint8_t*>(&v);out.insert(out.end(),p,p+4);}return out;
 }
};
void fill_q8(std::vector<uint8_t>&w,unsigned rows,unsigned k,uint32_t&seed){
 auto rb=iq3::expanded::row_bytes(Type::Q8_0,k);w.resize(rows*rb);
 for(unsigned r=0;r<rows;++r){auto*p=w.data()+r*rb;for(unsigned j=0;j<k;++j)p[j]=uint8_t(next(seed)>>24);for(unsigned j=0;j<k/32;++j){float d=float(int(next(seed)%31)-15)/4096.f;std::memcpy(p+k+4*j,&d,4);}}
}
int main(int argc,char**argv){try{
 require(argc==3,"VIEW OUTPUT");std::string name=argv[1];require(name=="production"||name=="hc-normfuse"||name=="hc-normfuse+weightcache","view");bool fused=name!="production",cached=name=="hc-normfuse+weightcache";
 std::filesystem::path out=argv[2];std::filesystem::create_directories(out);std::ofstream expected(out/"expected.bin",std::ios::binary),actual(out/"candidate.bin",std::ios::binary),cases(out/"cases.jsonl");unsigned count=0;uint64_t chain_checks=0;
 for(unsigned scenario=0;scenario<12;++scenario){
  uint32_t seed=0x940060+scenario;std::vector<uint8_t>low_w,gate_w,inject_w(4*10240*4);fill_q8(low_w,320,10240,seed);fill_q8(gate_w,10240,320,seed);auto cached_w=p90::hc_from_expanded(gate_w.data(),10240);
  for(unsigned i=0;i<4*10240;++i){float v=float(int(next(seed)%31)-15)/8192.f;std::memcpy(inject_w.data()+i*4,&v,4);}
  std::vector<uint16_t>x(10240);std::vector<float>gain(10240);for(auto&g:gain)g=float(int(next(seed)%63)-31)/32.f;
  State a,b;
  for(unsigned token=0;token<4;++token)for(unsigned side=0;side<2;++side){
   for(unsigned i=0;i<10240;++i)x[i]=iq3::bf16_bits(float(int(next(seed)%513)-256)/64.f);
   // Each new residual depends on the prior token/side's exact HC output.
   if(token||side)for(unsigned i=0;i<10240;++i)x[i]=iq3::bf16_bits(p60::get(x.data(),i)+p60::get(a.mix.data(),i%2560)/32.f);
   if(scenario==1)std::fill(x.begin(),x.end(),0);
   if(scenario==2){x[0]=1;x[1]=0x8001;x[32]=0x8000;}
   if(scenario==3)x[0]=0x7fc1;
   if(scenario==4){x[0]=0x7f80;x[32]=0xff80;}
   if(scenario==8){x[0]=0x7fc1;x[32]=0xffd5;}
   if(scenario==9){gain[0]=0.f;gain[1]=-0.f;gain[32]=iq3::bits_float(1);}
   if(scenario==10){x[0]=0x7f7f;x[2560]=0xff7f;}
   if(scenario==11){gain[0]=iq3::bits_float(0x7fc10000);gain[1]=iq3::bits_float(0xffd50000);}
   a.active=b.active=scenario==5&&token%2?0:1;a.position=b.position=scenario==7&&token%2?4096:token;
   if(scenario==6&&token==1)a.error=b.error=7;
   auto aa=a.bind(x,gain,low_w,gate_w,inject_w),bb=b.bind(x,gain,low_w,cached?cached_w:gate_w,inject_w);
   p60::host_norm(aa);p60::host_low_inject(aa);p73hc::host(aa);
   if(fused)p94norm::host(bb);else{p60::host_norm(bb);p60::host_low_inject(bb);}if(cached)p90hc::host(bb);else p73hc::host(bb);
   auto ab=a.bytes(),ba=b.bytes();expected.write(reinterpret_cast<const char*>(ab.data()),ab.size());actual.write(reinterpret_cast<const char*>(ba.data()),ba.size());
   if(ab!=ba){size_t i=0;while(i<ab.size()&&ab[i]==ba[i])++i;throw std::runtime_error("scenario="+std::to_string(scenario)+" token="+std::to_string(token)+" side="+std::to_string(side)+" byte="+std::to_string(i));}
   // Independently compare every logical chain in representative low and inject
   // rows after normalization. This includes the FP32 value before tree/BF16.
   if(p60::enabled(aa))for(unsigned stream=0;stream<4;++stream){
    float roots[4];for(unsigned g=0;g<4;++g){float v[32];for(unsigned l=0;l<32;++l)v[l]=g*32+l<80?a.scratch[stream*80+g*32+l]:0.f;roots[g]=iq3::tree32(v);}float inv=detmath::rsqrt(((roots[0]+roots[1])+(roots[2]+roots[3]))/2560.f+1e-6f);auto bound=iq3::kopt2::bounds(10240,stream,4);
    for(unsigned l=0;l<32;++l){float v=p49c::dense_lane<Type::Q8_0,10240>(low_w.data(),a.norm.data(),bound.first,bound.second,l),w=p94norm::lane<Type::Q8_0>(low_w.data(),aa,inv,true,bound.first,bound.second,l);require(std::memcmp(&v,&w,4)==0,"low raw FP32 chain");v=p49c::dense_lane<Type::F32,10240>(inject_w.data(),a.norm.data(),bound.first,bound.second,l);w=p94norm::lane<Type::F32>(inject_w.data(),aa,inv,true,bound.first,bound.second,l);require(std::memcmp(&v,&w,4)==0,"inject raw FP32 chain");chain_checks+=2;}
   }
   cases<<"{\"scenario\":"<<scenario<<",\"token\":"<<token<<",\"side\":"<<side<<",\"bytes\":"<<ab.size()<<",\"passed\":true}\n";++count;
  }
 }
 expected.close();actual.close();cases.close();require(bool(expected)&&bool(actual)&&bool(cases),"write");require(count==96,"cases");
 std::ofstream(out/"native.json")<<"{\"passed\":true,\"device_executed\":false,\"cases\":"<<count<<",\"consecutive_tokens\":4,\"hc_sides\":2,\"raw_fp32_chain_checks\":"<<chain_checks<<",\"nan_tolerance\":false}\n";
 std::cout<<count<<" full HC cases, "<<chain_checks<<" raw chains PASS\n";return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
