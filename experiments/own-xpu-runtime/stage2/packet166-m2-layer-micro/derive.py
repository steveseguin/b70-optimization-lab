"""Mechanical row-grid pairing of the selected lab kernels, no math edits."""
from pathlib import Path
P=Path(__file__).resolve().parent; B=P/'native/experiments/own-xpu-runtime/stage2/packet136-record-bundle'
def function(text,signature):
 at=text.index(signature); start=text.index('{',at); depth=1;end=start+1
 while depth:
  depth+=(text[end]=='{')-(text[end]=='}');end+=1
 return text[at:end]
out=['#pragma once\n#include "native_headers.hpp"\n#ifndef OWN_RT_HOST_ONLY\nnamespace p166hc {using namespace p60;\n']
for filename,name,groups,namespace in [('p60_kernels.hpp','norm_kernel',40,'p60'),('p60_kernels.hpp','low_inject_kernel',324,'p60'),('p73_hc.hpp','device',640,'p73hc')]:
 s=function((B/filename).read_text(),'inline sycl::event '+name+'(')
 s=s.replace('Bound b,','std::array<p60::Bound,2> bb,unsigned batch,').replace('p60::std::array','std::array')
 s=s.replace('inline sycl::event device(', 'inline sycl::event gate_mix(')
 s=s.replace('640*256,256','batch*640*256,256').replace('(40*256,256','(batch*40*256,256').replace('(L+S)*128,128','batch*(L+S)*128,128')
 s=s.replace('it.get_group_linear_id()', 'local_group')
 marker='[[sycl::reqd_sub_group_size(32)]]{'
 assert marker in s
 s=s.replace(marker,marker+f'\n auto b=bb[it.get_group_linear_id()/{groups}];unsigned local_group=it.get_group_linear_id()%{groups};\n',1)
 if namespace=='p73hc':s=s.replace('chains(', 'p73hc::chains(')
 out.append(s+'\n')
out.append('}\nnamespace p166route {using namespace p109route;\n')
s=function((B/'p109_route.hpp').read_text(),'  sycl::event submit(')
s=s.replace('sycl::event submit(', 'inline sycl::event submit(integrated::Spec spec,unsigned batch,').replace(')const override{','){')
s=s.replace('auto a=route42::bind(spec,p.first(p.size()-3));', 'const unsigned stride=p.size()/batch;std::array<route42::Args,2> aa{};std::array<const uint32_t*,2> positions{};std::array<std::array<void*,3>,2> activations{};for(unsigned r=0;r<batch;++r){auto row=p.subspan(r*stride,stride);aa[r]=route42::bind(spec,row.first(stride-3));positions[r]=static_cast<const uint32_t*>(row[spec.ni+spec.no+spec.nw+2]);for(unsigned j=0;j<3;++j)activations[r][j]=row[stride-3+j];}')
s=s.replace('sycl::nd_range<1>(512,512)','sycl::nd_range<1>(batch*512,512)')
s=s.replace('[[sycl::reqd_sub_group_size(32)]]{','[[sycl::reqd_sub_group_size(32)]]{auto a=aa[it.get_group_linear_id()];auto pos=positions[it.get_group_linear_id()];auto activation_args=activations[it.get_group_linear_id()];')
s=s.replace('sycl::handler& h){','sycl::handler& h){h.depends_on(deps);',1).replace('[=,p35_range0','[=,p35_range0')
out.append(s+'\n}\nnamespace p166down {using namespace p100;\n')
s=function((B/'p100_down.hpp').read_text(),' sycl::event submit(')
s=s.replace('sycl::event submit(', 'inline sycl::event submit(unsigned batch,').replace(')const override{','){')
s=s.replace('auto b=bind(p);unsigned total=rows*count,groups=(total+RowsPerGroup-1)/RowsPerGroup;', 'p100::Kernel<2> op;const unsigned rows=2560,count=10,RowsPerGroup=32,WG=64,P=2,K=640;constexpr bool paired=false;std::array<p39::Bound,2> bounds{op.bind(p.first(19)),op.bind(p.subspan(batch==2?19:0,19))};unsigned total=rows*count,groups=(total+RowsPerGroup-1)/RowsPerGroup;')
s=s.replace('size_t(groups)*WG','size_t(groups)*WG*batch')
s=s.replace('[[sycl::reqd_sub_group_size(32)]]{','[[sycl::reqd_sub_group_size(32)]]{auto b=bounds[it.get_group_linear_id()/groups];unsigned group=it.get_group_linear_id()%groups;')
s=s.replace('logical_row(mapped_group(it.get_group_linear_id(),b.rows,b.count),sub,lane)','p100::Kernel<2>::logical_row(group,sub,lane)').replace('local_tree<V>', 'local_tree<16>').replace('chains((stream?', 'p100::Kernel<2>::chains((stream?')
out.append(s+'\n}\n#endif\n')
(P/'paired_wrappers.hpp').write_text(''.join(out))
