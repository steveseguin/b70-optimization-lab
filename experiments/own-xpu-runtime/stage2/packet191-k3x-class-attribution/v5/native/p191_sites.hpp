// Packet191: per-class site instrumentation as an in-load view key (`sites=off|on`, k3-storage selections only).
//
// Replaces packet65's expert-only recorder (p65_attribution.hpp) under the same namespace, so rank.hpp's half
// hooks compile unchanged. Observation only: no kernel, no barrier, no device readback. With `sites=on` the
// engine records, for every kernel event it submits inside a SAMPLED half/boundary/draft (fixtures 9-16,
// 57-64 and 105-112 of each request: three eight-token windows across the 128-token request), the site label
// it was issued under; at the half's own final drain (after the GPU finished, exactly where `timing=class`
// reads them) the event's start/end timestamps are read from the profiling queue and one JSON row is written
// to sites.jsonl. Both ranks already run profiling-enabled queues on the record line (rank 0 always, rank 1
// for the MTP draft), so `on` changes no queue property. With `sites=off` (and in the 19-key record selection
// without the key) `enabled` is false: active() is false, nothing is recorded, nothing is written, and the
// submit path is the record path plus one bool test (the same test packet65/77 left in it).
#pragma once
#include <map>
#include <string>
namespace p65timing {
inline bool sample(int fixture) { return (fixture>=9&&fixture<=16)||(fixture>=57&&fixture<=64)||(fixture>=105&&fixture<=112); }
struct Site {std::string label;int fixture=0,position=-1;bool speculative=false;unsigned long long half=0;const char* phase="half";bool corrected=false;};
struct Recorder {
 bool enabled=false;unsigned long long next_half=0,rows=0;Site current;
 std::map<unsigned long long,Site> events;
 bool active() const {return enabled&&sample(current.fixture);}
 void begin(int fixture,int position,bool speculative,const char* phase="half",bool corrected=false){current={"",fixture,position,speculative,++next_half,phase,corrected};}
 // `override` tags events submitted outside a labelled site (the rank-1 MTP draft: label "draft", phase "draft").
 void record(unsigned long long event,const char* override=nullptr){
  if(!active())return;
  if(!override){events.emplace(event,current);return;}
  Site s=current;s.label=override;s.phase=override;events.emplace(event,s);
 }
};
}
