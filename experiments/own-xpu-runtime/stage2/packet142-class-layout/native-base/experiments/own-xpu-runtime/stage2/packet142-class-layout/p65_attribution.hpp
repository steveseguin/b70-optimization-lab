#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet142-class-layout/kernel_guard.hpp"
#line 1 "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet136-record-bundle/p65_attribution.hpp"
#pragma once
#include <map>
#include <string>
namespace p65timing {
inline bool sample(int fixture) { return fixture >= 9 && fixture <= 16; }
// Same precedence as packet57's moe_experts category, across every real layer.
inline bool routed_class(const std::string& label) {
 if(!label.starts_with("blk."))return false;
 if(label.find("shexp")!=std::string::npos||label.find("shared")!=std::string::npos)return false;
 if(label.find("hc.")!=std::string::npos||label.find("norm")!=std::string::npos||label.find("final.")!=std::string::npos||label.find("merge.")!=std::string::npos)return false;
 for(const char* needle:{"gather","moe","exps","expert","router","route","ffn."})
  if(label.find(needle)!=std::string::npos)return true;
 return false;
}
struct Site {std::string label;int fixture=0,position=-1;bool speculative=false;unsigned long long half=0;};
struct Recorder {
 bool enabled=false;unsigned long long next_half=0;Site current;
 std::map<unsigned long long,Site> events;
 bool active() const {return enabled&&sample(current.fixture)&&routed_class(current.label);}
 void begin(int fixture,int position,bool speculative){current={"",fixture,position,speculative,++next_half};}
 void record(unsigned long long event){if(active())events.emplace(event,current);}
};
}
