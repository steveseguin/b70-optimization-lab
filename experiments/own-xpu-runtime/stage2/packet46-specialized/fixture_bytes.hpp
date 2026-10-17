#pragma once
// Packet34 deterministic synthetic bytes; no model payload access.
namespace fixture46 {
inline std::string canonical(const std::string& n){return n;}
inline uint64_t seed_for(const std::string& n) {
 uint64_t v=0x34d0cafe20261011ull;
 for(unsigned char c:canonical(n)){v^=c;v*=1099511628211ull;}return v;
}
inline uint64_t mix(uint64_t x) {
 x^=x>>30;x*=0xbf58476d1ce4e5b9ull;x^=x>>27;x*=0x94d049bb133111ebull;return x^(x>>31);
}
inline std::vector<uint8_t> generated(const flash::Tensor& t,size_t off,size_t n) {
 flash::validate_descriptor(t);
 require(n&&n<=4u*1024*1024&&off<=t.bytes&&n<=t.bytes-off,"generator bounded extent");
 auto type=flash::grid_type(t.grid);auto fmt=iq3::layout(type);
 std::vector<uint8_t> out(n);uint64_t seed=seed_for(t.name);
 if(type==iq3::Type::F32||type==iq3::Type::BF16){
  const size_t width=type==iq3::Type::F32?4:2;
  require(off%width==0&&n%width==0,"scalar generator alignment");
  for(size_t j=0;j<n;j+=width){
   uint64_t h=mix(seed+(off+j)/width);
   float x=float(int(h%33)-16)/8192.f;
   if(t.name.find("norm")!=std::string::npos)x+=1.f;
   if(ends(t.name,"ssm_a"))x=-.5f-std::abs(x);
   if(width==4)std::memcpy(out.data()+j,&x,4);
   else{uint16_t b=iq3::bf16_bits(x);std::memcpy(out.data()+j,&b,2);}
  }
 }else{
  // Thirty-two distinct valid blocks repeat throughout each tensor. All bit
  // patterns in integer fields are valid; half scales are finite small values.
  std::array<std::array<uint8_t,256>,32> blocks{};
  require(fmt.bytes<=256,"quant block bound");
  for(size_t k=0;k<blocks.size();++k){
   for(size_t j=0;j<fmt.bytes;++j)blocks[k][j]=uint8_t(mix(seed+k*257+j));
   size_t scale=type==iq3::Type::Q6_K?208:0;
   uint16_t half=type==iq3::Type::Q6_K?uint16_t(0x0010+(k%4)):uint16_t(0x0400+(k%4)*32);
   blocks[k][scale]=uint8_t(half);blocks[k][scale+1]=uint8_t(half>>8);
  }
  for(size_t j=0;j<n;){
   size_t absolute=off+j,within=absolute%fmt.bytes;
   size_t take=std::min(n-j,size_t(fmt.bytes)-within);
   std::memcpy(out.data()+j,blocks[(absolute/fmt.bytes)%32].data()+within,take);j+=take;
  }
 }
 return out;
}
}
