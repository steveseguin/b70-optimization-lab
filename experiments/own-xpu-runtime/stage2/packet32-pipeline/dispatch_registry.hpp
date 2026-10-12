#pragma once
#include <map>
#include <set>
#include <string>
#include <stdexcept>
namespace packet29 {
using Table=std::map<std::string,std::string>;
inline void validate_dispatch(const Table& classes,const Table& gemv,const Table& fusions){
 const std::map<std::string,std::set<std::string>> known_classes{
  {"hc.a.norm",{"packet18","specialised"}},
  {"hc.f.norm",{"packet18","specialised"}},
  {"final.norm",{"packet18","specialised"}},
  {"ple.kn",{"packet18","specialised"}},
  {"ple.qn",{"packet18","specialised"}},
  {"ple.cn",{"packet18","specialised"}},
  {"gdn.norm",{"packet18","specialised"}},
  {"gdn.recurrence",{"packet18","specialised","round2"}},
  {"qsa.prepare",{"packet18","specialised"}},
  {"qsa.pool",{"packet18","specialised"}},
  {"qsa.select",{"packet18","specialised","round2"}},
  {"qsa.attention",{"packet18","specialised","round2"}},
  {"attn.combine",{"packet18","specialised"}},
  {"ffn.combine",{"packet18","specialised"}},
  {"route",{"packet18","specialised","round2"}},
  {"gather",{"packet18","specialised"}},
  {"argmax",{"packet18","specialised","round2"}},
  {"streams",{"packet18","specialised"}},
  {"ple.add",{"packet18","specialised"}},
  {"norm",{"packet18","specialised"}},
 };
 for(const auto& [key,value]:classes){auto i=known_classes.find(key);if(i==known_classes.end()||!i->second.contains(value))throw std::invalid_argument("unknown classes class/kernel: "+key+"/"+value);}
 const std::map<std::string,std::set<std::string>> known_gemv{
  {"expsgate",{"r5","p25.rows4","p25.wg32","p25.private_decode","p25.paired_input","p25.half_table","p27.fp32_input","p28.private.rows4","p28.private.wg32","p28.shared.rows4","p28.shared.wg32","p28.paired.rows4","p28.paired.wg32"}},
  {"expsdown",{"r5","p25.rows4","p25.wg32","p25.private_decode","p25.wide8","p27.packed64","p27.rows2sg","p27.fp32_input","p28.private.rows4","p28.private.wg32","p28.shared.rows4","p28.shared.wg32","p29.down.wg32","p29.down.rows4"}},
  {"gdn.qkv",{"r5","p25.rows4","p25.scale8","p25.wide8","p27.packed64","p27.fp32_input","p28.dense.rows4","p28.dense.wg32"}},
  {"gdn.z",{"r5","p25.rows4","p25.scale8","p25.wide8","p27.packed64","p27.fp32_input","p28.dense.rows4","p28.dense.wg32"}},
  {"qsa.qgate",{"r5","p25.rows4","p25.scale8","p25.wide8","p27.packed64","p27.fp32_input","p28.dense.rows4","p28.dense.wg32"}},
  {"qsa.k",{"r5","p25.rows4","p25.scale8","p25.wide8","p27.packed64","p27.fp32_input","p28.dense.rows4","p28.dense.wg32"}},
  {"qsa.v",{"r5","p25.rows4","p25.scale8","p25.wide8","p27.packed64","p27.fp32_input","p28.dense.rows4","p28.dense.wg32"}},
  {"attention",{"r5","p25.rows4","p25.scale8","p25.wide8","p27.packed64","p27.fp32_input","p28.dense.rows4","p28.dense.wg32"}},
  {"ple.key",{"r5","p25.rows4","p25.scale8","p25.wide8","p27.packed64","p27.fp32_input","p28.dense.rows4","p28.dense.wg32"}},
  {"ple.value",{"r5","p25.rows4","p25.scale8","p25.wide8","p27.packed64","p27.fp32_input","p28.dense.rows4","p28.dense.wg32"}},
  {"hc.a.gate",{"r5","p25.rows4","p25.scale8","p25.wide8","p27.packed64","p27.fp32_input","p28.dense.rows4","p28.dense.wg32"}},
  {"hc.a.low",{"r5","p25.rows4","p25.scale8","p25.wide8","p27.packed64","p27.fp32_input","p28.dense.rows4","p28.dense.wg32"}},
  {"hc.a.inject",{"r5","p28.dense.rows4","p28.dense.wg32"}},
  {"hc.f.gate",{"r5","p25.rows4","p25.scale8","p25.wide8","p27.packed64","p27.fp32_input","p28.dense.rows4","p28.dense.wg32"}},
  {"hc.f.low",{"r5","p25.rows4","p25.scale8","p25.wide8","p27.packed64","p27.fp32_input","p28.dense.rows4","p28.dense.wg32"}},
  {"hc.f.inject",{"r5","p28.dense.rows4","p28.dense.wg32"}},
  {"final.gate",{"r5","p25.rows4","p25.scale8","p25.wide8","p27.packed64","p27.fp32_input","p28.dense.rows4","p28.dense.wg32"}},
  {"final.low",{"r5","p25.rows4","p25.scale8","p25.wide8","p27.packed64","p27.fp32_input","p28.dense.rows4","p28.dense.wg32"}},
  {"qsa.iq",{"r5","p28.dense.rows4","p28.dense.wg32"}},
  {"qsa.ik",{"r5","p28.dense.rows4","p28.dense.wg32"}},
  {"router",{"r5","p28.dense.rows4","p28.dense.wg32"}},
  {"gdn.a",{"r5","p28.dense.rows4","p28.dense.wg32"}},
  {"gdn.b",{"r5","p28.dense.rows4","p28.dense.wg32"}},
  {"shexpgate",{"r5","p25.rows4","p25.scale8","p25.wide8","p27.packed64","p27.fp32_input","p28.dense.rows4","p28.dense.wg32"}},
  {"shexpup",{"r5","p25.rows4","p25.scale8","p25.wide8","p27.packed64","p27.fp32_input","p28.dense.rows4","p28.dense.wg32"}},
  {"shexpdown",{"r5","p25.rows4","p25.scale8","p25.wide8","p27.packed64","p27.fp32_input","p28.dense.rows4","p28.dense.wg32"}},
  {"shared_gate",{"r5","p28.dense.rows4","p28.dense.wg32"}},
  {"logits",{"r5","p25.rows4","p25.scale8","p25.wide8","p27.packed64","p27.fp32_input","p28.dense.rows4","p28.dense.wg32"}},
  {"hc.gate",{"r5","p25.rows4","p25.scale8","p25.wide8","p27.packed64","p27.fp32_input","p28.dense.rows4","p28.dense.wg32"}},
  {"hc.low",{"r5","p25.rows4","p25.scale8","p25.wide8","p27.packed64","p27.fp32_input","p28.dense.rows4","p28.dense.wg32"}},
 };
 for(const auto& [key,value]:gemv){auto i=known_gemv.find(key);if(i==known_gemv.end()||!i->second.contains(value))throw std::invalid_argument("unknown gemv class/kernel: "+key+"/"+value);}
 const std::map<std::string,std::set<std::string>> known_fusions{
  {"attn.combine+norm",{"packet18","specialised"}},
  {"ffn.combine+norm",{"packet18","specialised"}},
  {"route+gather",{"packet18","specialised","round2"}},
  {"small.hc",{"packet18","round2"}},
  {"small.gdn.ab",{"packet18","round2"}},
  {"small.ffn",{"packet18","round2"}},
 };
 for(const auto& [key,value]:fusions){auto i=known_fusions.find(key);if(i==known_fusions.end()||!i->second.contains(value))throw std::invalid_argument("unknown fusions class/kernel: "+key+"/"+value);}
 if(auto f=fusions.find("attn.combine+norm");f!=fusions.end()&&f->second!="packet18"){
  if(auto i=classes.find("attn.combine");i!=classes.end()&&i->second!="specialised")throw std::invalid_argument("fusion conflicts with classes: attn.combine+norm / attn.combine");
  if(auto i=classes.find("hc.a.norm");i!=classes.end()&&i->second!="specialised")throw std::invalid_argument("fusion conflicts with classes: attn.combine+norm / hc.a.norm");
 }
 if(auto f=fusions.find("ffn.combine+norm");f!=fusions.end()&&f->second!="packet18"){
  if(auto i=classes.find("ffn.combine");i!=classes.end()&&i->second!="specialised")throw std::invalid_argument("fusion conflicts with classes: ffn.combine+norm / ffn.combine");
  if(auto i=classes.find("hc.f.norm");i!=classes.end()&&i->second!="specialised")throw std::invalid_argument("fusion conflicts with classes: ffn.combine+norm / hc.f.norm");
 }
 if(auto f=fusions.find("route+gather");f!=fusions.end()&&f->second!="packet18"){
  if(auto i=classes.find("route");i!=classes.end()&&i->second!=(f->second=="round2"?"round2":"specialised"))throw std::invalid_argument("fusion conflicts with classes: route+gather / route");
  if(auto i=classes.find("gather");i!=classes.end()&&i->second!="specialised")throw std::invalid_argument("fusion conflicts with classes: route+gather / gather");
 }
 if(auto f=fusions.find("small.hc");f!=fusions.end()&&f->second!="packet18"){
  if(auto i=gemv.find("hc.a.low");i!=gemv.end()&&i->second!="r5")throw std::invalid_argument("fusion conflicts with gemv: small.hc / hc.a.low");
  if(auto i=gemv.find("hc.f.low");i!=gemv.end()&&i->second!="r5")throw std::invalid_argument("fusion conflicts with gemv: small.hc / hc.f.low");
  if(auto i=gemv.find("hc.a.inject");i!=gemv.end()&&i->second!="r5")throw std::invalid_argument("fusion conflicts with gemv: small.hc / hc.a.inject");
  if(auto i=gemv.find("hc.f.inject");i!=gemv.end()&&i->second!="r5")throw std::invalid_argument("fusion conflicts with gemv: small.hc / hc.f.inject");
  if(auto i=gemv.find("hc.low");i!=gemv.end()&&i->second!="r5")throw std::invalid_argument("fusion conflicts with gemv: small.hc / hc.low");
 }
 if(auto f=fusions.find("small.gdn.ab");f!=fusions.end()&&f->second!="packet18"){
  if(auto i=gemv.find("gdn.a");i!=gemv.end()&&i->second!="r5")throw std::invalid_argument("fusion conflicts with gemv: small.gdn.ab / gdn.a");
  if(auto i=gemv.find("gdn.b");i!=gemv.end()&&i->second!="r5")throw std::invalid_argument("fusion conflicts with gemv: small.gdn.ab / gdn.b");
 }
 if(auto f=fusions.find("small.ffn");f!=fusions.end()&&f->second!="packet18"){
  if(auto i=gemv.find("router");i!=gemv.end()&&i->second!="r5")throw std::invalid_argument("fusion conflicts with gemv: small.ffn / router");
  if(auto i=gemv.find("shexpgate");i!=gemv.end()&&i->second!="r5")throw std::invalid_argument("fusion conflicts with gemv: small.ffn / shexpgate");
  if(auto i=gemv.find("shexpup");i!=gemv.end()&&i->second!="r5")throw std::invalid_argument("fusion conflicts with gemv: small.ffn / shexpup");
  if(auto i=gemv.find("shared_gate");i!=gemv.end()&&i->second!="r5")throw std::invalid_argument("fusion conflicts with gemv: small.ffn / shared_gate");
 }
}
}
