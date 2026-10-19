#pragma once
namespace p154 {
struct Sample { std::string name; int position; bool replay; double ms; double start; double end; int sequence; int op; };
inline thread_local std::vector<Sample> samples;
inline thread_local int sequence=0, op=0;
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
 for(const auto& r:samples)out<<"{\"p154_segment\":\""<<r.name<<"\",\"position\":"<<r.position<<",\"sequence\":"<<r.sequence<<",\"op\":"<<r.op<<",\"rank\":"<<rank<<",\"replay\":"<<(r.replay?"true":"false")<<",\"ms\":"<<r.ms<<",\"start\":"<<std::setprecision(17)<<r.start<<",\"end\":"<<r.end<<"}\n";
 samples.clear();require(bool(out),"p154 segment receipt");
}
}
