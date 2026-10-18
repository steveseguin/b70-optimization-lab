"""Compile mirror adaptations; source packets remain byte-for-byte read-only.

Retain single-matrix packet18 GEMV arithmetic. Remove dormant matrix-descriptor
search and oversized capture arrays. Format is chosen on the host and compiled
as a template argument. No device parameter allocation or indirection.
"""
import re

def apply(path,text):
 name=path.parent.name
 if path.name!='kernels.cpp' or name not in ('packet6-kopt','packet7-kopt2','packet8-kopt3'):return text
 def replace(old,new):
  nonlocal text
  assert old in text,(path,old)
  text=text.replace(old,new)
 if name=='packet6-kopt':
  replace('template<unsigned SG> sycl::event run(', 'template<Type T,unsigned SG> sycl::event run(')
  replace('auto descriptions=desc;auto count=matrices;', 'if(matrices!=1)throw std::invalid_argument("packet26 single-matrix kernel");auto description=desc[0];')
  replace('std::array<void*,28> pointers{};', 'std::array<void*,8> pointers{};if(p.size()>pointers.size())throw std::invalid_argument("packet26 capture extent");')
  replace('unsigned which=0;for(unsigned j=1;j<count;++j)if(group>=descriptions[j].first_group)which=j;\n          auto d=descriptions[which];', 'auto d=description;')
  replace('dispatch_dot<SG>(d.type,', 'dot<T,SG>(')
  replace('return subgroup==16?run<16>(q,p,deps):run<32>(q,p,deps);', 'switch(desc[0].type){\n#define P26_CASE(T) case Type::T:return subgroup==16?run<Type::T,16>(q,p,deps):run<Type::T,32>(q,p,deps)\nP26_CASE(F32);P26_CASE(F16);P26_CASE(BF16);P26_CASE(Q8_0);P26_CASE(Q6_K);P26_CASE(Q3_K);P26_CASE(IQ3_XXS);P26_CASE(IQ2_S);P26_CASE(IQ3_S);P26_CASE(IQ4_NL);\n#undef P26_CASE\n}throw std::invalid_argument("type");')
 else:
  template='unsigned BYTES' if name=='packet7-kopt2' else 'bool SLM'
  replace('template<'+template+'> sycl::event run(', 'template<Type T,'+template+'> sycl::event run(')
  replace('auto descriptors=desc;auto nm=count,ns=split;', 'if(count!=1)throw std::invalid_argument("packet26 single-matrix kernel");auto description=desc[0];auto ns=split;')
  replace('std::array<void*,64> ptr{};', 'std::array<void*,8> ptr{};if(p.size()>ptr.size())throw std::invalid_argument("packet26 capture extent");')
  replace('unsigned which=0;for(unsigned j=1;j<nm;++j)if(group>=descriptors[j].first)which=j;\n        auto d=descriptors[which];', 'auto d=description;')
  if name=='packet8-kopt3':
   replace('dispatch_dot(d.type,','dot<T>(')
   ret='return slm?run<true>(q,p,deps):run<false>(q,p,deps);'
   call='return slm?run<Type::T,true>(q,p,deps):run<Type::T,false>(q,p,deps)'
  else:
   ret='return bytes==32?run<32>(q,p,deps):run<64>(q,p,deps);'
   call='return bytes==32?run<Type::T,32>(q,p,deps):run<Type::T,64>(q,p,deps)'
  replace(ret,'switch(desc[0].type){\n#define P26_CASE(T) case Type::T:'+call+'\nP26_CASE(F32);P26_CASE(F16);P26_CASE(BF16);P26_CASE(Q8_0);P26_CASE(Q6_K);P26_CASE(Q3_K);P26_CASE(IQ3_XXS);P26_CASE(IQ2_S);P26_CASE(IQ3_S);P26_CASE(IQ4_NL);\n#undef P26_CASE\n}throw std::invalid_argument("type");')
  # Only the synthetic mini model asks for paired F32 matrices here. Preserve
  # each arithmetic tree, with separate submissions; real expert kernels stay p18.
  marker='  if(matrices.empty() || matrices.size()>8)'
  prefix='  if(matrices.size()>1){Launch all{};for(const auto& m:matrices){auto one=multiply(device,{m},variant);if(!all.first)all.first=one.first;all.last=one.last;all.passes+=one.passes;}return all;}\n'
  replace(marker,prefix+marker)
 # Within the submitted kernel, the format now is a compile-time constant.
 start=text.index('  template<Type T,');end=text.index('  sycl::event submit(',start)
 text=text[:start]+text[start:end].replace('d.type','T')+text[end:]
 return text
