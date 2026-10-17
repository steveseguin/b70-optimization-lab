"""Full geometry, real setup/allocation/capture code, no payloads or model compute.

Generate a separate test translation unit. Production sources/binaries remain
unchanged. Replace only backend and payload-loading seams; preserve every real
allocation, category, lifetime, shape, prepared binding and post-load constructor.
"""
import json,subprocess
from pathlib import Path
from build_engine import P,ROOT,B,sha,save
import os,resource
def limits():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))

MOCK=r'''
class P71cAllocationMock;
static P71cAllocationMock* p71c_last_mock=nullptr;
class P71cAllocationMock final : public ownrt::Backend {
 std::vector<ownrt::Event> events;uintptr_t logical_address=0x10000000000ull;
public:
 size_t backing_bytes=0,payload_reads=0,kernels_executed=0;
 P71cAllocationMock(){p71c_last_mock=this;}
 std::string identity()const override{return "p71c-full-shape-allocation-only";}
 void* allocate(size_t n,Memory m)override{if(m==Memory::device){auto p=logical_address;logical_address+=(n+4095)&~size_t(4095);return reinterpret_cast<void*>(p);}backing_bytes+=n;return ::operator new(n);}
 void release(void*p,Memory m)override{if(m!=Memory::device)::operator delete(p);}
 ownrt::Event marker(std::span<const ownrt::Event>)override{auto e=ownrt::next_handle();events.push_back(e);return e;}
 ownrt::Event copy(void*,const void*,size_t,std::span<const ownrt::Event>d)override{return marker(d);}
 ownrt::Event compute(const ownrt::Operation&,std::span<void*const>,std::span<const ownrt::Event>d)override{return marker(d);}
 std::function<ownrt::Event()> prepare_owned(std::shared_ptr<const ownrt::Operation>,std::span<void*const>)override{return [this]{return marker({});};}
 bool complete(ownrt::Event e)override{return std::binary_search(events.begin(),events.end(),e);}
 bool ordered_prefix_complete(ownrt::Event e){if(events.empty()||events.back()!=e)throw std::logic_error("not terminal");return complete(e);}
 bool wait(ownrt::Event e,ownrt::Deadline)override{return complete(e);}
 void synchronize()override{}
 void clear_events()override{events.clear();}
 void close_queue()override{}
 void close_context()override{}
};
'''

def main():
 limits();dest=B/'fullshape';dest.mkdir(exist_ok=True)
 checked=B/'checked'/P.relative_to(ROOT)
 main=(checked/'main.cpp').read_text()
 assert main.count('std::make_unique<Host>()')==1
 main=main.replace('class Host final',MOCK+'\nclass Host final',1)
 main=main.replace('std::make_unique<Host>()','std::make_unique<P71cAllocationMock>()')
 anchor='    weights[c][name] = id;'
 assert main.count(anchor)==1;main=main.replace(anchor,anchor+'\n    return; // test seam: no target payload read or repack')
 # Weights metadata constructor is tiny-only and no payload entrypoint is called.
 # Turn accidental calls into explicit failure even in this test-only image.
 anchor='  std::vector<uint8_t> read(const std::string &name, size_t off, size_t n) {'
 if anchor not in main:
  import re
  match=re.search(r'  std::vector<uint8_t> read\([^{}]+\)\s*\{',main);assert match
  anchor=match.group()
 main=main.replace(anchor,anchor+'\n    throw std::logic_error("fullshape forbids target payload reads");',1)
 mtp=(checked/'mtp.hpp').read_text()
 mtp=mtp.replace('if(!e.a.mini)store=std::make_unique<Store>(e.a.draft_manifest,e.a.draft_model);','/* test seam: no draft payload Store */')
 anchor='mutable_ids.erase(w.id);'
 assert mtp.count(anchor)==1;mtp=mtp.replace(anchor,anchor+'weights[name]=w;return; // test seam: no draft payload reads\n')
 (dest/'mtp.hpp').write_text(mtp)
 assert str(checked/'mtp.hpp') in main
 main=main.replace(str(checked/'mtp.hpp'),str(dest/'mtp.hpp'))
 (dest/'main.cpp').write_text(main)
 entry=dest/'test.cpp';entry.write_text('#define main p71c_unused_model_entry\n#include '+json.dumps(str(dest/'main.cpp'))+'\n#undef main\n#include '+json.dumps(str(P/'fullshape_test.cpp'))+'\n')
 commands=json.loads((P/'engine-commands.json').read_text());base=next(r['command'] for r in commands if r['name']=='gnu-host-entry-main');base=base[:base.index('-o')]
 # Lower compiler optimization for a setup-only test; arithmetic never runs.
 base=[x for x in base if not x.startswith('-O')]+['-O0']
 compile_cmd=[*base,'-o',str(dest/'test.o'),'-c',str(entry)]
 link=list(next(r['command'] for r in commands if r['name']=='gnu-host-link'))
 link=[x for x in link if not x.endswith('own-rt-iq3-entry.cpp.o')]
 index=link.index(str(B/'gnu-host/entry-main.o'));link[index]=str(dest/'test.o');link[link.index('-o')+1]=str(dest/'test')
 for i,cmd in enumerate((compile_cmd,link)):
  with (dest/f'build-{i}.log').open('w') as log:subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=600)
 results=[]
 control=P.with_name('packet64-record-bundle')/'selections/1-draft-hc-batch'
 for choice,view,depth in [('smoke-B',P,'production'),('candidate-B',P,'production'),('serial-smoke-B',P,'serial'),('control-B',control,'off'),('control-repeat-B',control,'off'),('negative-71b',P.with_name('packet71b-depth2-engine'),'production')]:
  out=dest/(choice+'-verified');cmd=[str(dest/'test'),str(P),str(out),str(view/'selection.json'),str(view/'dispatch-speed6.json'),depth]
  with (dest/(choice+'.log')).open('w') as log:r=subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=180)
  if choice=='negative-71b':
   assert r.returncode!=0 and '71b router expects production standalone' in (dest/(choice+'.log')).read_text()
   results.append(dict(choice=choice,expected_refusal=True,passed=True,command=cmd));print(choice,'refused as expected',flush=True);continue
  r.check_returncode()
  for rank in (0,1):results.append(dict(choice=choice,command=cmd,result=json.loads((out/f'rank{rank}/result.json').read_text()),census=str((out/f'rank{rank}/census.json').relative_to(ROOT))))
  print(choice,'full-shape startup/capture PASS',flush=True)
 sources={str(f.relative_to(ROOT)):sha(f) for f in (P/'fullshape_gate.py',P/'fullshape_test.cpp',P/'build-device-receipt.json',dest/'main.cpp',dest/'mtp.hpp',entry)}
 for view in (P,control,P.with_name('packet71b-depth2-engine')):
  for leaf in ('selection.json','dispatch-speed6.json','memory-plan.json'):
   f=view/leaf;sources[str(f.relative_to(ROOT))]=sha(f)
 from memory_gate import check
 admitted=[]
 for row in results:
  if 'census' not in row:continue
  ledger=json.loads(((control if row['choice'].startswith('control') else P)/'memory-plan.json').read_text())
  admitted.append(check(json.loads((ROOT/row['census']).read_text()),ledger,row['result']['rank'],mtp=True,context=4096,draft_rank=1,target_split=0))
 save(P/'evidence/fullshape.json',dict(passed=True,device_executed=False,cpu_model_executed=False,commands=[compile_cmd,link],sources=sources,results=results,admissions=admitted,binary_sha256=sha(dest/'test')))
if __name__=='__main__':main()
