#pragma once
#include <string>
namespace packet37 {
inline std::string gemv_incumbent(const std::string& key){
 if(key=="expsgate")return "p28.paired.wg32";
 if(key=="gdn.qkv")return "p28.dense.wg32";
 if(key=="gdn.z")return "p28.dense.wg32";
 if(key=="qsa.qgate")return "p28.dense.wg32";
 if(key=="qsa.k")return "p28.dense.rows4";
 if(key=="qsa.v")return "p28.dense.rows4";
 if(key=="attention")return "p28.dense.wg32";
 if(key=="ple.key")return "p28.dense.wg32";
 if(key=="ple.value")return "p28.dense.wg32";
 if(key=="logits")return "p28.dense.wg32";
 if(key=="hc.a.gate")return "p28.dense.wg32";
 if(key=="hc.f.gate")return "p28.dense.wg32";
 if(key=="final.gate")return "p28.dense.wg32";
 if(key=="final.low")return "p28.dense.rows4";
 if(key=="qsa.iq")return "p28.dense.rows4";
 if(key=="qsa.ik")return "p28.dense.wg32";
 if(key=="shexpdown")return "p28.dense.wg32";
 return "r5";
}
inline int class_incumbent(const std::string& key){
 if(key=="hc.a.norm")return 1;
 if(key=="hc.f.norm")return 1;
 if(key=="final.norm")return 1;
 if(key=="ple.kn")return 1;
 if(key=="ple.qn")return 1;
 if(key=="ple.cn")return 1;
 if(key=="gdn.norm")return 0;
 if(key=="gdn.recurrence")return 2;
 if(key=="qsa.prepare")return 0;
 if(key=="qsa.pool")return 0;
 if(key=="qsa.select")return 2;
 if(key=="qsa.attention")return 0;
 if(key=="attn.combine")return 1;
 if(key=="ffn.combine")return 1;
 if(key=="route")return 1;
 if(key=="gather")return 1;
 if(key=="argmax")return 2;
 if(key=="streams")return 1;
 if(key=="ple.add")return 1;
 return key=="norm"||key=="hc.combine_norm"||key=="route_gather"?1:0;
}
}
