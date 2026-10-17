from pathlib import Path
import json
P=Path(__file__).resolve().parent

def edit(n,a,b):
 p=P/n;s=p.read_text();assert a in s,(n,a);p.write_text(s.replace(a,b))
edit('p49c_kernel.hpp','#include "p39_fused.hpp"','#include "p39_fused.hpp"\n#include "p74_packed.hpp"')
edit('p49c_kernel.hpp','unsigned Stage=0>struct DenseKernel','unsigned Stage=0,bool Packed=false>struct DenseKernel')
edit('p49c_kernel.hpp','static_assert(K%256==0||K==320);','static_assert(K%32==0);')
edit('p49c_kernel.hpp','dense_lane<T,K>(b.w+size_t(row)*b.rb,b.x,bounds.first,bounds.second,lane)', '(Packed?p74::lane<T,K>(b.w+size_t(row)*b.rb,b.x,bounds.first,bounds.second,lane):dense_lane<T,K>(b.w+size_t(row)*b.rb,b.x,bounds.first,bounds.second,lane))')
# Existing DenseKernel is instantiated only for Q6/Q8. Runtime ternary folds.
edit('main.cpp','#include "p49c_submit.hpp"','#include "p49c_submit.hpp"\n#include "p74_submit.hpp"')
marker='  void load(int c, const std::string &name) {'
edit('main.cpp',marker,'''  bool packed_weight(const std::string& name)const {
    if(a.mini||a.memory!="resident")return false;
    const auto& t=w.directory.at(name);auto type=flash::grid_type(t.grid);
    if(type!=iq3::Type::Q6_K&&type!=iq3::Type::Q8_0)return false;
    auto choice=sealed_selection.choices.find("packed_dense");
    if(choice==sealed_selection.choices.end()||choice->second=="production")return false;
    if(name=="output.weight")return choice->second=="head-packed"||choice->second=="combined";
    if(choice->second!="dense-packed"&&choice->second!="combined")return false;
    for(const auto& l:p.launches)if(l.op=="gemv"&&l.weights[0]==name){
      auto cls=packet26::Dispatch::class_name(l.label);
      return cls=="gdn.qkv"||cls=="gdn.z"||cls=="qsa.qgate"||cls=="qsa.k"||cls=="qsa.v"||cls=="attention"||cls=="ple.key"||cls=="ple.value"||cls=="shexpdown";
    }return false;
  }
'''+marker)
edit('main.cpp','const bool planes=p49b_weight(w,a,p,name);','const bool packed=packed_weight(name);\n    const bool planes=!packed&&p49b_weight(w,a,p,name);')
edit('main.cpp','size_t expanded_bytes=planes?', 'size_t expanded_bytes=packed?t.bytes:planes?')
edit('main.cpp','if(arithmetic::is_expanded(v)) {','if(!packed&&arithmetic::is_expanded(v)) {')
edit('main.cpp','finish(c,round2?p49c::dense_submit(dev(c),m,kind,b)', 'finish(c,packed_weight(l.weights[0])?p74::submit(dev(c),m,variant(l),kind,b):round2?p49c::dense_submit(dev(c),m,kind,b)')
edit('main.cpp','    const auto& candidate=gemv_choices.at(&l).first;\n    if(candidate==', '    if(packed_weight(l.weights[0])){finish(c,p74::submit(dev(c),m,variant(l)),true);return;}\n    const auto& candidate=gemv_choices.at(&l).first;\n    if(candidate==')
# Keep draft unchanged: own only its expanded prefix when target is packed.
edit('mtp.hpp','if(e.a.memory=="resident"&&e.weights[0].count("output.weight"))hw.id=', 'if(e.a.memory=="resident"&&e.weights[0].count("output.weight")&&!e.packed_weight("output.weight"))hw.id=')
edit('mtp.hpp','hw.id=alloc("shared-head-host",size_t(hw.rows)*er,Category::weights);','if(e.packed_weight("output.weight"))hw.rows=p56::rows(p.g.vocab,e.a.mini);hw.id=alloc("shared-head-host",size_t(hw.rows)*er,Category::weights);')
edit('mtp.hpp','\\"extra_weight_bytes\\":0,','\\"extra_weight_bytes\\":"+std::to_string(e.packed_weight("output.weight")?size_t(hw.rows)*arithmetic::row_bytes(hw.type,hw.cols,head_variant):0)+",')
edit('p49d_submit.cpp','Submit resolve(std::string_view cls,std::string_view choice){','Submit resolve(std::string_view cls,std::string_view choice){\n if(cls=="packed_dense"&&(choice=="production"||choice=="head-packed"||choice=="dense-packed"||choice=="combined"))return production;')
edit('p49d_submit.cpp','values.size()!=5','values.size()!=6')
edit('p49d_submit.cpp','target_values.erase("experts");','target_values.erase("experts");target_values.erase("packed_dense");')
s=json.loads((P/'selection.json').read_text());s['decision']=None;s['choices']['packed_dense']='production';assert s['choices']['experts']=='wide64';(P/'selection.json').write_text(json.dumps(s,indent=2)+'\n')
edit('math_gate.py',"SOURCES=[", "SOURCES=['p74_submit.cpp',")
