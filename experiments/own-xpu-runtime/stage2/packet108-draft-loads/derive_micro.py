"""Adapt packet104's real-route paired harness, keeping its timing discipline."""
from pathlib import Path
P=Path(__file__).resolve().parent
def main():
    from build_engine import limits
    limits()
    src=(P.parent/'packet104-tile-transpose/microbench.cpp').read_text()
    start=src.index('#include <csignal>')
    end=src.index('template<bool HC>struct Target')
    common=src[start:end]
    begin=src.index('template<class Op,bool Tiled>sycl::event raw_kernel')
    end=src.index('#include "micro_small.hpp"')
    harness=src[begin:end]
    # Layout and bank addresses are unchanged: one control/candidate weight set.
    harness=harness.replace('auto*t=b.alloc<uint8_t>(bytes);','auto*t=w;')
    harness=harness.replace('auto*pt=Op::paired?b.alloc<uint8_t>(bytes):t;','auto*pt=peer;')
    harness=harness.replace('auto trans=Op::transpose(raw.data(),nr);','')
    harness=harness.replace('q.memcpy((stream?pt:t)+size_t(first)*Op::rb,trans.data(),trans.size()).wait_and_throw();','')
    harness=harness.replace('uint32_t seed=104','uint32_t seed=108')
    harness=harness.replace(' FP32/BF16/epilogue/status mismatch',' FP32/BF16/status mismatch')
    desc='''template<unsigned Columns,bool Pair>struct Draft {
 static constexpr unsigned K=Columns,rows=K==2560?640:2560,count=10,experts=512,wg=128,lanes=32;
 static constexpr size_t rb=K+K/16*4;static constexpr bool paired=Pair,routed=true;
 using Prod=p108base::Dense<K,true,Pair>;using Candidate=p108::Dense<K,true,Pair>;
 static const char*name(){return Pair?"draft-gate-load8":"draft-down-load8";}
 template<class Next>static void initialize(std::vector<uint8_t>&v,Next next){
  for(size_t r=0;r<v.size()/rb;++r){auto*p=v.data()+r*rb;
   for(unsigned k=0;k<K;++k)p[k]=next()>>24;
   for(unsigned k=0;k<K/16;++k){float f=float(1+next()%63)/128.f;std::memcpy(p+K+4*k,&f,4);}
  }
 }
 template<bool Changed>static float raw(const uint8_t*w,const uint16_t*x,size_t row,unsigned lane){
  if constexpr(Changed)return p108::lane<K,true>(w+row*rb,x,lane);
  else return p108base::lane<K,true>(w+row*rb,x,lane);
 }
 static sycl::event launch(sycl::queue&q,bool changed,const std::array<void*,19>&p){
  mtp36::Linear a;a.rows=rows;a.columns=K;a.batch=count;a.experts=experts;a.int8=true;a.paired=Pair;a.routes=ownrt::Allocation{1};
  if(changed){Candidate op;op.a=a;return op.submit(q,std::span<void*const>(p.data(),8),{});}
  Prod op;op.a=a;return op.submit(q,std::span<void*const>(p.data(),8),{});
 }
};
'''
    main=src[src.index('int main(int argc'):]
    a=main.index('  benchmark<Target<false>>')
    b=main.index('  q.wait_and_throw();guard();}',a)
    main=main[:a]+'  benchmark<Draft<2560,true>>(q,rs);benchmark<Draft<640,false>>(q,rs);\n'+main[b:]
    main=main.replace('candidate_count\\\":9','candidate_count\\\":2')
    (P/'microbench.cpp').write_text('// Packet108: unchanged mtp36 geometry, raw load-only candidate.\n#include "p108_base.hpp"\n#include "p108_loads.hpp"\n'+common+desc+harness+main)
    gate=(P.parent/'packet104-tile-transpose/micro_gate.py').read_text()
    a=gate.index('CANDIDATES=');b=gate.index('def require(',a)
    gate=gate[:a]+'''CANDIDATES=('draft-gate-load8','draft-down-load8')
MICRO_DIRECTORY='evidence/micro-B'
SHAPES={'draft-gate-load8':(640,2560,10,512,128,0),
        'draft-down-load8':(2560,640,10,512,128,0)}
'''+gate[b:]
    (P/'micro_gate.py').write_text(gate.replace('packet104','packet108'))
    print('Derived two-arm real-route proxy micro and unchanged 15% stratum/order gate.')
if __name__=='__main__':main()
