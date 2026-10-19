#pragma once
namespace p157 {
struct Sample { std::string name; int position; bool replay; double ms; double start; double end; int sequence; int op; };
inline thread_local std::vector<Sample> samples;
inline thread_local int sequence=0, op=0;
struct DeviceSample { int group,position,sequence; uint64_t event,start,end; };
inline thread_local std::vector<DeviceSample> device_samples;
inline const char* groups[]={"input_norm_embedding_mix","attention_projections","attention","routed_experts","shared_expert","final_norm","head_gemv","argmax_publication"};
inline int group(const std::string& label){
 if(label=="logits")return 6;if(label=="argmax"||label.starts_with("begin.")||label.starts_with("commit."))return 7;
 if(label.starts_with("final."))return 5;
 if(label.find("shexp")!=std::string::npos||label=="blk.0.shared_gate")return 4;
 if(label.find("exps")!=std::string::npos||label.find("route")!=std::string::npos||label.find("moe")!=std::string::npos||label.find("ffn")!=std::string::npos||label.find("hc.f")!=std::string::npos||label=="blk.0.gather")return 3;
 if(label=="blk.0.qsa.qgate"||label=="blk.0.qsa.k"||label=="blk.0.qsa.v"||label=="blk.0.qsa.iq"||label=="blk.0.qsa.ik"||label=="blk.0.attention")return 1;
 if(label=="blk.0.attn.combine")return 2;
 if(label.find("qsa")!=std::string::npos)return 2;
 if(label.starts_with("merge.")||label.starts_with("blk.0.hc.a"))return 0;
 throw std::runtime_error("unclassified draft site: "+label);
}

struct Identity {int old_sequence=sequence,old_op=op;Identity(int s,int o){sequence=s;op=o;}~Identity(){sequence=old_sequence;op=old_op;}};
struct Scope {const char* name;int position;bool replay;std::chrono::steady_clock::time_point start=std::chrono::steady_clock::now();Scope(const char*n,int p,bool r=false):name(n),position(p),replay(r){};~Scope();};
inline double record(const char* name,int position,bool replay,std::chrono::steady_clock::time_point start){
 const auto end=std::chrono::steady_clock::now();
 double elapsed=std::chrono::duration<double,std::milli>(end-start).count();
 samples.push_back({name,position,replay,elapsed,std::chrono::duration<double>(start.time_since_epoch()).count(),std::chrono::duration<double>(end.time_since_epoch()).count(),sequence,op});return elapsed;
}
inline Scope::~Scope(){record(name,position,replay,start);}
template<class F> double measure(const char* name,int position,bool replay,F fn){
 const auto start=std::chrono::steady_clock::now();fn();return record(name,position,replay,start);
}
inline void flush(std::ostream& out,int rank){
 for(const auto& r:samples)out<<"{\"p157_segment\":\""<<r.name<<"\",\"position\":"<<r.position<<",\"sequence\":"<<r.sequence<<",\"op\":"<<r.op<<",\"rank\":"<<rank<<",\"replay\":"<<(r.replay?"true":"false")<<",\"ms\":"<<r.ms<<",\"start\":"<<std::setprecision(17)<<r.start<<",\"end\":"<<r.end<<"}\n";
 for(const auto& r:device_samples)out<<"{\"p157_device\":true,\"group\":"<<ownrt::quote(groups[r.group])<<",\"rank\":"<<rank<<",\"position\":"<<r.position<<",\"sequence\":"<<r.sequence<<",\"event\":"<<r.event<<",\"start_ns\":"<<r.start<<",\"end_ns\":"<<r.end<<"}\n";
 device_samples.clear();samples.clear();require(bool(out),"p157 segment receipt");
}
}
