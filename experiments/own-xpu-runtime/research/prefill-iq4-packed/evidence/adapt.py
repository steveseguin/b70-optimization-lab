from pathlib import Path
p=Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime/research/prefill-iq4-packed/bench')
s=(p/'original_test.cpp').read_text().replace('#include <sycl/sycl.hpp>','#include "group_iq4_packed.hpp"\n#include "harness.hpp"\n#include <fstream>\n#include <chrono>')
s=s.replace('auto dev=sycl::device(sycl::cpu_selector_v)','auto dev=sycl::device(sycl::gpu_selector_v)').replace('sycl::property::queue::in_order());','{sycl::property::queue::in_order(),sycl::property::queue::enable_profiling()});')
a=s.index(' int f=0;\n f+=run<');b=s.index('\n return f;}',a)
s=s[:a]+''' int f=run<F,1,4,4,128>(q,c,n,w,x,r,want,st);'''+s[b:]
old='q.submit([&](sycl::handler& h){h.parallel_for(p.range,kernel);}).wait();'
new='''auto reference=[&](){return q.submit([&](sycl::handler& h){h.parallel_for(p.range,kernel);});};
 auto candidate=[&](){return packed_group::launch(q,w,x,y,order,tiles,cnt,c.rows,c.k,c.rb,n,c.experts);};
 std::vector<float> production_want;
 if(c.rows==2560){reference().wait_and_throw();production_want.assign(y,y+size_t(n)*c.rows);}
 candidate().wait_and_throw();'''
s=s.replace(old,new).replace('std::memcpy(&bw,&want[i],4);','std::memcpy(&bw,c.rows==2560?&production_want[i]:&want[i],4);')
s=s.replace(' sycl::free(y,q);',' if(!bad&&c.rows==2560){Bench b(q,y,size_t(n)*c.rows);b.add("incumbent_xgroup_1x4",reference);b.add("packed_logical4_T4",candidate);b.run(6,8);}\n sycl::free(y,q);')
s=s.replace('for(uint32_t s=0;s<n;++s){const Route r=routes[s];','if(c.rows==2560){std::ifstream f("routes256.bin",std::ios::binary);f.read(reinterpret_cast<char*>(routes),n*sizeof(Route));if(!f)throw std::runtime_error("route census read");}\n  if(c.rows!=2560)for(uint32_t s=0;s<n;++s){const Route r=routes[s];')
a=s.index(' for(int mode:{0,1})');b=s.index(' printf("TOTAL FAILS',a)
s=s[:a]+''' for(int mode:{0,1})for(uint32_t tokens:{1u,7u,32u})for(uint32_t k:{256u,640u,768u}){
  Case c{"IQ4_NLd",41,k,k/32*18,9,halfblocks(18,k/32,0),ref_kopt<Type::IQ4_NL>};go(c,xgroup::C8<Kopt<Type::IQ4_NL>>{},tokens,mode);
  if(fails)return 1;
 }
 {Case c{"IQ4_prod",2560,640,360,512,halfblocks(18,20,0),ref_kopt<Type::IQ4_NL>};go(c,xgroup::C8<Kopt<Type::IQ4_NL>>{},256,0);}
'''+s[b:]
(p/'bench.cpp').write_text(s)
