#include "route.hpp"
#include "../packet27-round2/core_v2.hpp"
#include <numeric>
namespace p30::route {
void cpu(ng::Shape s,ng::Args a,std::string_view variant){
 bool known=false;for(auto v:variants)known|=variant==v;if(!known)throw std::invalid_argument("route CPU variant");
 if(!*a.i(18)||*a.i(15))return;
 int n=s.width,top=s.extra;float p[512],partial[16],m=-INFINITY;
 for(int i=0;i<n;++i){float v=read(s,a,i);if(!std::isfinite(v)){*a.i(15)=1;return;}m=std::max(m,v);}
 for(int i=0;i<n;++i)p[i]=detmath::exp(read(s,a,i)-m);
 for(int block=0;block<(n+31)/32;++block){float v[32];int count=std::min(32,n-32*block);std::copy_n(p+32*block,count,v);
  for(int d=1;d<32&&d<n;d*=2)for(int i=0;i<count;i+=2*d)v[i]=v[i]+(i+d<count?v[i+d]:0.f);
  partial[block]=v[0];
 }
 float den=tree(partial,(n+31)/32);for(int i=0;i<n;++i)p[i]=p[i]/den;
 float selected[10];int prev=-1;float prevv=INFINITY;
 for(int rank=0;rank<top;++rank){int id=512;float v=-INFINITY;for(int j=0;j<n;++j)if((rank==0||before(prevv,prev,p[j],j))&&before(p[j],j,v,id)){id=j;v=p[j];}selected[rank]=v;prev=id;prevv=v;}
 float sd=tree(selected,top);
 int parts=variant==variants[1]?16:variant==variants[2]?32:1;
 for(int part=0;part<parts;++part)for(int block=part;block<(n+31)/32;block+=parts)for(int lane=0;lane<32;++lane){int j=block*32+lane;if(j>=n)continue;int rank=0;for(int k=0;k<n;++k)rank+=before(p[k],k,p[j],j);if(rank<top)write(a,rank,j,p[j]/sd);}
}
namespace {
void demand(bool ok,const char* why){if(!ok)throw std::runtime_error(why);}
}
int cpu_gate(){int count=0;
 for(int n:{1,3,7,10,17,31,32,33,63,87,127,255,256,511,512})for(int mode=0;mode<7;++mode)for(const char* variant:variants){
  Fixture f(n,std::min(n,10)),inc(n,std::min(n,10));
  for(int j=0;j<n;++j){float v=mode==1?0.f:mode==2?float(j%3):mode==3?(j%2?-0.f:0.f):float((j*37)%113-56)/7.f;f.a.put(0,j,v);inc.a.put(0,j,v);}
  if(mode==4||mode==5){float v=mode==4?NAN:INFINITY;f.a.put(0,n/2,v);inc.a.put(0,n/2,v);}
  if(mode==6)*f.a.i(18)=*inc.a.i(18)=0;
  std::vector<float> pool(65536);integrated::Core c;c.pool={pool.data(),0,pool.size(),0};c.op=integrated::Op::route;c.s[1]=f.s.extra;c.inputs[0]=c.make(n);for(int j=0;j<n;++j)c.inputs[0][j]=f.a.b(0,j);
  validate(f.s,f.a,f.bytes,f.scratch.data(),f.scratch.size()*4,variant);
  cpu(f.s,f.a,variant);ng::cpu(inc.s,inc.a);if(mode!=6)c.run();
  demand(*f.a.i(15)==*inc.a.i(15),"route incumbent rejection");
  if(mode!=6)demand(*f.a.i(15)==c.failed,"route core rejection");
  for(int slot:{2,3,5,6})demand(!std::memcmp(f.a.p[slot],inc.a.p[slot],f.bytes[slot]),"route incumbent bytes");
  if(mode<4)for(int j=0;j<f.s.extra;++j){demand(f.a.i(2)[j]==int(c.out(0)[j]),"route core IDs");demand(std::bit_cast<uint32_t>(f.a.f(3)[j])==std::bit_cast<uint32_t>(c.out(1)[j]),"route core probability bits");}
  ++count;
 }
 // Every entry gets the exact host argument guard, plus rejected short output,
 // scratch, pointer overlap, geometry and unrecognised variant checks.
 for(auto variant:variants){Fixture f(512,10);validate(f.s,f.a,f.bytes,f.scratch.data(),2048,variant);++count;
  for(int bad=0;bad<5;++bad){auto a=f.a;auto s=f.s;auto bytes=f.bytes;size_t sb=2048;std::string_view v=variant;if(bad==0)bytes[3]=3;if(bad==1)sb=2047;if(bad==2)a.p[3]=a.p[2];if(bad==3)s.extra=11;if(bad==4)v="invalid";bool threw=false;try{validate(s,a,bytes,f.scratch.data(),sb,v);}catch(const std::invalid_argument&){threw=true;}demand(threw,"route guard poison accepted");++count;}
 }
 return count;
}
}

#ifdef P30_ROUTE_CPU_MAIN
#include <iostream>
int main(){try{std::cout<<p30::route::cpu_gate()<<"\n";return 0;}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
#endif
