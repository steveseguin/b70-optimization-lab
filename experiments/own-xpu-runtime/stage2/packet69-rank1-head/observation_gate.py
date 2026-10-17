"""Small observer gate and exact source identity, never a CPU model run."""
from pathlib import Path
import json,subprocess,hashlib,os
from build_engine import P,ROOT,BASE,limits,sha,save

def main():
 limits();original=P.parent/'packet64-attribution'
 # Only selected()/category() changed in native code. Recording uses identical
 # event ownership and no new wait. Every arithmetic translation unit inherited.
 same={}
 for f in original.iterdir():
  if f.suffix in ('.cpp','.hpp','.inc') and f.name!='attribution.hpp':
   assert sha(P/f.name)==sha(f),f.name;same[str(f.relative_to(ROOT))]=sha(f)
 source=P/'build/observer-test.cpp';source.write_text(r'''#include "attribution.hpp"
#include <array>
#include <cassert>
#include <fstream>
#include <cstdint>
int main(int argc,char**argv){
 std::array<uint32_t,8> values{0x3f800000,0x3f800000,0x80000000,0,0xbf800000,0x3f000000,0x40000000,0x40000000};
 auto expected=values;p57::Recorder r;
 for(bool enabled:{false,true,false}){r.enabled=enabled;r.current={"logits",9,100,false};r.record(enabled?2:1);assert(values==expected);}
 assert(r.events.size()==1);assert(p57::selected("logits")&&p57::selected("argmax")&&p57::selected("final.norm"));
 assert(p57::category("logits")=="target_head"&&p57::category("draft.logits")=="head_prefix");
 r.current.fixture=17;r.record(3);assert(r.events.size()==1);
 std::ofstream f(argv[1],std::ios::binary);f.write((char*)values.data(),sizeof(values));
}
''')
 commands=json.loads((BASE/'engine-commands.json').read_text());intel=next(r['command'][0] for r in commands if r['name']=='device-entry-main')
 rows=[]
 for label,cc in [('gnu','/usr/bin/g++'),('intel',intel)]:
  cmd=[cc,'-std=c++20','-O1','-I'+str(P),str(source),'-o',str(P/'build'/('observer-'+label))]
  with (P/'evidence'/('observer-'+label+'.log')).open('w') as log:subprocess.run(cmd,check=True,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
  for repeat in (1,2):
   out=P/'evidence'/f'observer-{label}-{repeat}.bin'
   subprocess.run([str(P/'build'/('observer-'+label)),str(out)],check=True,stdin=subprocess.DEVNULL)
   rows.append(dict(compiler=label,repeat=repeat,sha256=sha(out)))
 assert len({r['sha256'] for r in rows})==1
 for k in ('expected','actual'):(P/'evidence'/('fixture-'+k+'.bin')).write_bytes((P/'evidence/observer-gnu-1.bin').read_bytes())
 save(P/'evidence/observer-gate.json',dict(passed=True,device_executed=False,cpu_model_executed=False,runs=rows,unchanged_native_sources=same,
    scope='Metadata observer smoke + exact native source/object identity; no full model parity claim',sources={str((P/'observation_gate.py').relative_to(ROOT)):sha(P/'observation_gate.py')}))
if __name__=='__main__':main()
