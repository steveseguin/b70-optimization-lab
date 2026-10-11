#pragma once
#include "../packet26-specialised/performance.hpp"
namespace p28 {
using iq3::Type;
struct Shape {const char* label;const char* klass;Type type;unsigned rows,k,count;bool paired;const char* timing_class;};
inline constexpr Shape shapes[]{
 {"expsgate.iq2","expsgate",Type::IQ2_S,640,2560,10,true,"expsgate"},
 {"expsgate.iq3","expsgate",Type::IQ3_S,640,2560,10,true,"expsgate"},
 {"expsdown","expsdown",Type::IQ4_NL,2560,640,10,false,"expsdown"},
 {"gdn.qkv.q6","gdn.qkv",Type::Q6_K,10240,2560,1,false,"gdn.qkv"},
 {"gdn.qkv.q8","gdn.qkv",Type::Q8_0,10240,2560,1,false,"gdn.qkv"},
 {"gdn.z.q6","gdn.z",Type::Q6_K,6144,2560,1,false,"gdn.z"},
 {"gdn.z.q8","gdn.z",Type::Q8_0,6144,2560,1,false,"gdn.z"},
 {"qsa.qgate","qsa.qgate",Type::Q6_K,12288,2560,1,false,"qsa.qgate"},
 {"qsa.k","qsa.k",Type::Q6_K,512,2560,1,false,"qsa.k"},
 {"qsa.v","qsa.v",Type::Q6_K,512,2560,1,false,"qsa.v"},
 {"attention.gdn","attention",Type::Q6_K,2560,6144,1,false,"attention"},
 {"attention.qsa","attention",Type::Q6_K,2560,6144,1,false,"attention"},
 {"ple.key","ple.key",Type::Q8_0,10240,2560,1,false,"ple.key"},
 {"ple.value","ple.value",Type::Q8_0,2560,2560,1,false,"ple.value"},
 {"hc.a.gate","hc.a.gate",Type::Q8_0,10240,320,1,false,"hc.a.gate"},
 {"hc.a.low","hc.a.low",Type::Q8_0,320,10240,1,false,"hc.a.low"},
 {"hc.a.inject","hc.a.inject",Type::F32,4,10240,1,false,"hc.a.inject"},
 {"hc.f.gate","hc.f.gate",Type::Q8_0,10240,320,1,false,"hc.f.gate"},
 {"hc.f.low","hc.f.low",Type::Q8_0,320,10240,1,false,"hc.f.low"},
 {"hc.f.inject","hc.f.inject",Type::F32,4,10240,1,false,"hc.f.inject"},
 {"final.gate","final.gate",Type::Q8_0,10240,320,1,false,"final.gate"},
 {"final.low","final.low",Type::Q8_0,320,10240,1,false,"final.low"},
 {"qsa.iq","qsa.iq",Type::BF16,512,2560,1,false,"qsa.iq"},
 {"qsa.ik","qsa.ik",Type::BF16,128,2560,1,false,"qsa.ik"},
 {"router","router",Type::F32,512,2560,1,false,"router"},
 {"gdn.a","gdn.a",Type::F32,48,2560,1,false,"gdn.a"},
 {"gdn.b","gdn.b",Type::F32,48,2560,1,false,"gdn.b"},
 {"shexpgate.q6","shexpgate",Type::Q6_K,640,2560,1,false,"shexpgate"},
 {"shexpgate.q8","shexpgate",Type::Q8_0,640,2560,1,false,"shexpgate"},
 {"shexpup.q6","shexpup",Type::Q6_K,640,2560,1,false,"shexpup"},
 {"shexpup.q8","shexpup",Type::Q8_0,640,2560,1,false,"shexpup"},
 {"shexpdown","shexpdown",Type::Q8_0,2560,640,1,false,"shexpdown"},
 {"shared_gate","shared_gate",Type::F32,1,2560,1,false,"shared_gate"},
 {"logits","logits",Type::Q6_K,248320,2560,1,false,"logits"}
};
inline bool expert(Type t){return t==Type::IQ2_S||t==Type::IQ3_S||t==Type::IQ3_XXS||t==Type::IQ4_NL;}
inline std::vector<std::string> candidates(Type t){
 if(expert(t)){if(t==Type::IQ4_NL)return {"p28.private.rows4","p28.private.wg32","p28.shared.rows4","p28.shared.wg32"};
 return {"p28.private.rows4","p28.private.wg32","p28.shared.rows4","p28.shared.wg32","p28.paired.rows4","p28.paired.wg32"};}
 return {"p28.dense.rows4","p28.dense.wg32"};
}
}
