// Included after frozen gsqn definitions. Candidate changes only repeated
// block half conversion/addressing, never the scalar FP expression boundaries.
namespace denseblock {
template<unsigned T> inline float block_element(const uint8_t*b,float d,float dmin,unsigned group,unsigned lane){
 static_assert(T==12||T==13||T==23);
 if constexpr(T==12||T==13){
  const auto*s=b+4;
  const unsigned scale=group<4?s[group]&63:(s[group+4]&15)|((s[group-4]>>6)<<4);
  const unsigned minimum=group<4?s[group+4]&63:(s[group+4]>>4)|((s[group]>>6)<<4);
  constexpr unsigned low_offset=T==12?16:48;
  unsigned code=(b[low_offset+(group/2)*32+lane]>>(4*(group%2)))&15;
  if constexpr(T==13)code|=((b[16+lane]>>group)&1)<<4;
  const float factor=d*float(scale);
  const float offset=dmin*float(minimum);
  const float product=factor*float(code);return product-offset;
 }else{
  constexpr int levels[]{-127,-104,-83,-65,-49,-35,-22,-10,1,13,25,38,53,69,89,113};
  const unsigned scale=((b[4+group/2]>>(4*(group%2)))&15)|(((iq3::u16(b+2)>>(2*group))&3)<<4);
  const unsigned code=(b[8+group*16+lane%16]>>(4*(lane/16)))&15;
  const float factor=d*float(int(scale)-32);
  return factor*float(levels[code]);
 }
}
template<unsigned T> inline float block_lane_sum(const gsqn::Bound&b,const iq3::Route&r,size_t row,unsigned slot,unsigned lane){
 constexpr size_t bytes=T==12?144:T==13?176:136;
 const auto*w=b.w+(size_t(r.expert_id)*b.s.rows+r.row_begin+row)*b.s.row_bytes;
 const auto*x=b.x+(b.s.per_slot?size_t(slot)*b.s.columns:0);float sum=0;
 for(size_t block=0;block<b.s.columns/256;++block){
  const auto*packed=w+block*bytes;
  const float d=iq3::half(iq3::u16(packed));
  float dmin=0;if constexpr(T==12||T==13)dmin=iq3::half(iq3::u16(packed+2));
  for(unsigned group=0;group<8;++group){
   const size_t k=block*256+group*32+lane;
   const float weight=block_element<T>(packed,d,dmin,group,lane);
   const float product=weight*iq3::bits_float(uint32_t(x[k])<<16);sum=sum+product;
  }
 }
 return sum;
}
}
