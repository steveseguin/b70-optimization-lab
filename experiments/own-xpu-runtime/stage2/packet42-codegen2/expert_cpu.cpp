#include "../packet29-merged/p28/submit.hpp"
#include "expert_candidates.hpp"
#include <iostream>
#include <map>
#include <cstring>
struct Stat{uint64_t checks=0,failures=0,nonfinite_checks=0,nonfinite_failures=0,hash=1469598103934665603ULL;};
std::map<std::string,Stat> stats;
void check(const char* name,float a,float b,bool finite=true){auto& s=stats[name];auto aa=std::bit_cast<uint32_t>(a),bb=std::bit_cast<uint32_t>(b);if(finite){++s.checks;s.failures+=aa!=bb;s.hash^=aa;s.hash*=1099511628211ULL;}else{++s.nonfinite_checks;s.nonfinite_failures+=aa!=bb;}}
constexpr std::array<uint16_t,20> scales{0,0x8000,1,0x8001,0x03ff,0x83ff,0x0400,0x8400,0x3555,0xb555,0x3c00,0xbc00,0x7bff,0xfbff,0x7c00,0xfc00,0x7e01,0xfe01,0x7c01,0xfc01};
constexpr std::array<uint16_t,16> inputs{0,0x8000,1,0x8001,0x7f,0x807f,0x80,0x8080,0x3f80,0xbf80,0x7f80,0xff80,0x7fc1,0xffc1,0x7f81,0xff81};
template<unsigned K>void down(){
 for(unsigned sc=0;sc<scales.size();++sc)for(unsigned pattern=0;pattern<3;++pattern)for(unsigned im=0;im<18;++im){
  std::array<uint8_t,((K+31)/32)*18>w{};std::array<uint16_t,K>x{};bool finite=true;
  for(unsigned b=0;b<(K+31)/32;++b){auto s=scales[pattern==2?(sc+b)%scales.size():sc];finite=finite&&((s&0x7c00)!=0x7c00);w[b*18]=uint8_t(s);w[b*18+1]=uint8_t(s>>8);for(unsigned c=0;c<16;++c)w[b*18+2+c]=uint8_t(((c+b)%16)|(((pattern==1?c:15-c)+b)%16<<4));}
  for(unsigned i=0;i<K;++i){x[i]=im<inputs.size()?inputs[im]:im==16?inputs[i%inputs.size()]:iq3::bf16_bits(float(int((i*17)%127)-63)/128.f);finite=finite&&((x[i]&0x7f80)!=0x7f80);}
  float a[32]{},b[32]{},ref[32]{};
  for(unsigned lane=0;lane<32;++lane){a[lane]=p42expert::down_lane<0,K>(w.data(),x.data(),lane);b[lane]=p42expert::down_lane<1,K>(w.data(),x.data(),lane);
   for(unsigned k=lane*8;k<K;k+=256)for(unsigned j=0;j<8&&k+j<K;++j){float v=iq3::element(iq3::Type::IQ4_NL,w.data(),k+j);float in=iq3::bits_float(uint32_t(x[k+j])<<16);float product=v*in;ref[lane]=ref[lane]+product;}
   check("down.bank",a[lane],ref[lane],finite);check("down.bank-incumbent",a[lane],p33::down_lane<0,K>(w.data(),x.data(),lane),finite);check("down.select-incumbent",b[lane],p33::down_lane<1,K>(w.data(),x.data(),lane),finite);check("down.select",b[lane],ref[lane],finite);
  }
  auto r=iq3::tree32(ref),aa=iq3::tree32(a),bb=iq3::tree32(b);check("down.bank",aa,r,finite);check("down.select",bb,r,finite);
  check("down.bank",iq3::bits_float(uint32_t(iq3::bf16_bits(aa))<<16),iq3::bits_float(uint32_t(iq3::bf16_bits(r))<<16),finite);
  check("down.select",iq3::bits_float(uint32_t(iq3::bf16_bits(bb))<<16),iq3::bits_float(uint32_t(iq3::bf16_bits(r))<<16),finite);
 }
}
template<iq3::Type T,unsigned K>void expert(){
 std::array<uint8_t,K/iq3::layout(T).elements*iq3::layout(T).bytes>w{},v{};std::array<uint16_t,K>x{};
 for(unsigned trial=0;trial<24;++trial){for(unsigned j=0;j<w.size();++j){w[j]=uint8_t(j*29+trial*11);v[j]=uint8_t(j*17+trial*19);}bool finite=trial<14;
  for(unsigned j=0;j<w.size();j+=iq3::layout(T).bytes){w[j]=v[j]=scales[trial%20];w[j+1]=v[j+1]=scales[trial%20]>>8;}
  for(unsigned j=0;j<K;++j)x[j]=iq3::bf16_bits(float(int((j*17)%127)-63)/128.f);
  for(unsigned end:{256u,K})for(unsigned lane=0;lane<32;++lane){auto a=p42expert::gate_lane<T,K>(w.data(),v.data(),x.data(),0,end,lane);auto b=p28::expert_lane<T,K,false,true>(w.data(),v.data(),x.data(),0,end,lane,p28::ExpertByteTables{},iq3::kopt3::HostShare{});
   check("expert.incumbent",a[0],b[0],finite);check("expert.incumbent",a[1],b[1],finite);
   float r=iq3::kopt3::dot<T>(w.data(),x.data(),iq3::Type::BF16,0,end,lane,iq3::kopt3::ConstantTables{},iq3::kopt3::HostShare{});check("expert.reference",a[0],r,finite);
  }
 }
}
uint32_t rng(uint32_t& s){s^=s<<13;s^=s>>17;s^=s<<5;return s;}
std::vector<uint8_t> seed(const p28::Shape& s,unsigned salt,unsigned v,unsigned mode=0){auto fmt=iq3::layout(s.type);std::vector<uint8_t> packed(8*(s.k/fmt.elements)*fmt.bytes);uint32_t state=0x23456789u+salt;for(auto& b:packed)b=rng(state);for(size_t off=0;off<packed.size();off+=fmt.bytes){size_t at=off+(s.type==iq3::Type::Q6_K?208:0);uint16_t half=uint16_t(0x1800+rng(state)%0x1000);if(mode==2){constexpr uint16_t special[]{0,0x8000,1,0x8001,0x03ff,0x83ff,0x0400,0x8400};half=special[(off/fmt.bytes)%8];}packed[at]=half&255;packed[at+1]=half>>8;}if(s.type==iq3::Type::F32||s.type==iq3::Type::BF16){for(size_t off=0;off<packed.size();off+=fmt.bytes){float value=float(int((off/fmt.bytes)*13%127)-63)/128.f;if(s.type==iq3::Type::F32){auto bits=std::bit_cast<uint32_t>(value);std::memcpy(packed.data()+off,&bits,4);}else{auto bits=iq3::bf16_bits(value);std::memcpy(packed.data()+off,&bits,2);}}}return integrated::arithmetic::is_expanded(v)?iq3::expanded::expand(s.type,packed.data(),packed.size(),s.k):packed;}

template<iq3::Type T>void fixture(){
 constexpr unsigned K=2560; p28::Shape shape{};shape.type=T;shape.k=K;
 for(unsigned mode=0;mode<6;++mode){unsigned rows=mode==4?9:8;std::vector<uint16_t>x(K);
 for(unsigned i=0;i<K;++i){x[i]=iq3::bf16_bits(float(int(i*17%127)-63)/128.f);if(mode==1)x[i]=i%2?0x8000:0;if(mode==2){constexpr uint16_t tiny[]{0,0x8000,1,0x8001,0x007f,0x807f,0x0080,0x8080};x[i]=tiny[i%8];}if(mode==3){constexpr uint16_t extreme[]{0,0x8000,0x4f00,0xcf00,0x3000,0xb000,0x3f80,0xbf80};x[i]=extreme[i%8];}}
 auto w=seed(shape,0,2,mode),v=seed(shape,1,2,mode);unsigned rb=K/256*iq3::layout(T).bytes;
 constexpr unsigned ids[]{1,1,7,3,3,0,9,2,5,4};std::array<iq3::Route,10>routes{};for(unsigned j=0;j<10;++j)routes[j]={ids[j],0,rows};if(mode==5){routes[0]={512,0,1};routes[1]={0,rows-1,2};routes[2]={0,0,0};routes[3]={1,1,3};routes[4]={511,2,4};}
 for(auto route:routes){bool ok=iq3::valid_route(route,512,rows,rows);check("fixture.status",float(!ok),float(route.expert_id>=512||route.row_begin>rows||route.row_count>rows-route.row_begin));
 for(unsigned row=0;row<rows;++row){uint16_t result[2]{0x7fc0,0x7fc0},oracle[2]{0x7fc0,0x7fc0},incumbent[2]{0x7fc0,0x7fc0};if(ok&&row<route.row_count){unsigned offset=((route.expert_id*rows+route.row_begin+row)%8)*rb;float a[2][32]{},b[2][32]{},c[2][32]{};
 for(unsigned lane=0;lane<32;++lane){auto pair=p42expert::gate_lane<T,K>(w.data()+offset,v.data()+offset,x.data(),0,K,lane);auto base=p28::expert_lane<T,K,false,true>(w.data()+offset,v.data()+offset,x.data(),0,K,lane,p28::ExpertByteTables{},iq3::kopt3::HostShare{});for(unsigned j=0;j<2;++j){a[j][lane]=pair[j];b[j][lane]=base[j];c[j][lane]=iq3::kopt3::dot<T>((j?v:w).data()+offset,x.data(),iq3::Type::BF16,0,K,lane,iq3::kopt3::ConstantTables{},iq3::kopt3::HostShare{});}}
 for(unsigned j=0;j<2;++j){result[j]=iq3::bf16_bits(iq3::tree32(a[j]));oracle[j]=iq3::bf16_bits(iq3::tree32(c[j]));incumbent[j]=iq3::bf16_bits(iq3::tree32(b[j]));}}
 for(unsigned j=0;j<2;++j){check("fixture.output-reference",float(result[j]),float(oracle[j]));check("fixture.output-incumbent",float(result[j]),float(incumbent[j]));}}
 }}
}
int main(){fixture<iq3::Type::IQ2_S>();fixture<iq3::Type::IQ3_S>();for(unsigned q=0;q<16;++q){check("level.exhaustive",float(p33::level_bank(q)),float(p28::iq4_bytes[q]));check("level.exhaustive",float(p33::level_select(q)),float(p28::iq4_bytes[q]));}
 down<640>();down<1>();down<3>();down<17>();down<255>();down<639>();expert<iq3::Type::IQ2_S,2560>();expert<iq3::Type::IQ3_S,2560>();
 bool pass=true;std::cout<<"{\"device_executed\":false,\"candidates\":{";unsigned n=0;for(auto&[name,s]:stats){if(n++)std::cout<<',';pass=pass&&!s.failures&&(name=="expert.reference"||!s.nonfinite_failures);std::cout<<'"'<<name<<"\":{\"checks\":"<<s.checks<<",\"failures\":"<<s.failures<<",\"nonfinite_checks\":"<<s.nonfinite_checks<<",\"nonfinite_failures\":"<<s.nonfinite_failures<<",\"hash\":\""<<std::hex<<s.hash<<std::dec<<"\"}";}std::cout<<"},\"passed\":"<<(pass?"true":"false")<<"}\n";return pass?0:1;}
