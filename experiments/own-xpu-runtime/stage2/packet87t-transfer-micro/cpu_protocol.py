"""Execute the real two-process micro control flow with host-memory devices."""
import json,os,subprocess
from pathlib import Path
from build_engine import P,ROOT,B,limits,sha
from compile_turn import turn
MOCK=r'''
#include "sources/ordered_queue.hpp"
struct Mock final:ownrt::Backend,ownrt::OrderedQueue {
 std::string identity()const override{return "CPU-protocol-only";}
 void*allocate(size_t n,ownrt::Memory)override{return ::operator new(n);}
 void release(void*p,ownrt::Memory)override{::operator delete(p);}
 ownrt::Event copy(void*d,const void*s,size_t n,std::span<const ownrt::Event>)override{std::memcpy(d,s,n);return ownrt::next_handle();}
 ownrt::Event marker(std::span<const ownrt::Event>)override{return ownrt::next_handle();}
 ownrt::Event compute(const ownrt::Operation&,std::span<void*const>,std::span<const ownrt::Event>)override{return ownrt::next_handle();}
 bool complete(ownrt::Event)override{return true;}
 bool wait(ownrt::Event,ownrt::Deadline)override{return true;}
 bool ordered_prefix_complete(ownrt::Event)override{return true;}
 void synchronize()override{}void clear_events()override{}void close_queue()override{}void close_context()override{}
};
struct Busy:ownrt::Operation {};
'''
def main():
 limits();source=(P/'microbench.cpp').read_text()
 source=source.replace('#include "sources/sycl_operation.hpp"','')
 a=source.index('struct Busy: SyclOperation {');b=source.index('struct Rank {',a)
 source=source[:a]+MOCK+source[b:]
 source=source.replace('make_sycl_device(0,false)','std::make_unique<Mock>()')
 assert 'sycl::' not in source and 'make_sycl' not in source
 path=B/'cpu-protocol.cpp';path.write_text(source);exe=B/'cpu-protocol'
 cmd=['/usr/bin/g++','-std=c++20','-O2','-pthread','-DP56X_SLEEP20=0','-I'+str(P),str(path),str(P/'sources/owner.cpp'),str(P/'sources/owner_retire.cpp'),str(P/'sources/host_wait_mode.cpp'),'-o',str(exe)]
 with turn(),(B/'cpu-protocol-build.log').open('w') as log:subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=180,check=True)
 with (B/'cpu-protocol-samples.jsonl').open('w') as out,(B/'cpu-protocol-stderr.log').open('w') as err:
  subprocess.run([str(exe),'--coordinator-admitted-device-window'],stdin=subprocess.DEVNULL,stdout=out,stderr=err,timeout=60,check=True)
 import report
 rows=[json.loads(l) for l in (B/'cpu-protocol-samples.jsonl').read_text().splitlines()]
 result=report.summarize(rows)
 receipt=dict(passed=True,device_executed=False,scope='host-backed real two-process mailbox, staging, payload verification and graceful drain; CPU timings discarded',samples=1800,cases=len(result),command=cmd,sources={str(p.relative_to(ROOT)):sha(p) for p in [P/'microbench.cpp',P/'cpu_protocol.py',path]},samples_sha256=sha(B/'cpu-protocol-samples.jsonl'))
 (P/'evidence/cpu-protocol.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
if __name__=='__main__':main()
