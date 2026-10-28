#!/usr/bin/env python3
"""Create a pinned, opt-in adapter overlay. Never modify canonical runtime files."""
import difflib
import hashlib
import json
import pathlib
import sys

BASE_SHA = '1c3d27e4fc3abfcd0f9ef47c26d701b5b304eaf6446e69034cfdd5ef0b8ded4e'
BASE = pathlib.Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/engine/src/stage2/packet194-expert-diet-engine/adapter.cpp')
HERE = pathlib.Path(__file__).resolve().parent

TIE_PATH = r'''
    // Only selected ties can affect the reference top-ten permutation.
    it.barrier(sycl::access::fence_space::local_space);
    bool internal=false;
    if(j==0)for(int k=1;k<Top;++k)internal|=prob[selected[k-1]]==prob[selected[k]];
    const int cutoff=selected[Top-1];
    const bool tied=sycl::any_of_group(g,internal||(j!=cutoff&&prob[j]==prob[cutoff]));
    if(tied){
     if(j==0){
      int* order=reference_indices.get_multi_ptr<sycl::access::decorated::no>().get();
      auto* stack=reference_frames.get_multi_ptr<sycl::access::decorated::no>().get();
      const float* probability=prob.get_multi_ptr<sycl::access::decorated::no>().get();
      bool valid=router_reference_sort::sort_indices_workspace(probability,order,N,stack);
      // Complete all checks before changing IDs or fused route descriptors.
      for(int rank=0;valid&&rank<Top;++rank){
       const int old=selected[rank],next=order[rank];
       valid=next>=0&&next<N&&prob[old]==prob[next];
       for(int previous=0;valid&&previous<rank;++previous)valid=order[previous]!=next;
       if(valid&&old!=next)valid=sycl::bit_cast<uint32_t>(rb.in(0).get(old))==sycl::bit_cast<uint32_t>(rb.in(0).get(next));
      }
      if(!valid){bad[0]=1;rb.fail();}
      else for(int rank=0;rank<Top;++rank){
       rb.out(0).put(rank,order[rank]);
       if(rb.s.no>=4){rb.out(2).put(rank*3,order[rank]);rb.out(3).put(rank*3,order[rank]);}
      }
     }
     it.barrier(sycl::access::fence_space::local_space);
     if(bad[0])return;
    }
'''

def replace_one(text, old, new):
    assert text.count(old) == 1, old[:100]
    return text.replace(old, new)

def main():
    output = pathlib.Path(sys.argv[1]); output.mkdir()
    original = BASE.read_text()
    assert hashlib.sha256(BASE.read_bytes()).hexdigest() == BASE_SHA
    start = original.index('template<int N,int Top,bool MERGE> struct RouteFast2 ')
    end = original.index('// HC combine and expert gather', start)
    reference = original[start:end]
    candidate = reference.replace('RouteFast2', 'RouteReferenceTie2')
    candidate = replace_one(candidate, '  Bound b{spec,{}};',
        '  if(!spec.f32_activations||(spec.no!=2&&spec.no!=4))throw std::invalid_argument("reference tie route requires F32 and known output geometry");\n  Bound b{spec,{}};')
    anchor = '   sycl::local_accessor<float,1> ex(N,h)'
    candidate = replace_one(candidate, anchor,
        '   sycl::local_accessor<int,1> selected(Top,h),reference_indices(N,h);\n'
        '   sycl::local_accessor<router_reference_sort::Frame,1> reference_frames(router_reference_sort::maximum_depth,h);\n' + anchor)
    candidate = replace_one(candidate, 'auto put=[&](int rank,int index){const float v=prob[index];',
        'auto put=[&](int rank,int index){selected[rank]=index;const float v=prob[index];')
    normalization = '    if(j==0){float sum=subtree<32>(Top,0,[&](int i){return rb.out(1).get(i);});for(int i=0;i<Top;++i)rb.out(1).put(i,rb.out(1).get(i)/sum);}'
    candidate = replace_one(candidate, normalization, TIE_PATH + normalization)
    changed = original[:end] + candidate + original[end:]
    changed = '#include "reference_sort_workspace.hpp"\n' + changed
    switch = '  if(route_fast()&&experts_v2::enabled("route")){RouteFast2<512,10,true> op(s);auto e=d.compute(op,bindings,deps);return {e,e,1};}'
    dispatch = '''  if(reference_route_tie_sort()){
   if(!route_fast())throw std::invalid_argument("reference tie sort requires RouteFast2");
   if(experts_v2::enabled("route")){RouteReferenceTie2<512,10,true> op(s);auto e=d.compute(op,bindings,deps);return {e,e,1};}
   if(experts_v2::enabled("guard")){RouteReferenceTie2<512,10,false> op(s);auto e=d.compute(op,bindings,deps);return {e,e,1};}
   throw std::invalid_argument("reference tie sort requires RouteFast2 treatment");
  }
'''
    changed = replace_one(changed, switch, dispatch + switch)
    anchor = 'inline bool route_fast(){'
    flag = '''inline bool reference_route_tie_sort(){static const bool on=[]{
 const char* e=std::getenv("OWNRT_REFERENCE_ROUTE_TIE_SORT");if(!e||std::string(e)=="0")return false;
 if(std::string(e)=="1")return true;throw std::invalid_argument("OWNRT_REFERENCE_ROUTE_TIE_SORT must be 0 or 1");
 }();return on;}
'''
    changed = replace_one(changed, anchor, flag + anchor)
    guard_anchor = ' if(bindings.size()!=size_t(s.ni+s.no+s.nw+5)||bindings.size()>31)throw std::invalid_argument("adapter binding count");'
    guard = '''
#ifndef OWN_RT_HOST_ONLY
 if(s.op==Op::route&&reference_route_tie_sort()){
  if(s.special!=Special::normal||(s.implementation!=1&&s.implementation!=11)||s.sizes[0]!=512||s.site.shape[1]!=10||!s.f32_activations||(s.no!=2&&s.no!=4)||s.tokens<1||!route_fast()||(!experts_v2::enabled("route")&&!experts_v2::enabled("guard")))
   throw std::invalid_argument("reference tie sort unsupported route treatment");
 }
#endif
'''
    changed = replace_one(changed, guard_anchor, guard_anchor + guard)
    assert changed.count(reference) == 1  # disabled original class remains exact
    (output / 'adapter.cpp').write_text(changed)
    (output / 'route-reference-class.inc').write_text(candidate)
    capture_classes = ''
    for name, body, capture_name in [('RouteFast2', reference, 'RouteOriginalCapture2'),
                                     ('RouteReferenceTie2', candidate, 'RouteReferenceCapture2')]:
        body = body.replace(name, capture_name)
        line = '    prob[j]=ex[j]/den;it.barrier(sycl::access::fence_space::local_space);'
        body = replace_one(body, line, line+'\n    static_cast<float*>(b.scratch())[r*N+j]=prob[j];')
        capture_classes += body
    (output / 'route-capture-classes.inc').write_text(capture_classes)
    for name in ('reference_sort.hpp', 'reference_sort_workspace.hpp'):
        (output / name).write_bytes((HERE / name).read_bytes())
    patch = ''.join(difflib.unified_diff(original.splitlines(True), changed.splitlines(True),
                    fromfile='a/engine/src/stage2/packet194-expert-diet-engine/adapter.cpp',
                    tofile='b/engine/src/stage2/packet194-expert-diet-engine/adapter.cpp'))
    (output / 'adapter.patch').write_text(patch)
    records = {name: hashlib.sha256((output / name).read_bytes()).hexdigest() for name in
               ('adapter.cpp','adapter.patch','route-reference-class.inc','route-capture-classes.inc','reference_sort.hpp','reference_sort_workspace.hpp')}
    (output / 'source.json').write_text(json.dumps(dict(schema='ownrt.reference-route-overlay.v1',
        canonical_path=str(BASE), canonical_sha256=BASE_SHA, canonical_edited=False,
        default_enabled=False, treatment_flag='OWNRT_REFERENCE_ROUTE_TIE_SORT=1',
        original_route_class_sha256=hashlib.sha256(reference.encode()).hexdigest(),
        output_files=records), indent=2)+'\n')
    print(json.dumps(records))

if __name__ == '__main__':
    main()
