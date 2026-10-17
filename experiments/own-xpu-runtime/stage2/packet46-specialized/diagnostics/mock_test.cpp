#include "trace.hpp"
#include <iostream>
#include <sstream>
#include <functional>
using namespace packet46::diagnostics;
void fails(const std::function<void()>& f) {
  bool caught=false; try { f(); } catch(const std::invalid_argument&) { caught=true; }
  require(caught,"expected rejection did not happen");
}
int main() {
  Command a{7,1,9,123,9,"decode","speculative"};
  Config c; c.mode=Mode::diagnostic; c.routes=true; c.phases=true;
  c.run_id="cpu-mock"; c.model_identity="fixture-only"; c.runtime_identity="packet46-mock";
  c.prompt_sha256=std::string(64,'0'); c.dataset_role="mock";
  std::array<uint32_t,10> ids{91,0,511,36,4,17,90,1,255,29};
  unsigned reads=0,queries=0;
  Trace off(Config{});
  auto read=[&]{++reads;return ids;};
  struct Timing{uint64_t start_ns,end_ns;};
  auto timing=[&](uint64_t id){++queries;return Timing{id*10,id*10+7};};
  std::array<uint64_t,2> events{21,22};
  off.capture_routes(a,3,read); off.gpu_events(a,3,"routing",std::span<const uint64_t>(events),timing);
  off.resolve(a,"rejected"); off.close();
  require(!reads && !queries,"disabled diagnostic executed callbacks");
  Config speed=c; speed.mode=Mode::speed_claim;
  fails([&]{Trace invalid(speed,&std::cout);});
  Config absent=c; absent.mode=Mode::off;
  fails([&]{Trace invalid(absent,&std::cout);});
  std::ostringstream rejected;
  Trace invalid_ids(c,&rejected);
  fails([&]{invalid_ids.capture_routes(a,3,[&]{auto x=ids;x[1]=x[0];return x;});});
  fails([&]{invalid_ids.capture_routes(a,48,read);});
  fails([&]{invalid_ids.host_span(a,3,"not-a-phase",1,2);});
  fails([&]{invalid_ids.close();});
  require(rejected.str().find("footer")==std::string::npos,"failed collector emitted footer");
  std::ostringstream bad_metadata;
  Trace invalid_command(c,&bad_metadata);
  Command invalid=a; invalid.stage="not-a-stage";
  fails([&]{invalid_command.capture_routes(invalid,3,read);});
  require(!reads,"bad command invoked route callback");
  Trace trace(c,&std::cout);
  trace.capture_routes(a,3,read);
  trace.gpu_events(a,3,"routing",std::span<const uint64_t>(events),timing);
  trace.host_span(a,-1,"command",100,500);
  trace.resolve(a,"rejected");
  Command b{7,2,9,124,9,"decode","corrected"};
  ids[0]=92; trace.capture_routes(b,3,read); trace.resolve(b,"accepted");
  trace.close();
  require(reads==2 && queries==2,"collector callback count");
  fails([&]{trace.capture_routes(b,3,read);});
  require(reads==2,"closed collector invoked route callback");
  fails([&]{trace.resolve(b,"accepted");});
}
