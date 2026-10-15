"""Extract actual plan constructors/group validation; metadata only, no backend."""
import json,subprocess,os,hashlib
from pathlib import Path
P=Path(__file__).resolve().parent;B=P/'build/fix6';E=P/'evidence/fix6'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def block(text,start):
 begin=text.index(start);left=text.index('{',begin);depth=1;end=left+1
 while depth:
  depth+=(text[end]=='{')-(text[end]=='}');end+=1
 return text[begin:end]
def generate(label, transform=None):
 source=E/'before-main.cpp.txt' if label=='before' else P/'main.cpp'
 main=source.read_text();rank=(P/'rank.hpp').read_text();mtp=(P/'mtp.hpp').read_text()
 group=main[main.index('    // Only move sibling projections'):main.index('\n  void guard()')].rsplit('\n  }',1)[0]
 # Instrument the original failed predicate without changing its decision.
 needle='require(found&&found->op=="gemv"&&found->card==first.card&&found->inputs==first.inputs,"small GEMV sibling schedule/input");'
 if needle in group:
  group=group.replace(needle,'if(!(found&&found->op=="gemv"&&found->card==first.card&&found->inputs==first.inputs))std::cerr<<"group="<<key<<" first="<<first.label<<" label="<<label<<" missing="<<!found<<" op="<<(found?found->op:"absent")<<" other_card="<<(found&&found->card!=first.card)<<" different_inputs="<<(found&&found->inputs!=first.inputs)<<" p39_tag="<<(found&&p39::tagged(*found))<<"\\n";'+needle)
 draft=mtp[mtp.index('  p=flash::Builder(e.p.g)'):mtp.index('  for(auto b:p.buffers)')].replace('e.p.g','geometry')
 code='''#include "../packet2/loader/gguf.hpp"
#include "../packet3/step/plan.hpp"
#include "small_gemv.hpp"
#include "dispatch.hpp"
#include "p39_plan.hpp"
#include <iostream>
#include <filesystem>
#include <unordered_map>
using namespace integrated; namespace fs=std::filesystem;
static void require(bool ok,const std::string& msg){if(!ok)throw std::runtime_error(msg);}
struct Options {bool mini=false,first=false,pipeline_mini=false;int context=4096,cards=1;std::string nongemv="parallel",gemv="r5";};
struct Weights {flash::Directory directory;void synthesize(const flash::Plan&){throw std::logic_error("no synthetic or model weights");}};
'''+block(main,'static flash::Plan plan(')+'\n'+block(main,'static unsigned selected_variant(')+'\n'+block(rank,'static flash::Plan split(')+'''
struct Probe {
 Weights&w;Options a;flash::Plan p;
 struct SmallGroup {std::string name;std::vector<const flash::Launch*> members;};
 std::unordered_map<const flash::Launch*,SmallGroup> small_groups;
 std::unordered_map<const flash::Launch*,const flash::Launch*> small_followers;
 unsigned variant(const flash::Launch&l){return selected_variant(w,a,p,l);}
 Probe(Weights& ww,Options aa,flash::Plan pp):w(ww),a(aa),p(std::move(pp)){
'''+group+'''
 }
};
static flash::Plan draft_plan(flash::Geometry geometry){flash::Plan p;
'''+draft+'''
return p;}
int main(int argc,char**argv){try{
 require(argc==6,"plan context draft_rank rank dispatch");
 Weights w;w.directory=flash::directory_from_loader(iq3::read_plan("'''+str(P/'build/input/plan.tsv')+'''"));
 Options a;a.context=std::stoi(argv[2]);int dr=std::stoi(argv[3]),rank=std::stoi(argv[4]);
 packet26::dispatch.load(argv[5]);auto full=plan(w,a);
 if(std::string(argv[1])=="draft"){
 auto p=draft_plan(full.g);std::cout<<"{\\"passed\\":true,\\"groups\\":0,\\"launches\\":"<<p.launches.size()<<",\\"draft_uses_own_unfused_dispatch\\":true}\\n";
 }else{auto p=split(full,rank,false,std::string(argv[1])=="KD"?1:dr);Probe e(w,a,std::move(p));std::cout<<"{\\"passed\\":true,\\"groups\\":"<<e.small_groups.size()<<",\\"followers\\":"<<e.small_followers.size()<<",\\"launches\\":"<<e.p.launches.size()<<"}\\n";}
 return 0;
 }catch(const std::exception&e){std::cout<<"{\\"passed\\":false,\\"error\\":\\""<<e.what()<<"\\"}\\n";return 1;}}
'''
 if transform is not None:code=transform(code)
 path=B/(label+'.cpp');path.write_text(code)
 cmd=['g++','-std=c++20','-O0','-DOWN_RT_HOST_ONLY','-ffunction-sections','-fdata-sections','-Wl,--gc-sections','-fno-fast-math','-ffp-contract=off','-I'+str(P),'-I'+str(P.parent/'packet2/kernels'),'-I'+str(P.parents[1]/'stage1/packet3-prep/src'),str(path),str(P/'small_gemv.cpp'),str(P.parent/'packet2/loader/gguf.cpp'),'-o',str(B/label)]
 with (E/(label+'-compile.log')).open('w') as out:r=subprocess.run(cmd,stdout=out,stderr=subprocess.STDOUT)
 (E/(label+'-compile.json')).write_text(json.dumps(dict(command=cmd,exit_code=r.returncode,main_sha256=digest(source),rank_sha256=digest(P/'rank.hpp'),mtp_sha256=digest(P/'mtp.hpp'),generated_sha256=digest(path)),indent=2)+'\n')
 assert r.returncode==0,(E/(label+'-compile.log')).read_text()[-3000:]
def verify():
 row=json.loads((P/'fix6-plan-gates.json').read_text())
 assert row['passed'] and row['device_executed'] is False and row['weight_bytes_read']==0
 from seal6_amendment import source_matches
 for n,h in row['sources_sha256'].items():assert source_matches(P/n,h),'stale fix6 plan source '+n
 for n,h in row['evidence_sha256'].items():assert digest(P/n)==h,'stale fix6 plan evidence '+n
 assert digest(P/'build/input/plan.tsv')==row['metadata_sha256'],'plan metadata changed'
 assert digest(B/'after')==row['binary_sha256'],'plan gate binary changed'
 compiled=json.loads((E/'after-compile.json').read_text())
 assert compiled['main_sha256']==digest(P/'main.cpp') and compiled['generated_sha256']==digest(B/'after.cpp'),'grouping mirror changed'
 rows=json.loads((E/'plan-sweep.json').read_text())
 expected={(kind,c,dr,rank,d) for c in (4096,32768) for dr in (0,1) for kind,rank in [('target',0),('target',1),('KD',1),('draft',dr)] for d in ('dr0','dr1','forced')}
 assert len(rows)==48 and {(r['plan'],r['context'],r['draft_rank'],r['rank'],r['dispatch']) for r in rows}==expected
 assert all(r['exit_code']==0 and r['result']['passed'] for r in rows)
 tests=json.loads((E/'mutations.log').read_text().splitlines()[-1]);assert tests['passed'] and tests['checks']==9 and tests['complete_groups']==83
 return row
if __name__=='__main__':
 import argparse
 ap=argparse.ArgumentParser();ap.add_argument('stage',choices=('before','after','verify'));args=ap.parse_args()
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 if args.stage=='verify':verify()
 else:generate(args.stage)
