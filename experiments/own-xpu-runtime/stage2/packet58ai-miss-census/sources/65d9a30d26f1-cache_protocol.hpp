#pragma once
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58ai-miss-census/sources/720c174a6411-cache_table.hpp"
#include <optional>
// Lab-authored two-phase protocol. Idea: Niko1221 / Strata hot-expert cache.
// Planning mutates only unpublished CPU metadata. Hardware adapters supply the
// completion facts; no boolean here substitutes for a real native event query.
namespace p58v {
struct Protocol {
  enum class State { idle, planned, filling };
  State state=State::idle;
  bool running=false;
  std::optional<p58::Plan> plan;
  uint64_t ticket=0;
  void begin() {
    if(running)throw std::logic_error("position already running");running=true;
  }
  void end(bool complete) {
    if(!running||!complete)throw std::logic_error("position still reads cache");running=false;
  }
  void prepare(p58::Cache& cache,const std::vector<uint32_t>& routes) {
    if(!running||state!=State::idle)throw std::logic_error("plan requires running next position and free transaction");
    plan=cache.prepare(routes);state=State::planned;
  }
  std::vector<p58::Entry> revoked(const p58::Cache& cache) const {
    if(running||state!=State::planned)throw std::logic_error("victim referenced by in-flight position");
    auto table=plan->table;
    for(const auto& f:plan->fills) {
      const auto& e=cache.experts().at(f.expert);
      table[f.expert]={e.host_gate,e.host_up,e.host_down,table[f.expert].generation};
    }
    return table;
  }
  void submitted(bool publication_complete,uint64_t event) {
    if(running||state!=State::planned||!publication_complete)throw std::logic_error("fill before host-pointer publication");
    ticket=event;state=State::filling;
  }
  bool may_publish(bool complete) const {return !running&&state==State::filling&&complete;}
  void commit(p58::Cache& cache,bool complete,bool publication_complete) {
    if(!may_publish(complete)||!publication_complete)throw std::logic_error("premature device-pointer publication");
    cache.commit(plan->epoch,true,true);plan.reset();ticket=0;state=State::idle;
  }
};
}
