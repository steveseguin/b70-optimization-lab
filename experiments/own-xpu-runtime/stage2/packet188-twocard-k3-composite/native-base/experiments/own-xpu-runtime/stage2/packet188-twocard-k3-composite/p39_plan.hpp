#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet188-twocard-k3-composite/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/p39_plan.hpp"
#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet188-twocard-k3-composite/build/checked/experiments/own-xpu-runtime/stage2/packet188-twocard-k3-composite/p39_submit.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet188-twocard-k3-composite/build/checked/experiments/own-xpu-runtime/stage2/packet188-twocard-k3-composite/dispatch.hpp"
namespace p39 {
inline bool tagged(const flash::Launch&l){return l.parameter>=plan_tag&&l.parameter<plan_tag+8;}
inline Kind kind(const flash::Launch&l){return Kind(l.parameter-plan_tag);}
template<class TypeOf>void fuse_plan(flash::Plan&p,TypeOf type_of){
 if(p.g.h!=2560)return;
 const auto enabled=[](const std::string&key){return packet26::dispatch.fusion_choice(key)=="p39.epilogue";};
 std::map<std::string,flash::Launch> by_label;for(const auto&l:p.launches)by_label.emplace(l.label,l);
 std::set<std::string> removed;std::vector<flash::Launch> out;
 auto append=[](auto&dest,const auto&source){for(const auto&v:source)if(std::find(dest.begin(),dest.end(),v)==dest.end())dest.push_back(v);};
 for(auto l:p.launches){if(removed.count(l.label))continue;auto cls=packet26::Dispatch::class_name(l.label),prefix=l.label.substr(0,l.label.size()-cls.size());
  auto absorb=[&](const std::string&name){auto i=by_label.find(name);if(i==by_label.end()||i->second.card!=l.card)throw std::invalid_argument("p39 missing same-card tail: "+name);append(l.inputs,i->second.inputs);append(l.outputs,i->second.outputs);removed.insert(name);};
  auto tag=[&](Kind k){l.parameter=plan_tag+int(k);};
  if(l.op=="expert_gate_up"&&cls=="expsgate"){
   auto type=type_of(l.weights[0]);auto key=type==iq3::Type::IQ2_S?"expert-checks-iq2":type==iq3::Type::IQ3_S?"expert-checks-iq3":"";
   // Packed gate and p39 checks are independent alternatives for this GEMV.
   // A K2-selected packed gate keeps its original checks until that combination is measured.
   if(*key&&enabled(key)&&packet26::dispatch.gemv_for(l.label)!="p42.gate.packed"){absorb(prefix+"expsgate.check");absorb(prefix+"expsup.check");tag(Kind::expert_checks);}
  }else if(cls=="expsdown"&&enabled("down-status")){absorb(prefix+"expsdown.check");tag(Kind::down_status);}
  else if((cls=="hc.a.low"||cls=="hc.f.low"||cls=="final.low")&&enabled("hc-low-act")){absorb(l.label.substr(0,l.label.size()-3)+"act");tag(Kind::silu_div4);}
  // SPEED1: keep the primitive shared-up site and activation separate. The
  // selected small.ffn tuple owns router/gate/up/shared_gate together; absorbing
  // only shared-up made that tuple unavailable and stranded its siblings on r5.
  // Both shared-up epilogues remain available as isolated K2 fixtures, but are
  // disabled in production plans until the complete composition is measured.
  else if(cls=="attention"&&l.op=="gemv"&&type_of(l.weights[0])==iq3::Type::Q6_K&&enabled("attention-combine")){absorb(prefix+"attn.combine");tag(Kind::attention_combine);}
  else if(cls=="shexpdown"&&enabled("shared-down-combine")){
   // The gate and existing ten-expert mixture precede this GEMV; the latter
   // remains a separate Device::compute in Engine::linear, with all hooks.
   auto gate=by_label.at(prefix+"shared_gate");out.push_back(gate);removed.insert(gate.label);
   absorb(prefix+"moe");absorb(prefix+"ffn.combine");tag(Kind::shared_combine);
   // Keep the old layer-end identity on the surviving fused launch so the
   // snapshot, cancellation, streaming release and p-1 handoff hooks survive.
   l.label=prefix+"ffn.combine";
  }
  out.push_back(std::move(l));
 }
 p.launches=std::move(out);
}
}
