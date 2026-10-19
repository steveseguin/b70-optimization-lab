#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet165-warm-prefill/two-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet131-snapshot-banks/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet165-warm-prefill/two-card/native-source/repo/experiments/own-xpu-runtime/stage2/packet131-snapshot-banks/engine_fusion.hpp"
// Included in Engine. Empty sites remain in the plan for stable recapture indexes.
 bool other_fused_site(const flash::Launch& l){
  if(!sealed_selection.choices.contains("other_fusion")||sealed_selection.choices.at("other_fusion")!="fused"||a.mini)return false;
  require(a.memory=="resident"&&a.nongemv=="parallel"&&p.g.h==2560&&p.g.mid==640&&p.g.top==10,"p109 exact production geometry");
  const auto cls=packet26::Dispatch::class_name(l.label);int c=l.card;
  const auto prefix=l.label.substr(0,l.label.size()-cls.size());
  auto id=[&](const std::string& n){return buffers[c].at(n).id;};
  if(cls=="route"){
   require(sealed_selection.choices.at("route")=="route-fast","p109 requires selected single-WG route");
   const auto& bound=prepared.at(&l);
   finish(c,p109::route_activation(dev(c),bound.spec,bound.bindings,{id(prefix+"shexpgate"),id(prefix+"shexpup"),id(prefix+"shexpact")}),false);
   return true;
  }
  if(cls=="shexpact"||l.op=="moe_combine")return true;
  if(cls=="shexpdown"){
   require(l.op=="gemv"&&l.shape[1]==2560&&l.shape[2]==640&&variant(l)==6&&flash::grid_type(w.directory.at(l.weights[0]).grid)==iq3::Type::Q8_0,"p109 shared-down production ABI");
   auto m=matrix(l);
   finish(c,p109::shared_down(dev(c),{m.w,m.x,m.y,id(prefix+"expsdown"),id(prefix+"prob"),mixture_out[c],id(prefix+"shared_gate"),one[c],id(prefix+"moe"),id("error"),id("position"),id("active")},p.g.context),true);
   return true;
  }
  return false;
 }
