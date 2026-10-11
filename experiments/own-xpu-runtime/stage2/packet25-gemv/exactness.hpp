#pragma once
#include "fixtures.hpp"
#include <iomanip>
#include <sstream>
namespace p25 {
inline constexpr char gate_policy[] = "host finite (including signed zero and denormals) and infinity: exact bits; host NaN: device NaN, any encoding; candidate: exact current-card bits everywhere; nonfinite values are fatal sticky model errors, not model outputs";
inline bool nan_bits(uint32_t v, bool bf=false){return bf ? (v&0x7fff)>0x7f80 : (v&0x7fffffff)>0x7f800000;}
inline bool finite_bits(uint32_t v, bool bf=false){return bf ? (v&0x7f80)!=0x7f80 : (v&0x7f800000)!=0x7f800000;}
struct Gate {
 size_t host_failures=0, finite_failures=0, infinity_failures=0, nan_class_failures=0, nan_encoding_differences=0, current_differences=0;
 bool passed()const{return !host_failures&&!current_differences;}
};
inline Gate compare(const Result& host,const Result& card,const Result* current=nullptr){
 Gate g;
 for(unsigned bf=0;bf<2;++bf)for(unsigned peer=0;peer<2;++peer){
  uint32_t h=bf?host.bf[peer]:host.fp[peer],d=bf?card.bf[peer]:card.fp[peer];
  bool host_ok=h==d;
  if(nan_bits(h,bf)){host_ok=nan_bits(d,bf);if(host_ok&&h!=d)++g.nan_encoding_differences;}
  bool same=!current||d==(bf?current->bf[peer]:current->fp[peer]);
  if(!same)++g.current_differences;
  if(!host_ok){++g.host_failures;if(nan_bits(h,bf))++g.nan_class_failures;else if(!finite_bits(h,bf))++g.infinity_failures;}
  if(finite_bits(h,bf)&&(!host_ok||!same))++g.finite_failures;
 }
 return g;
}
inline void accumulate(Gate& a,const Gate& b){a.host_failures+=b.host_failures;a.finite_failures+=b.finite_failures;a.infinity_failures+=b.infinity_failures;a.nan_class_failures+=b.nan_class_failures;a.nan_encoding_differences+=b.nan_encoding_differences;a.current_differences+=b.current_differences;}
inline std::string hex_bits(uint32_t v,unsigned width){std::ostringstream s;s<<'"'<<"0x"<<std::hex<<std::setfill('0')<<std::setw(width)<<v<<'"';return s.str();}
inline void result_bits(std::ostream& out,const Result& r){out<<"{\"fp32\":["<<hex_bits(r.fp[0],8)<<","<<hex_bits(r.fp[1],8)<<"],\"bf16\":["<<hex_bits(r.bf[0],4)<<","<<hex_bits(r.bf[1],4)<<"]}";}
inline void gate_fields(std::ostream& out,const Gate& g){out<<"\"host_gate_failures\":"<<g.host_failures<<",\"finite_element_gate_failures\":"<<g.finite_failures<<",\"infinity_gate_failures\":"<<g.infinity_failures<<",\"nan_class_gate_failures\":"<<g.nan_class_failures<<",\"nan_encoding_differences_vs_host\":"<<g.nan_encoding_differences<<",\"candidate_current_bit_differences\":"<<g.current_differences;}
inline unsigned gate_tests(){
 auto check=[](bool ok){if(!ok)throw std::runtime_error("exceptional gate regression");};
 Result h{},d{};h.fp[0]=0x7fc10000;h.bf[0]=0x7fc1;d.fp[0]=0xffc00000;d.bf[0]=0xffc0;
 auto g=compare(h,d);check(g.passed()&&g.nan_encoding_differences==2&&!g.finite_failures);
 auto c=d;check(compare(h,d,&c).passed());c.fp[0]=0x7fc20000;check(!compare(h,d,&c).passed());
 d.fp[0]=0x7f800000;check(compare(h,d).nan_class_failures==1);
 h={};d={};d.fp[0]=0x80000000;d.bf[0]=0x8000;check(compare(h,d).finite_failures==2);
 h.fp[0]=1;h.bf[0]=1;d={};check(compare(h,d).finite_failures==2);
 h.fp[0]=0x3f800000;h.bf[0]=0x3f80;d=h;d.fp[0]++;check(compare(h,d).finite_failures==1);
 h={};h.fp[0]=0x7f800000;d=h;check(compare(h,d).passed());d.fp[0]=0xff800000;check(compare(h,d).infinity_failures==1&&!compare(h,d).finite_failures);
 h={};d=h;c=h;c.fp[0]=1;check(compare(h,d,&c).finite_failures==1);
 return 10;
}
}
