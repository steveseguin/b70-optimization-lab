#define OWN_RT_HOST_ONLY
#include "predecoded.hpp"
#include <array>
#include <cstdio>
#include <random>

int main() {
 using namespace iq3_predecoded;
 std::mt19937 gen(1701);uint64_t values=0,rows=0;
 const std::array<uint16_t,12> halves{0,0x8000,1,0x8001,0x3c00,0xbc00,0x7bff,0xfbff,0x7c00,0xfc00,0x7e01,0xfe01};
 for(unsigned trial=0;trial<4096;++trial) {
  std::array<uint8_t,98> packed{};std::array<uint8_t,266> cached{};
  for(auto& b:packed)b=uint8_t(gen());
  const uint16_t half=trial<halves.size()?halves[trial]:uint16_t(gen());
  packed[0]=uint8_t(half);packed[1]=uint8_t(half>>8);expand_block(packed.data(),cached.data());
  const float d=iq3::half(half);
  for(unsigned group=0;group<8;++group) for(unsigned lane=0;lane<32;++lane) {
   const float a=packed_element(packed.data(),d,group,lane),b=element(cached.data(),d,group,lane);
   if(std::bit_cast<uint32_t>(a)!=std::bit_cast<uint32_t>(b)) {
    std::printf("value mismatch half=%04x group=%u lane=%u %08x %08x\n",half,group,lane,std::bit_cast<uint32_t>(a),std::bit_cast<uint32_t>(b));return 1;
   }
   ++values;
  }
 }
 for(uint32_t columns:{256u,768u,2560u,4096u}) {
  const size_t old_row=size_t(columns/256)*98;
  std::vector<uint8_t> packed(13*old_row);for(auto& b:packed)b=uint8_t(gen());
  for(size_t b=0;b<packed.size()/98;++b){const uint16_t h=uint16_t(0x1000+(gen()&0x4fff));packed[b*98]=uint8_t(h);packed[b*98+1]=uint8_t(h>>8);}
  const auto cached=expand(packed.data(),packed.size(),columns);
  std::vector<float>x(columns);for(auto& f:x)f=std::uniform_real_distribution<float>(-1,1)(gen);
  for(size_t row=0;row<13;++row) {
   const float a=host_row<false>(packed.data()+row*old_row,x.data(),columns);
   const float b=host_row<true>(cached.data()+row*row_bytes(columns),x.data(),columns);
   if(std::bit_cast<uint32_t>(a)!=std::bit_cast<uint32_t>(b)){std::printf("row mismatch columns=%u row=%zu\n",columns,row);return 1;}
   ++rows;
  }
 }
 std::printf("PASS values=%llu rows=%llu block_bytes=266 original_bytes=98\n",(unsigned long long)values,(unsigned long long)rows);
}
