#pragma once
#include "runtime_kernels.hpp"
#include "dispatch_registry.hpp"
#include <fstream>
#include <map>
#include <set>
#include <cctype>
#include <string>
namespace packet26 {
struct Dispatch {
 std::map<std::string,std::string> classes,gemv,fusions;
 Dispatch(){classes={{"hc.a.norm","specialised"},{"hc.f.norm","specialised"},{"final.norm","specialised"},{"ple.kn","specialised"},{"ple.qn","specialised"},{"ple.cn","specialised"},{"gdn.norm","packet18"},{"gdn.recurrence","packet18"},{"qsa.prepare","packet18"},{"qsa.pool","packet18"},{"qsa.select","packet18"},{"qsa.attention","packet18"},{"attn.combine","specialised"},{"ffn.combine","specialised"},{"route","specialised"},{"gather","specialised"},{"argmax","specialised"},{"streams","specialised"},{"ple.add","specialised"}};gemv={{"expsgate","r5"},{"expsdown","r5"},{"gdn.qkv","r5"},{"gdn.z","r5"},{"qsa.qgate","r5"},{"qsa.k","r5"},{"qsa.v","r5"},{"attention","r5"},{"ple.key","r5"},{"ple.value","r5"},{"hc.gate","r5"},{"hc.low","r5"},{"logits","r5"}};fusions={{"attn.combine+norm","specialised"},{"ffn.combine+norm","specialised"},{"route+gather","specialised"}};}
 // Deliberately small closed JSON grammar: schema plus string-valued maps.
 // Reject malformed/trailing data, escapes, duplicate keys and unknown fields.
 void load(const std::string& path){
  classes.clear();gemv.clear();fusions.clear();if(path.empty())return;
  std::ifstream f(path);if(!f)throw std::invalid_argument("dispatch file missing: "+path);
  std::string text((std::istreambuf_iterator<char>(f)),{});size_t at=0;
  auto ws=[&](){while(at<text.size()&&std::isspace(static_cast<unsigned char>(text[at])))++at;};
  auto take=[&](char c){ws();if(at>=text.size()||text[at++]!=c)throw std::invalid_argument("dispatch JSON punctuation");};
  auto str=[&](){take('"');std::string out;while(at<text.size()&&text[at]!='"'){auto c=text[at++];if(c==92||static_cast<unsigned char>(c)<32)throw std::invalid_argument("dispatch JSON string");out+=c;}take('"');return out;};
  auto more=[&](){ws();if(at<text.size()&&text[at]==','){++at;return true;}return false;};
  std::set<std::string> fields;bool schema=false;take('{');
  do {auto key=str();if(!fields.insert(key).second)throw std::invalid_argument("duplicate dispatch field");take(':');
   if(key=="schema"){if(str()!="packet26.dispatch.v1")throw std::invalid_argument("dispatch schema");schema=true;}
   else if(key=="classes"||key=="gemv"||key=="fusions"){
    auto& table=key=="classes"?classes:(key=="gemv"?gemv:fusions);take('{');ws();if(at<text.size()&&text[at]!='}')do{auto k=str();take(':');auto v=str();
     if(k.empty()||v.empty()||!table.emplace(k,v).second)throw std::invalid_argument("duplicate/empty dispatch class");
     if(key!="gemv"&&v!="packet18"&&v!="specialised"&&v!="round2")throw std::invalid_argument("unknown non-GEMV kernel: "+v);
    }while(more());take('}');
   }else throw std::invalid_argument("unknown dispatch field: "+key);
  }while(more());take('}');ws();if(at!=text.size()||!schema)throw std::invalid_argument("dispatch trailing data/schema");
  packet29::validate_dispatch(classes,gemv,fusions);
 }
 static const char* op_class(integrated::Op op){using integrated::Op;switch(op){
 case Op::route:return "route";case Op::expert_gather:return "gather";case Op::hc_combine:return "hc.combine";case Op::argmax:return "argmax";
 case Op::norm:return "norm";case Op::gdn:return "gdn.recurrence";case Op::gdn_norm_gate:return "gdn.norm";case Op::qsa_prepare:return "qsa.prepare";
 case Op::qsa_append_pool:return "qsa.pool";case Op::qsa_select:return "qsa.select";case Op::qsa_attention:return "qsa.attention";default:return "other";}}
 static std::string class_name(const std::string& label){if(label.starts_with("blk.")){auto end=label.find('.',4);if(end!=std::string::npos)return label.substr(end+1);}return label;}
 int implementation_for(const std::string& label,integrated::Op op)const{
  auto i=classes.find(label);if(i==classes.end())i=classes.find(class_name(label));if(i==classes.end())i=classes.find(op_class(op));if(i==classes.end())i=classes.find("*");
  if(i==classes.end())return 0;return i->second=="round2"?2:i->second=="specialised"?1:0;
 }
 bool new_for(const std::string& label,integrated::Op op)const{return implementation_for(label,op)>0;}
 std::string fusion_choice(const std::string& key)const{auto i=fusions.find(key);if(i==fusions.end())i=fusions.find("*");return i==fusions.end()?"packet18":i->second;}
 bool fusion_for(const std::string& key)const{auto i=fusions.find(key);if(i==fusions.end())i=fusions.find("*");return i!=fusions.end()&&i->second!="packet18";}
 std::string gemv_for(const std::string& label)const{auto i=gemv.find(label);if(i==gemv.end())i=gemv.find(class_name(label));auto cls=class_name(label);if(i==gemv.end()&&(cls.starts_with("hc.a.")||cls.starts_with("hc.f.")))i=gemv.find("hc."+cls.substr(5));return i==gemv.end()?"":i->second;}
};
inline Dispatch dispatch;
}
