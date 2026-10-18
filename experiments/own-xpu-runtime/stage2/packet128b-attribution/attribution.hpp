#pragma once
#include <map>
#include <string>
// Packet57 observation only. Device timestamps never compare different cards.
namespace p57 {
inline bool sample(int fixture) { return fixture>=9 && fixture<=16; }
inline const char* layer_boundary(const std::string& label) {
 if(label=="blk.0.hc.a.norm"||label=="blk.24.hc.a.norm")return "begin";
 if(label=="blk.23.ffn.combine"||label=="blk.47.ffn.combine")return "end";
 return "";
}
inline bool selected(const std::string&) { return true; }
inline std::string category(std::string label) {
 if(label.starts_with("head.suffix"))return "target_head_suffix";
 if(label.starts_with("head.pack"))return "target_head_merge";
 if(label.starts_with("snapshot."))return "snapshot_capture";
 if(label.starts_with("rollback."))return "rollback";
 if(label.find("transfer")!=std::string::npos)return "transfers";
 if(label=="argmax")return "target_head_prefix";
 if(label.ends_with("argmax"))return "argmax";
 if(label=="logits")return "target_head_prefix";
 if(label.starts_with("final."))return "final_norm_merge";
 if(label.ends_with("logits"))return "head_prefix";
 if(label.find("embedding")!=std::string::npos||label.find("ple.")!=std::string::npos)return "embedding_ple";
 if(label.find("shexp")!=std::string::npos||label.find("shared")!=std::string::npos)return "shared_expert";
 if(label.find("hc.")!=std::string::npos||label.find("norm")!=std::string::npos||label.find("final.")!=std::string::npos||label.find("merge.")!=std::string::npos)return "hc_norm_merge";
 if(label.find("gather")!=std::string::npos||label.find("moe")!=std::string::npos||label.find("exps")!=std::string::npos||label.find("expert")!=std::string::npos||label.find("router")!=std::string::npos||label.find("route")!=std::string::npos||label.find("ffn.")!=std::string::npos)return "moe_experts";
 if(label.find("attention")!=std::string::npos||label.find("qsa")!=std::string::npos||label.find("gdn")!=std::string::npos||label.find("attn")!=std::string::npos)return "attention";
 return "other";
}
struct Site {std::string label;int fixture=0,position=-1;bool speculative=false;const char* queue="compute";};
struct Recorder {
 bool enabled=false;int request=0;int generation_origin=-1;Site current;std::map<unsigned long long,Site> events;
 bool sampling()const{return enabled&&sample(current.fixture);}
 bool active()const{return sampling()&&selected(current.label);}
 void record(unsigned long long event){if(active())events.emplace(event,current);}
};
}
