#pragma once
namespace p150 {
struct Sample { std::string name; int position; bool replay; double ms; double start; double end; };
inline thread_local std::vector<Sample> samples;
inline double record(const char* name,int position,bool replay,std::chrono::steady_clock::time_point start){
 const auto end=std::chrono::steady_clock::now();
 double elapsed=std::chrono::duration<double,std::milli>(end-start).count();
 samples.push_back({name,position,replay,elapsed,std::chrono::duration<double>(start.time_since_epoch()).count(),std::chrono::duration<double>(end.time_since_epoch()).count()});return elapsed;
}
template<class F> double measure(const char* name,int position,bool replay,F fn){
 const auto start=std::chrono::steady_clock::now();fn();return record(name,position,replay,start);
}
inline void flush(std::ostream& out,int rank){
 for(const auto& r:samples)out<<"{\"p150_segment\":\""<<r.name<<"\",\"position\":"<<r.position<<",\"rank\":"<<rank<<",\"replay\":"<<(r.replay?"true":"false")<<",\"ms\":"<<r.ms<<",\"start\":"<<std::setprecision(17)<<r.start<<",\"end\":"<<r.end<<"}\n";
 samples.clear();require(bool(out),"p150 segment receipt");
}
}
