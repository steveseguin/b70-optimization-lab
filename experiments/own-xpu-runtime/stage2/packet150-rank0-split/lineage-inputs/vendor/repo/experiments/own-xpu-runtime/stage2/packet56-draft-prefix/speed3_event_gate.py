"""CPU mock of the exact production publication and profiling-drain methods."""
import hashlib,json,os,subprocess
from pathlib import Path
from plan_group_gate import block
P=Path(__file__).resolve().parent;E=P/'evidence/speed3';B=P/'build/speed3-events'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 B.mkdir(exist_ok=True)
 main=(P/'main.cpp').read_text();mtp=(P/'mtp.hpp').read_text()
 drain=block(main,'  void drain()');poll=block(mtp,' std::optional<Completion> poll_result()')
 assert '.timing(' not in poll and 'pending_profile' not in mtp
 code=r'''
#include <array>
#include <vector>
#include <optional>
#include <chrono>
#include <sstream>
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <algorithm>
static void require(bool b,const char*s){if(!b)throw std::runtime_error(s);}
struct Timing {uint64_t start_ns=100,end_ns=200;};
struct Device {
 struct Row{void*pointer;};struct Arena{std::array<int,2> bytes{0,7};Row row(int){return {bytes.data()};}}arena;
 int queries=0,completions=0,retirements=0;bool ready=true,live=true,oversize=false;
 bool complete(int){++completions;require(live,"completion after retirement");return ready;}
 Timing timing(int){require(live,"timing after retirement");++queries;return {100,oversize?4000000101ull:200ull};}
 void retire_completed_events(){require(live,"double retirement");live=false;++retirements;}
};
struct Engine {
 struct Launch{int first,last,passes;};struct Pending{Launch launch;bool gemv;int cls;};
 std::vector<Pending> pending{{{1,2,2},true,0},{{3,3,1},false,1}};
 int tail=4;Device device;std::vector<int> devices{0};bool progress_pending=true,class_timing=true;
 double gemv_ms=0,nongemv_ms=0;uint64_t max_submission_ns=0;
 std::array<double,2> class_ms{};std::array<int,2> class_launches{},class_groups{};
 struct Args{std::string draft_fault="none";}a;
 Device&dev(int){return device;}void wait(int,int){require(device.ready,"wait before completion");}
 static double ms(std::chrono::steady_clock::time_point){return 1.;}
'''+drain+r'''
};
struct Provider {
 Engine&e;int publication=1,publication_event=4,position=0,pending_confirmed=2;
 bool async_pending=true,pending_head=true,disabled=false;
 std::chrono::steady_clock::time_point pending_start{};std::ostringstream trace;
 struct Plan{struct Geometry{int vocab=16;}g;}p;
 struct Completion{int token=-1;double wall_ms=0,gpu_ms=0;};
'''+poll+r'''
};
int main(){int checks=0;
 for(int placement:{0,1}) {
  Engine e;Provider p{e};e.device.ready=false;
  require(!p.poll_result()&&e.device.queries==0,"premature publication");++checks;
  e.device.ready=true;auto done=p.poll_result();
  require(done&&done->token==7&&done->gpu_ms<0&&!e.progress_pending,"completion publication");
  require(e.device.queries==0&&e.device.live&&e.pending.size()==2,"publication profiled or retired events");++checks;
  int probes=e.device.completions;require(!p.poll_result()&&e.device.completions==probes,"inactive completion query");++checks;
  e.drain();require(e.device.queries==3&&e.device.retirements==1&&e.pending.empty(),"events not profiled exactly once");
  require(e.class_launches[0]==2&&e.class_launches[1]==1&&e.gemv_ms>0&&e.nongemv_ms>0,"profiling not accounted");++checks;
  e.drain();require(e.device.queries==3&&e.device.retirements==1,"duplicate profiling or retirement");++checks;
  Engine over;Provider slow{over};over.device.oversize=true;require(bool(slow.poll_result()),"completion before budget validation");
  bool rejected=false;try{over.drain();}catch(const std::runtime_error& ex){rejected=std::string(ex.what()).find("4-second")!=std::string::npos;}
  require(rejected&&over.device.live&&over.device.retirements==0,"budget failure released owner");++checks;
  Engine failed;Provider error{failed};failed.device.arena.bytes[0]=7;auto bad=error.poll_result();
  require(bad&&bad->token==-1&&error.disabled&&failed.device.arena.bytes[0]==7,"sticky error erased");++checks;
  Engine malformed;malformed.pending[0].launch.passes=1;rejected=false;
  try{malformed.drain();}catch(const std::runtime_error&){rejected=true;}
  require(rejected&&malformed.device.retirements==0,"malformed event group accepted");++checks;
 }
 std::cout<<"{\"passed\":true,\"checks\":"<<checks<<",\"placements\":2,\"publication_timing_queries\":0,\"profile_queries_per_three_events\":3,\"budget_negative_controls\":2,\"sticky_error_checks\":2}\n";
}
'''
 source=B/'gate.cpp';source.write_text(code)
 command=['g++','-std=c++20','-O0','-fno-fast-math','-ffp-contract=off',str(source),'-o',str(B/'gate')]
 compiled=subprocess.run(command,text=True,capture_output=True)
 (E/'event-compile.log').write_text(compiled.stdout+compiled.stderr)
 assert compiled.returncode==0,compiled.stderr
 run=subprocess.run([str(B/'gate')],text=True,capture_output=True)
 (E/'event.log').write_text(run.stdout+run.stderr);assert run.returncode==0,run.stdout+run.stderr
 row=json.loads(run.stdout);row.update(device_executed=False,source_sha256={n:sha(P/n) for n in ('speed3_event_gate.py','main.cpp','mtp.hpp','rank.hpp')},binary_sha256=sha(B/'gate'),generated_sha256=sha(source),command=command)
 (P/'speed3-event-gates.json').write_text(json.dumps(row,indent=2)+'\n');print(json.dumps(row))
if __name__=='__main__':main()
