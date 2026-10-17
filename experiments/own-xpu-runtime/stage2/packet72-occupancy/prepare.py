"""One-time CPU source copy; never modifies a parent packet."""
from pathlib import Path
import hashlib, json, shutil
P=Path(__file__).resolve().parent
BASE=P.parent/'packet70-record-bundle'
ROOT=P.parents[3]
assert not (P/'main.cpp').exists()
pins={}
for p in BASE.iterdir():
    if p.is_file() and (p.suffix in ('.cpp','.hpp','.inc') or p.name in ('math_gate.py','kernel_gate.py','kernel_overlay.py','submission_overlay.py','rope.bf16','mtp-manifest.tsv','dispatch-speed6.json','memory-plan.json','selection.json')):
        shutil.copyfile(p,P/p.name)
        pins[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
for name in ('p28','prototype'):
    shutil.copytree(BASE/name,P/name,ignore=shutil.ignore_patterns('__pycache__'))
(P/'parent-source-manifest.json').write_text(json.dumps(pins,indent=2)+'\n')
(P/'build').mkdir(exist_ok=True)
def edit(name,old,new):
    p=P/name;s=p.read_text();assert old in s,(name,old);p.write_text(s.replace(old,new))
edit('p49c_submit.cpp','#include "p49c_kernel.hpp"','#include "p49c_kernel.hpp"\n#include "p72_attention.hpp"')
edit('p49c_submit.cpp','template<Type T,unsigned K,unsigned Split,p39::Kind E>','template<Type T,unsigned K,unsigned Split,p39::Kind E,bool Wide=false>')
edit('p49c_submit.cpp','DenseKernel<T,K,Split,E> op;', 'std::conditional_t<Wide,p72::AttentionKernel,DenseKernel<T,K,Split,E>> op;')
edit('p49c_submit.cpp','integrated::Launch route(ownrt::Device&d,', '''integrated::Launch attention_wide_submit(ownrt::Device&d,const integrated::Matrix&m,const p39::Bindings&b){
 if(m.type!=Type::Q6_K||m.columns!=6144)throw std::invalid_argument("packet72 attention shape");
 return issue<Type::Q6_K,6144,4,p39::Kind::attention_combine,true>(d,m,b);
}
integrated::Launch route(ownrt::Device&d,''')
edit('p49c_submit.hpp','namespace p49c {','namespace p49c {\nintegrated::Launch attention_wide_submit(ownrt::Device&,const integrated::Matrix&,const p39::Bindings&);')
edit('main.cpp','round2?p49c::dense_submit(dev(c),m,kind,b)', 'round2?(kind==p39::Kind::attention_combine&&sealed_selection.choices.at("attention_output")=="wide64"?p49c::attention_wide_submit(dev(c),m,b):p49c::dense_submit(dev(c),m,kind,b))')
edit('p49d_submit.cpp','Submit resolve(std::string_view cls,std::string_view choice){','Submit resolve(std::string_view cls,std::string_view choice){\n if(cls=="attention_output"&&(choice=="production"||choice=="wide64"))return production;')
edit('p49d_submit.cpp','values.size()!=5','values.size()!=6')
edit('p49d_submit.cpp','target_values.erase("experts");','target_values.erase("experts");target_values.erase("attention_output");')
s=json.loads((P/'selection.json').read_text());s['decision']=None;s['choices']['attention_output']='production'
assert s['choices']['experts']=='wide64' and s['choices']['miss']=='batch'
(P/'selection.json').write_text(json.dumps(s,indent=2)+'\n')
print('packet70 copied; only attention output and its selector changed')
