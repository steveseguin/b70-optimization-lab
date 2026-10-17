#pragma once
#include <map>
#include <string>
// Packet57 observation only. Device timestamps never compare different cards.
namespace p57 {
inline bool sample(int fixture) { return fixture>=9 && fixture<=16; }
inline bool selected(const std::string& label) {
 if(label.starts_with("draft.")||label.starts_with("transfer."))return true;
 for(const char* prefix:{"blk.19.","blk.22.","blk.23.","blk.24."})
  if(label.starts_with(prefix))return true;
 return label=="embedding" || label.starts_with("ple.");
}
inline std::string category(std::string label) {
 if(label.find("transfer")!=std::string::npos)return "transfers";
 if(label.ends_with("argmax"))return "argmax";
 if(label.ends_with("logits"))return "head_prefix";
 if(label.find("embedding")!=std::string::npos||label.find("ple.")!=std::string::npos)return "embedding_ple";
 if(label.find("shexp")!=std::string::npos||label.find("shared")!=std::string::npos)return "shared_expert";
 if(label.find("hc.")!=std::string::npos||label.find("norm")!=std::string::npos||label.find("final.")!=std::string::npos||label.find("merge.")!=std::string::npos)return "hc_norm_merge";
 if(label.find("gather")!=std::string::npos||label.find("moe")!=std::string::npos||label.find("exps")!=std::string::npos||label.find("expert")!=std::string::npos||label.find("router")!=std::string::npos||label.find("route")!=std::string::npos||label.find("ffn.")!=std::string::npos)return "moe_experts";
 if(label.find("attention")!=std::string::npos||label.find("qsa")!=std::string::npos||label.find("gdn")!=std::string::npos||label.find("attn")!=std::string::npos)return "attention";
 return "other";
}
struct Site {std::string label;int fixture=0,position=-1;bool speculative=false;};
struct Recorder {
 bool enabled=false;int generation_origin=-1;Site current;std::map<unsigned long long,Site> events;
 bool active()const{return enabled&&sample(current.fixture)&&selected(current.label);}
 void record(unsigned long long event){if(active())events.emplace(event,current);}
};
}
