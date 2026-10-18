"""Deterministic private expert partition instrumentation; original arithmetic retained."""
from pathlib import Path
from measure_source import P, once

def generate():
    base=P/'frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port'
    checked=base/'build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port'
    for name in ('p49d_expert.hpp','p100_down.hpp'):
        s=(P/'native/templates'/name).read_text()
        s='#include "'+str(P/'native/partition.hpp')+'"\n'+s
        # Only qualified gate/up stream arm and tile16 down are partitioned.
        target='return ownrt::prepared_submit(q,'
        s=s.replace(target,'return p58af::prepared_submit(q,',1)
        opening='(sycl::handler& h){'
        i=s.index('return p58af::prepared_submit')
        s=s[:i]+s[i:].replace(opening,opening+'const int part=p58af::partition;const auto cache_begin=p58af::cache_begin,cache_end=p58af::cache_end;',1)
        if name=='p49d_expert.hpp':
            hook='   if(valid){size_t source=size_t(route.expert_id)*b.rows+route.row_begin+row;value='
            filt='   if(!p58af::selected(part,ok,ok?reinterpret_cast<uintptr_t>(p58::resolve(b.w,size_t(route.expert_id)*b.rows*b.rb,size_t(b.rows)*b.rb,b.indirect)):0,cache_begin,cache_end))return;\n'
            s=once(s,hook,filt+hook)
            hook='    if(!row){b.status[slot]=!ok;'
            filt='    if(!p58af::selected(p58af::partition,ok,ok?reinterpret_cast<uintptr_t>(p58::resolve(b.w,size_t(r.expert_id)*rows*b.rb,size_t(rows)*b.rb,b.indirect)):0,p58af::cache_begin,p58af::cache_end))continue;\n'
            s=once(s,hook,filt+hook)
        else:
            hook='    float value=0;if(valid)'
            filt='    if(!p58af::selected(part,ok,ok?reinterpret_cast<uintptr_t>(p58::resolve(b.w,size_t(route.expert_id)*b.rows*row_bytes,size_t(b.rows)*row_bytes,b.indirect)):0,cache_begin,cache_end))return;\n'
            s=once(s,hook,filt+hook)
            hook='   float values[P]{};if(valid)'
            filt='   if(!p58af::selected(p58af::partition,ok,ok?reinterpret_cast<uintptr_t>(p58::resolve(b.w,size_t(route.expert_id)*rows*row_bytes,size_t(rows)*row_bytes,b.indirect)):0,p58af::cache_begin,p58af::cache_end))continue;\n'
            s=once(s,hook,filt+hook)
        s=s.replace('if(!p58af::selected(part,','if(part&&!p58af::selected(part,')
        s=s.replace('if(!p58af::selected(p58af::partition,','if(p58af::partition&&!p58af::selected(p58af::partition,')
        (checked/name).write_text(s)
    # Compile this TU anew: these kernels otherwise live in a frozen parent object.
    s=(base/'p49d_expert_submit.cpp').read_text()
    for name in ('p49d_submit.hpp','p49d_expert.hpp','p100_down.hpp','expert_down.hpp'):
        s=s.replace('#include "'+name+'"','#include "'+str(checked/name)+'"')
    (P/'build/native/expert.cpp').write_text(s)

if __name__=='__main__':generate()
