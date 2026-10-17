#include "gemv.hpp"
#include <iostream>
#include <memory>
#include <vector>
#include <string>

namespace {
size_t checks=0;
std::string context;
uint32_t rng=0x48b70;
uint32_t random32(){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;}
void equal(float a,float b,const std::string& what){++checks;if(std::bit_cast<uint32_t>(a)!=std::bit_cast<uint32_t>(b))throw std::runtime_error(context+" "+what+" expected="+std::to_string(std::bit_cast<uint32_t>(a))+" actual="+std::to_string(std::bit_cast<uint32_t>(b)));}
struct Buffer {uint8_t* p;explicit Buffer(size_t n):p(static_cast<uint8_t*>(::operator new(n,std::align_val_t{64}))){}~Buffer(){::operator delete(p,std::align_val_t{64});}};
template<iq3::Type T,unsigned K> float old_lane(const uint8_t* w,const uint16_t* x,unsigned begin,unsigned end,unsigned lane){
 if constexpr(T==iq3::Type::IQ2_S||T==iq3::Type::IQ3_S)return p28::expert_lane<T,K,false,false>(w,w,x,begin,end,lane,p28::ExpertByteTables{},iq3::kopt3::HostShare{})[0];
 else if constexpr(T==iq3::Type::IQ4_NL){if(begin||end!=K)throw std::runtime_error("down split");return p33::down_lane<1,K>(w,x,lane);}
 else return p33::dense_lane<T,K>(w,x,begin,end,lane);
}
template<iq3::Type T,unsigned K> void test_format(){
 constexpr unsigned rows=5;const size_t src_rb=p48::source_row_bytes(T,K);constexpr auto l=p48::layout(T,K);std::vector<uint8_t> original(rows*src_rb);Buffer packed(rows*l.row_bytes);std::vector<uint16_t> x(K),y(K);
 for(unsigned run=0;run<8;++run){
  for(auto& b:original)b=uint8_t(random32());
  // Purely generated format fixtures: no model payload. Weight scales are
  // finite, including both signed zeros. Nonfinite banks have a separate
  // rejection gate below; their payloads are never silently canonicalized.
  for(unsigned row=0;row<rows;++row){auto* s=original.data()+row*src_rb;
   if constexpr(T==iq3::Type::Q6_K||T==iq3::Type::Q8_0){constexpr unsigned group=T==iq3::Type::Q6_K?16:32;for(unsigned k=0;k<K;k+=group){uint32_t bits=0x3c000000|(random32()&0x807fffff);if(run>=6&&(k/group)%5==0)bits=(run==6?0u:0x80000000u);std::memcpy(s+K+4*(k/group),&bits,4);}}
   else {auto f=iq3::layout(T);for(unsigned b=0;b<K/f.elements;++b){uint16_t bits=uint16_t(0x2800|(random32()&0x83ff));if(run>=6&&b%5==0)bits=run==6?0:0x8000;std::memcpy(s+b*f.bytes,&bits,2);}}
   context="type="+std::to_string(unsigned(T))+" run="+std::to_string(run)+" row="+std::to_string(row);
   p48::repack_row(T,K,s,packed.p+row*l.row_bytes);
   for(unsigned k=0;k<K;k+=8){float got[8],want[8];p48::decode8<T,K>(packed.p+row*l.row_bytes,k,got);
    if constexpr(T==iq3::Type::IQ2_S||T==iq3::Type::IQ3_S)p28::expert_decode8<T,false>(s,k,want,p28::ExpertByteTables{},iq3::kopt3::HostShare{});
    else if constexpr(T==iq3::Type::IQ4_NL){auto* b=s+(k/32)*18;float scale=iq3::half(iq3::u16(b));for(unsigned j=0;j<8;++j){unsigned n=k%32+j;unsigned q=(b[2+n%16]>>(4*(n/16)))&15;want[j]=scale*float(p33::level_select(q));}}
    else {constexpr unsigned group=T==iq3::Type::Q6_K?16:32;float scale=iq3::bits_float(iq3::u32(s+K+4*(k/group)));for(unsigned j=0;j<8;++j)want[j]=scale*float(iq3::signed8(s[k+j]));}
    for(unsigned j=0;j<8;++j)equal(want[j],got[j],"decoded value type="+std::to_string(unsigned(T))+" row="+std::to_string(row)+" k="+std::to_string(k+j));
   }
  }
  for(unsigned k=0;k<K;++k){x[k]=uint16_t(0x3e00|(random32()&0x81ff));y[k]=uint16_t(0x3e00|(random32()&0x81ff));if(run==7&&k%257==0)x[k]=0x7fc3;}
  if(run==6){x[0]=0x7f80;x[8]=0xff80;}
  // Ordinary QKV/Z use split1. Keep split4 only as an additional compatibility
  // check, never as a substitute for the production row's accumulation tree.
  constexpr unsigned split_cases=(T==iq3::Type::Q6_K||T==iq3::Type::Q8_0)?2:1;
  for(unsigned split_case=0;split_case<split_cases;++split_case){unsigned splits=split_case?4:1;
  for(unsigned row=0;row<rows;++row){const auto* s=original.data()+row*src_rb;const auto* p=packed.p+row*l.row_bytes;float old_parts[4]{},new_parts[4]{};
   for(unsigned part=0;part<splits;++part){auto bounds=iq3::kopt2::bounds(K,part,splits);float old[32],now[32];
    for(unsigned lane=0;lane<32;++lane){context="type="+std::to_string(unsigned(T))+" run="+std::to_string(run)+" row="+std::to_string(row)+" split="+std::to_string(splits)+" part="+std::to_string(part)+" lane="+std::to_string(lane);old[lane]=old_lane<T,K>(s,x.data(),bounds.first,bounds.second,lane);now[lane]=p48::lane<T,K>(p,x.data(),bounds.first,bounds.second,lane);equal(old[lane],now[lane],"lane");auto pair=p48::lanes2<T,K>(p,x.data(),y.data(),bounds.first,bounds.second,lane);equal(old[lane],pair[0],"M2 first");equal(old_lane<T,K>(s,y.data(),bounds.first,bounds.second,lane),pair[1],"M2 second");
     if constexpr(T==iq3::Type::IQ2_S||T==iq3::Type::IQ3_S){unsigned peer=(row+1)%rows;auto a=p28::expert_lane<T,K,false,true>(s,original.data()+peer*src_rb,x.data(),bounds.first,bounds.second,lane,p28::ExpertByteTables{},iq3::kopt3::HostShare{});auto b=p48::gate_lane<T,K>(p,packed.p+peer*l.row_bytes,x.data(),bounds.first,bounds.second,lane);equal(a[0],b[0],"gate pair");equal(a[1],b[1],"up pair");}
    }
    old_parts[part]=iq3::tree32(old);new_parts[part]=iq3::tree32(now);equal(old_parts[part],new_parts[part],"adjacent SG32 tree");
   }
   float before=splits==1?old_parts[0]:(old_parts[0]+old_parts[1])+(old_parts[2]+old_parts[3]);float after=splits==1?new_parts[0]:(new_parts[0]+new_parts[1])+(new_parts[2]+new_parts[3]);equal(before,after,"split tree");++checks;if(iq3::bf16_bits(before)!=iq3::bf16_bits(after))throw std::runtime_error("BF16 store");
  }
  }
 }
 // Exercise every nonfinite half payload (positive and negative), and each
 // IEEE float category/sign/extreme payload. Rejection precedes all writes.
 {auto* s=original.data();auto* d=packed.p;size_t at=(T==iq3::Type::Q6_K||T==iq3::Type::Q8_0)?K:0;
  const unsigned width=(T==iq3::Type::Q6_K||T==iq3::Type::Q8_0)?4:2;uint32_t saved=0;std::memcpy(&saved,s+at,width);
  auto reject=[&](uint32_t bits){std::memcpy(s+at,&bits,width);std::memset(d,0xa5,l.row_bytes);bool rejected=false;try{p48::repack_row(T,K,s,d);}catch(const std::invalid_argument& e){rejected=std::string(e.what())=="p48 nonfinite weight scale";}++checks;if(!rejected)throw std::runtime_error("nonfinite weight admitted");for(size_t j=0;j<l.row_bytes;++j)if(d[j]!=0xa5)throw std::runtime_error("rejected repack wrote destination");++checks;};
  if constexpr(T==iq3::Type::Q6_K||T==iq3::Type::Q8_0){for(uint32_t sign:{0u,0x80000000u})for(uint32_t payload:{0u,1u,0x3fffffu,0x400000u,0x400001u,0x7fffffu})reject(sign|0x7f800000u|payload);}
  else {for(unsigned sign:{0u,0x8000u})for(unsigned payload=0;payload<1024;++payload)reject(sign|0x7c00u|payload);}
  std::memcpy(s+at,&saved,width);
 }
 std::cout<<"{\"type\":"<<unsigned(T)<<",\"K\":"<<K<<",\"source_row_bytes\":"<<src_rb<<",\"packed_row_bytes\":"<<l.row_bytes<<",\"passed\":true}\n";
}
}
int main(){try{
 test_format<iq3::Type::IQ2_S,2560>();test_format<iq3::Type::IQ3_S,2560>();test_format<iq3::Type::IQ4_NL,640>();test_format<iq3::Type::Q6_K,2560>();test_format<iq3::Type::Q8_0,2560>();
 std::cout<<"{\"schema\":\"p48.cpu-gemv.v1\",\"checks\":"<<checks<<",\"passed\":true}\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
