#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet188-twocard-k3-composite/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/p59c_select.hpp"
#pragma once
// Init-time registry. No per-token file reads, environment choices or hot lookup.
#include <map>
#include <string>
#include <stdexcept>
namespace p59c {
inline const std::map<std::string,std::string> sites{
 {"blk.0.qsa.qgate","qgate"},{"blk.0.qsa.attention","qsa_attention"},
 {"blk.0.expsgate","gate_up"},{"blk.0.expsdown","down"},
 {"blk.0.attention","attention_output"},
 {"blk.0.hc.a.low","hc_a_low"},{"blk.0.hc.f.low","hc_f_low"},{"final.low","hc_final_low"},
 {"blk.0.hc.a.gate","hc_a_gate"},{"blk.0.hc.f.gate","hc_f_gate"},{"final.gate","hc_final_gate"},
 {"blk.0.hc.a.inject","hc_a_inject"},{"blk.0.hc.f.inject","hc_f_inject"},
 {"blk.0.route","route"},
 {"merge.embedding_norm","embedding_norm"},{"merge.hidden_norm","hidden_norm"},
 {"blk.0.hc.a.norm","hc_a_norm"},{"blk.0.hc.f.norm","hc_f_norm"},{"final.norm","final_norm"},
 {"merge.projected","hidden_projection"},{"merge.embedding_projected","embedding_projection"},
 {"blk.0.qsa.k","qsa_k"},{"blk.0.qsa.v","qsa_v"},{"blk.0.qsa.iq","qsa_iq"},{"blk.0.qsa.ik","qsa_ik"},
 {"blk.0.router","router"},{"blk.0.shexpgate","shared_gate"},{"blk.0.shexpup","shared_up"},
 {"blk.0.shexpdown","shared_down"},{"blk.0.shared_gate","shared_router"}
};
// Consumer label -> fusion switch. Producer remains independently selectable.
inline const std::map<std::string,std::string> consumers{
 {"blk.0.hc.a.act","fuse_hc_a_low"},{"blk.0.hc.f.act","fuse_hc_f_low"},{"final.act","fuse_hc_final_low"},
 {"blk.0.hc.a.mix","fuse_hc_a_mix"},{"blk.0.hc.f.mix","fuse_hc_f_mix"},{"final.mix","fuse_hc_final_mix"},
 {"blk.0.expsact","fuse_expert_activation"},{"blk.0.shexpact","fuse_shared_activation"},
 {"blk.0.attn.combine","fuse_attention_combine"},{"merge.add","fuse_hidden_merge"}
};
inline const std::map<std::string,std::string> dependencies{
 {"fuse_hc_a_low","hc_a_low"},{"fuse_hc_f_low","hc_f_low"},{"fuse_hc_final_low","hc_final_low"},
 {"fuse_hc_a_mix","hc_a_gate"},{"fuse_hc_f_mix","hc_f_gate"},{"fuse_hc_final_mix","hc_final_gate"},
 {"fuse_expert_activation","gate_up"},{"fuse_shared_activation","shared_up"},
 {"fuse_attention_combine","attention_output"},{"fuse_hidden_merge","hidden_projection"}
};
inline std::map<std::string,std::string> defaults(){
 std::map<std::string,std::string> m;for(auto&[label,key]:sites)m.emplace(key,"production");
 for(auto&[key,producer]:dependencies)m.emplace(key,"production");m.emplace("head_format","production");m.emplace("head_prefix","production");return m;
}
inline void validate(const std::map<std::string,std::string>&m){
 auto registered=defaults();if(m.size()!=registered.size())throw std::invalid_argument("p59c incomplete draft selection");
 for(auto&[key,value]:m)if(!registered.contains(key)||(key=="head_format"?(value!="production"&&value!="q4-g32"):key=="head_prefix"?(value!="production"&&value!="p114-80128"&&value!="coverage990"&&value!="coverage985"):(value!="production"&&value!="packet59")))throw std::invalid_argument("p59c unknown draft choice: "+key);
 if(m.at("head_format")!="production"&&m.at("head_prefix")!="production")throw std::invalid_argument("p83 unregistered combined draft head");
 for(auto&[key,producer]:dependencies)if(m.at(key)=="packet59"&&m.at(producer)!="packet59")throw std::invalid_argument("p59c fusion requires packet59 producer: "+key);
}
}
