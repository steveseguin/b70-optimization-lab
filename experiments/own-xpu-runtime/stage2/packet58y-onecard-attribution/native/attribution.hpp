#pragma once
// Host-only timestamps around EXISTING work. No device queries or fences.
#include <array>
#include <chrono>
#include <cstdint>
#include <ostream>
namespace p58y {
using Clock=std::chrono::steady_clock;
enum Phase {other,prepare,enqueue,cache_boundary,cache_plan,readbacks,cache_after,phase_count};
enum Cause {compute,zero_copy_miss,fill_copies,table_publication,readback,input_upload,cause_count};
inline constexpr const char* phases[]={"other","prepare","enqueue","cache_boundary","cache_plan","readbacks","cache_after"};
inline constexpr const char* causes[]={"compute_including_zero_copy_miss","zero_copy_miss_separate","fill_copies","table_publication","readbacks","input_upload"};
struct Stats {
  bool active=false; Phase phase=other; Cause cause=compute; Clock::time_point mark{},start{};
  std::array<double,phase_count> phase_ms{},phase_wait_ms{};
  std::array<double,cause_count> wait_ms{};
  std::array<uint64_t,cause_count> wait_calls{};
  std::array<double,10> enqueue_class_ms{};
  std::array<uint64_t,10> class_submissions{};
  uint64_t fills=0,fill_bytes=0,misses=0,hits=0,miss_bytes=0,hit_bytes=0,publications=0,publication_bytes=0,fill_queries=0,fill_pending_queries=0;
};
inline thread_local Stats stats;
inline double delta(Clock::time_point a,Clock::time_point b){return std::chrono::duration<double,std::milli>(b-a).count();}
inline void switch_phase(Phase p){if(stats.active){auto now=Clock::now();stats.phase_ms[stats.phase]+=delta(stats.mark,now);stats.mark=now;stats.phase=p;}}
struct Scope {Phase old;explicit Scope(Phase p):old(stats.phase){switch_phase(p);}~Scope(){switch_phase(old);}};
struct Waiting {bool active;Cause cause;Phase phase;Clock::time_point start;
  Waiting():active(stats.active),cause(stats.cause),phase(stats.phase),start(active?Clock::now():Clock::time_point{}){}
  ~Waiting(){if(active){double elapsed=delta(start,Clock::now());stats.wait_ms[cause]+=elapsed;stats.phase_wait_ms[phase]+=elapsed;++stats.wait_calls[cause];}}
};
struct Reason {Cause old;explicit Reason(Cause c):old(stats.cause){stats.cause=c;}~Reason(){stats.cause=old;}};
inline void begin(bool enabled){stats=Stats{};stats.active=enabled;if(enabled)stats.start=stats.mark=Clock::now();}
inline void finish(std::ostream& out,int generated_index,int token_id,int position,bool fill_pending){
  if(!stats.active)return;
  switch_phase(other);const auto end=stats.mark;stats.active=false;
  const double wall=delta(stats.start,end);
  double attributed=0;
  out.precision(17);
  out<<"{\"schema\":\"packet58y.token.v1\",\"generated_index\":"<<generated_index<<",\"token_id\":"<<token_id<<",\"position\":"<<position<<",\"wall_ms\":"<<wall<<",\"host_exclusive_ms\":{";
  for(int i=1;i<phase_count;++i){double n=stats.phase_ms[i]-stats.phase_wait_ms[i];attributed+=n;out<<(i>1?",":"")<<'"'<<phases[i]<<"\":"<<n;}
  out<<"},\"host_wait_ms\":{";
  for(int i=0;i<cause_count;++i){attributed+=stats.wait_ms[i];out<<(i?",":"")<<'"'<<causes[i]<<"\":"<<stats.wait_ms[i];}
  out<<"},\"host_wait_calls\":{";
  for(int i=0;i<cause_count;++i)out<<(i?",":"")<<'"'<<causes[i]<<"\":"<<stats.wait_calls[i];
  out<<"},\"enqueue_class_ms\":[";
  for(int i=0;i<10;++i)out<<(i?",":"")<<stats.enqueue_class_ms[i];
  out<<"],\"class_submissions\":[";
  for(int i=0;i<10;++i)out<<(i?",":"")<<stats.class_submissions[i];
  out<<"],\"device_class_ms\":{\"dense_r5\":null,\"experts_r5\":null,\"p25_p27_gemv\":null,\"p28_p29_gemv\":null,\"small_fusions\":null,\"specialised_round2\":null,\"parallel18\":null,\"combine\":null,\"check_commit\":null,\"copy\":null},\"device_timing_status\":\"unavailable: production queues are not profiling-enabled; no graph event timing\",\"zero_copy_miss_stall_ms\":null,\"fills\":"<<stats.fills<<",\"fill_bytes\":"<<stats.fill_bytes<<",\"misses\":"<<stats.misses<<",\"hits\":"<<stats.hits<<",\"miss_bytes\":"<<stats.miss_bytes<<",\"hit_bytes\":"<<stats.hit_bytes<<",\"publication_uploads\":"<<stats.publications<<",\"publication_bytes\":"<<stats.publication_bytes<<",\"fill_queries\":"<<stats.fill_queries<<",\"fill_pending_queries\":"<<stats.fill_pending_queries<<",\"fill_pending_end\":"<<(fill_pending?"true":"false")<<",\"residual_ms\":"<<wall-attributed<<",\"profiling\":false,\"extra_device_waits\":0}\n";
}
}
