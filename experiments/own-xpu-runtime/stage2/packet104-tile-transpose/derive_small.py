"""Address-only target shared Q6 / F32 router tuple derivatives."""
from build_engine import P,limits
def main():
 limits()
 s=(P/'p49d_small.hpp').read_text()
 s=s.replace('#include "p49c_kernel.hpp"','#include "p49c_kernel.hpp"\n#include "p104_layout.hpp"\n#include "p49d_small.hpp"')
 s=s.replace('namespace p49dvirtual {','namespace p104small {\nusing namespace p49dvirtual;\n'+'''
template<Type T,unsigned K,bool Tiled>inline const uint8_t* address(const uint8_t*w,size_t row,size_t rb,size_t byte){
 if constexpr(!Tiled)return w+row*rb+byte;
 else if constexpr(T==Type::F32)return p104::address(w,row,rb,0,32,byte);
 else {static_assert(T==Type::Q6_K);return byte<K?p104::address(w,row,rb,0,8,byte):p104::address(w,row,rb,K,4,byte-K);}
}
''')
 s=s.replace('template<Type T,unsigned K,unsigned V>','template<Type T,unsigned K,unsigned V,bool Tiled>')
 s=s.replace('unsigned physical){','unsigned physical,size_t source,size_t rb){')
 for expr in ('K+4*(k/G)','k+4','k','4*(k+j)'):
  s=s.replace('load32(w+'+expr+')','load32(address<T,K,Tiled>(w,source,rb,'+expr+'))')
 s=s.replace('template<Type T,unsigned K,unsigned Split,unsigned V>','template<Type T,unsigned K,unsigned Split,unsigned V,bool Tiled>')
 s=s.replace('dense_host(const uint8_t*w,const uint16_t*x){','dense_host(const uint8_t*w,const uint16_t*x,size_t source,size_t rb){')
 s=s.replace('dense_chains<T,K,V>(w,x,bounds.first,bounds.second,p)','dense_chains<T,K,V,Tiled>(w,x,bounds.first,bounds.second,p,source,rb)')
 s=s.replace('unsigned V,p39::Kind E>','unsigned V,p39::Kind E,bool Tiled>')
 s=s.replace('dense_chains<T,K,V>(b.w+size_t(row)*b.rb,b.x,bounds.first,bounds.second,physical)','dense_chains<T,K,V,Tiled>(b.w,b.x,bounds.first,bounds.second,physical,row,b.rb)')
 s=s.replace('template<unsigned V>struct SmallKernel','template<unsigned V,bool Q6,bool Router>struct SmallKernel')
 a=s.index(' void run(');b=s.index('\n#else',a)
 s=s[:a]+''' void run(std::span<void*const>p)const override{auto bs=bind(p);for(unsigned j=0;j<4;++j){auto b=bs[j];for(unsigned row=0;row<b.rows;++row){
 if(j==0)b.y[row]=dense_host<Type::F32,2560,4,V,Router>(b.w,b.x,row,b.rb);
 else if(j==3)b.y[row]=dense_host<Type::F32,2560,4,V,false>(b.w,b.x,row,b.rb);
 else b.y[row]=dense_host<Type::Q6_K,2560,4,V,Q6>(b.w,b.x,row,b.rb);
 }}}
'''+s[b:]
 s=s.replace('V,p39::Kind::expert_checks>(b[0]','V,p39::Kind::expert_checks,Router>(b[0]')
 for j in (1,2):s=s.replace(f'V,p39::Kind::expert_checks>(b[{j}]',f'V,p39::Kind::expert_checks,Q6>(b[{j}]')
 s=s.replace('V,p39::Kind::expert_checks>(b[3]','V,p39::Kind::expert_checks,false>(b[3]')
 (P/'p104_small.hpp').write_text(s)
 print('selected target tuple address derivatives generated')
if __name__=='__main__':main()
