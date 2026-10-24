#include "formats.hpp"
#include <openssl/evp.h>
#include <fstream>
#include <iostream>
#include <sstream>
#include <vector>
#include <cstring>
extern "C" void gsq_reference(unsigned,const void*,float*,size_t);
extern "C" float gsq_reference_half(uint16_t);
static void need(bool b,const std::string&s){if(!b)throw std::runtime_error(s);}
static std::string sha(const std::vector<uint8_t>&b){unsigned char h[32];unsigned n;EVP_Digest(b.data(),b.size(),h,&n,EVP_sha256(),nullptr);std::string out;for(unsigned i=0;i<n;++i){out+="0123456789abcdef"[h[i]>>4];out+="0123456789abcdef"[h[i]&15];}return out;}
static void append(std::vector<uint8_t>&b,const std::vector<float>&v){auto p=reinterpret_cast<const uint8_t*>(v.data());b.insert(b.end(),p,p+v.size()*4);}
int main(int argc,char**argv){try{
 uint64_t values=0,cases=0,gemvs=0,finite_half=0;std::vector<uint8_t> own_bytes,ref_bytes;std::vector<std::string>real;
 for(unsigned h=0;h<65536;++h)if((h&0x7c00)!=0x7c00){need(std::bit_cast<uint32_t>(iq3::half(h))==std::bit_cast<uint32_t>(gsq_reference_half(h)),"finite half conversion");++finite_half;}
 auto check=[&](unsigned type,const std::vector<uint8_t>&raw,size_t cols,const std::string&label){
  std::vector<float>actual(cols),expected(cols);gsq::decode_row(type,raw,actual);gsq_reference(type,raw.data(),expected.data(),cols);
  for(size_t i=0;i<cols;++i){need(std::bit_cast<uint32_t>(actual[i])==std::bit_cast<uint32_t>(expected[i]),"decode mismatch "+label+" index "+std::to_string(i)+" own "+std::to_string(std::bit_cast<uint32_t>(actual[i]))+" ref "+std::to_string(std::bit_cast<uint32_t>(expected[i])));need(std::bit_cast<uint32_t>(gsq::element(type,raw,cols,i))==std::bit_cast<uint32_t>(expected[i]),"element dispatch mismatch");}
  std::vector<uint16_t>x(cols);for(size_t i=0;i<cols;++i)x[i]=i%31==0?0x8000:iq3::bf16_bits(float(int((i*17)%41)-20)/16.f);
  float sums[32]{};for(size_t lane=0;lane<32;++lane)for(size_t k=lane;k<cols;k+=32){float product=expected[k]*iq3::bits_float(uint32_t(x[k])<<16);sums[lane]=sums[lane]+product;}
  for(size_t width=1;width<32;width*=2)for(size_t lane=0;lane<32;lane+=2*width)sums[lane]=sums[lane]+sums[lane+width];
  float got=gsq::row_gemv(type,raw,x);need(std::bit_cast<uint32_t>(got)==std::bit_cast<uint32_t>(sums[0]),"ordered row GEMV mismatch "+label);
  append(own_bytes,actual);append(ref_bytes,expected);values+=cols;++cases;++gemvs;
 };
 constexpr uint16_t scales[]{0,0x8000,1,0x8001,0x03ff,0x0400,0x3555,0xb555,0x3c00,0xbc00,0x7bff,0xfbff};
 for(unsigned type:{42,12,13,23}){
  auto f=gsq::layout(type);size_t headers=(type==12||type==13)?4:2;
  // Flip every packed field bit against a nonzero baseline, and require
  // the independent reference output to change (not merely execute the bit).
  std::vector<uint8_t>base(f.bytes,0x55);uint16_t one=0x3c00,minus=0xbc00;
  std::memcpy(base.data(),&one,2);if(headers==4)std::memcpy(base.data()+2,&minus,2);
  std::vector<float>base_out(f.elements);gsq_reference(type,base.data(),base_out.data(),f.elements);
  for(size_t byte=headers;byte<f.bytes;++byte)for(unsigned bit=0;bit<8;++bit){auto b=base;b[byte]^=uint8_t(1u<<bit);std::vector<float>changed(f.elements);gsq_reference(type,b.data(),changed.data(),f.elements);need(std::memcmp(changed.data(),base_out.data(),f.elements*4)!=0,"inert field bit");check(type,b,f.elements,"bit-"+std::to_string(type)+"-"+std::to_string(byte)+"-"+std::to_string(bit));}
  for(unsigned variant=0;variant<64;++variant)for(unsigned sc=0;sc<std::size(scales);++sc){std::vector<uint8_t>b(f.bytes*3);for(size_t i=0;i<b.size();++i)b[i]=uint8_t((i*73+variant*29)^(i*variant+0xa5));for(unsigned block=0;block<3;++block){auto d=scales[(sc+block)%std::size(scales)];std::memcpy(b.data()+block*f.bytes,&d,2);if(headers==4){auto m=scales[(sc+block+5)%std::size(scales)];std::memcpy(b.data()+block*f.bytes+2,&m,2);}}check(type,b,f.elements*3,"pattern-"+std::to_string(type)+"-"+std::to_string(variant)+"-"+std::to_string(sc));}
 }
 need((argc-1)%3==0,"slice argument triples");
 for(int i=1;i<argc;i+=3){unsigned type=unsigned(std::stoul(argv[i]));size_t cols=std::stoull(argv[i+1]);std::ifstream f(argv[i+2],std::ios::binary);need(bool(f),"slice open");std::vector<uint8_t>b((std::istreambuf_iterator<char>(f)),{});need(b.size()==gsq::row_bytes(type,cols),"slice bytes");check(type,b,cols,"real-"+std::to_string(i/3));std::ostringstream o;o<<"{\"type\":"<<type<<",\"columns\":"<<cols<<",\"bytes\":"<<b.size()<<",\"sha256\":\""<<sha(b)<<"\"}";real.push_back(o.str());}
 unsigned refusals=0;auto refuse=[&](auto fn){bool caught=false;try{fn();}catch(const std::invalid_argument&){caught=true;}need(caught,"missing refusal");++refusals;};
 refuse([]{gsq::layout(999);});refuse([]{gsq::row_bytes(42,0);});refuse([]{gsq::row_bytes(12,255);});refuse([]{gsq::row_bytes(12,std::numeric_limits<size_t>::max());});
 std::vector<uint8_t>b(18);std::vector<float>y(64);std::vector<uint16_t>x(64);refuse([&]{gsq::decode_row(42,std::span(b).first(17),y);});refuse([&]{gsq::element(42,b,64,64);});refuse([&]{gsq::row_gemv(42,b,std::span(x).first(63));});
 need(own_bytes==ref_bytes,"aggregate bytes");std::cout<<"{\"passed\":true,\"schema\":\"ownrt.gsq.scalar-formats.v1\",\"device_executed\":false,\"model_executed\":false,\"native_executed\":false,\"cases\":"<<cases<<",\"decoded_values\":"<<values<<",\"ordered_gemv_rows\":"<<gemvs<<",\"finite_half_values\":"<<finite_half<<",\"refusals\":"<<refusals<<",\"own_output_sha256\":\""<<sha(own_bytes)<<"\",\"reference_output_sha256\":\""<<sha(ref_bytes)<<"\",\"real_slices\":[";for(size_t i=0;i<real.size();++i)std::cout<<(i?",":"")<<real[i];std::cout<<"]}\n";return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
