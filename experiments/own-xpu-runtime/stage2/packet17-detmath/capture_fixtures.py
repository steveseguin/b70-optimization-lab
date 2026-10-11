"""Recompile v1 read-only sources with call-recording wrappers into packet17 build."""
import hashlib,json,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent;S=P.parent;B=P/'build'
source=(S/'packet4/core.hpp').read_text()
# Unary-call substitution only, including a balanced reciprocal operand.
def call_replace(s,prefix,replacement):
 while prefix in s:
  start=s.index(prefix);i=start+len(prefix);depth=1
  while depth:
   depth+=(s[i]=='(')-(s[i]==')');i+=1
  arg=s[start+len(prefix):i-1]
  s=s[:start]+replacement+'('+arg+')'+s[i:]
 return s
source=call_replace(source,'1.f / std::sqrt(','trace_math::rsqrt')
source=source.replace('1.f / (1.f + std::exp(-x))','trace_math::recip(1.f + std::exp(-x))')
for name in ('exp','log','sqrt','sin','cos','pow'):source=source.replace('std::'+name+'(','trace_math::'+name+'(')
source=source.replace('"../packet3/kernels/api.hpp"','"../../packet3/kernels/api.hpp"')
(B/'trace_core.hpp').write_text('#include "../trace_math.hpp"\n'+source)
ref=(S/'packet15-nongemv/reference.hpp').read_text().replace('"kernels.hpp"','"../../packet15-nongemv/kernels.hpp"').replace('"../packet4/core.hpp"','"trace_core.hpp"')
for name in ('exp','log','sqrt'):ref=ref.replace('std::'+name+'(','trace_math::'+name+'(')
(B/'trace_reference.hpp').write_text('#include "../trace_math.hpp"\n'+ref)
runner=(S/'packet15-nongemv/runner.cpp').read_text().split('int main(')[0].replace('"kernels.hpp"','"../../packet15-nongemv/kernels.hpp"').replace('"reference.hpp"','"trace_reference.hpp"')
runner+='int main(int argc,char**argv){if(argc!=3)return 2;std::ifstream list(fs::path(argv[1])/"cases.txt");std::string name;int count=0;while(list>>name){Fixture f(fs::path(argv[1])/name);ng::reference::cpu(f.s,f.args());++count;}require(count==72,"all fixtures required");std::ofstream out(argv[2],std::ios::binary);for(auto key:trace_math::calls){uint32_t row[4]={uint32_t(key>>32),uint32_t(key),0,0};out.write(reinterpret_cast<char*>(row),16);}std::cout<<"{\\"cases\\":"<<count<<",\\"unique_elementary_inputs\\":"<<trace_math::calls.size()<<"}\\n";}\n'
(B/'trace_fixtures.cpp').write_text(runner)
cmd=['g++','-std=c++20','-O2','-mfma','-fno-fast-math','-ffp-contract=off','-DHOST_ONLY',str(B/'trace_fixtures.cpp'),'-o',str(B/'trace-fixtures')]
subprocess.run(cmd,check=True,timeout=180)
out=subprocess.check_output([str(B/'trace-fixtures'),str(B/'fixtures'),str(B/'fixture-inputs.bin')],text=True,timeout=600)
r=json.loads(out);r.update(device_executed=False,distinct_inputs_preserve_all_evaluated_arguments=True,format='uint32 little endian op,a_bits,b_bits,c_bits; unary calls deduplicated exactly',sha256=hashlib.sha256((B/'fixture-inputs.bin').read_bytes()).hexdigest(),sources={str(q.relative_to(P.parents[3])):hashlib.sha256(q.read_bytes()).hexdigest() for q in (S/'packet4/core.hpp',S/'packet15-nongemv/reference.hpp',P/'trace_math.hpp',P/'capture_fixtures.py')})
r['case_count']=r['cases'];r['cases']=(B/'fixtures/cases.txt').read_text().split();r['complete']=True;r['trace_sha256']=r['sha256']
(P/'fixture-trace-receipt.json').write_text(json.dumps(r,indent=2)+'\n');print(out)
