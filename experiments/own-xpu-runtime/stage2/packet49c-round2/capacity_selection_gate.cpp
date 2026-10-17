#define OWN_RT_HOST_ONLY
#include "core_v2.hpp"
#include "round2.hpp"
#include "p30_attention.hpp"
#include <iostream>
#include <set>
#include <cstring>
namespace {
unsigned checks=0,cases=0,attention_cases=0,nonfinite_cases=0;
uint64_t digest=1469598103934665603ull;
void check(bool b,const char* label){++checks;if(!b)throw std::runtime_error(label);}
void hash(const void* ptr,size_t bytes){auto p=static_cast<const unsigned char*>(ptr);while(bytes--){digest^=*p++;digest*=1099511628211ull;}}
struct Selection {
 ng::Shape s;std::array<std::vector<uint32_t>,19> d;
 Selection(int capacity,int n,int pattern):s{ng::select,1,2560,4,0,0,capacity,2048}{
  s.extent=std::min(capacity,((n+31)/32)*32);
  auto ext=ng::required_bytes(s);for(int j=0;j<19;++j)d[j].resize((ext[j]+3)/4);auto a=args();
  for(int j=0;j<512;++j)a.put(0,j,pattern==1?0.f:float((j*7)%23-11)/16.f);
  for(int b=0;b<(capacity+3)/4;++b)for(int k=0;k<128;++k){int seed=pattern==2?b%13:b;float v=float((seed*71+k*17+seed*k*3)%127-63)/32.f;a.put(1,b*128+k,v);}
  a.i(17)[0]=n-1;a.i(18)[0]=1;std::fill_n(a.i(2),2051,-777);
 }
 ng::Args args(){ng::Args a;for(int j=0;j<19;++j)a.p[j]=d[j].data();return a;}
};
std::vector<int> reference(Selection& f,std::vector<float>& arena,bool bad=false){
 auto a=f.args();integrated::Core c;c.pool={arena.data(),0,arena.size(),0};c.op=integrated::Op::qsa_select;c.g.context=f.s.capacity;c.position=a.i(17)[0];
 for(int slot=0;slot<2;++slot){int size=slot?((f.s.capacity+3)/4)*128:512;c.inputs[slot]=c.make(size);for(int j=0;j<size;++j)c.inputs[slot][j]=a.b(slot,j);}
 c.run();check(!c.pool.failed,"core arena bound");check(bool(c.failed)==bad,"core finite guard");std::vector<int> result;if(!bad)for(auto v:c.out(0))result.push_back(int(v));return result;
}
void attention(int capacity,int n,const std::vector<int>& ids,std::vector<float>& arena){
 using namespace p30::attention;int admitted=std::min(n/4,512)*4+n%4;
 Fixture base(n-1,admitted,2048,capacity);base.shape.extent=std::min(capacity,((n+31)/32)*32);auto a=base.args();std::copy(ids.begin(),ids.end(),a.i(4));
 auto inc=base;for(int op:{ng::attention_score,ng::attention_softmax,ng::attention_value}){auto s=inc.shape;s.op=op;ng::cpu(s,inc.args());}
 integrated::Core c;c.pool={arena.data(),0,arena.size(),0};c.op=integrated::Op::qsa_attention;c.g.context=capacity;c.position=n-1;
 for(int slot=0;slot<5;++slot){int count=slot<2?6144:slot<4?capacity*512:2051;c.inputs[slot]=c.make(count);for(int j=0;j<count;++j)c.inputs[slot][j]=slot==4?float(a.i(4)[j]):a.b(slot,j);}
 c.run();if(c.failed||c.pool.failed)throw std::runtime_error("attention core valid capacity="+std::to_string(capacity)+" n="+std::to_string(n)+" core="+std::to_string(c.failed)+" arena="+std::to_string(c.pool.failed)+" used="+std::to_string(c.pool.used));for(int j=0;j<6144;++j)check(ng::Args::bits(c.out(0)[j])==static_cast<uint16_t*>(inc.args().p[5])[j],"attention oracle exact");
 for(int variant=0;variant<2;++variant){auto f=base;cpu(f.shape,f.args(),variant);for(int slot:{5,6,7,15})check(f.data[slot]==inc.data[slot],"p30 full buffer parity");}
 auto r=base;float scratch=0;auto stage=[&]<ng::Op Op>(){auto s=r.shape;s.op=Op;round2::cpu_stage<Op,0>(s,r.args(),&scratch);};stage.template operator()<ng::attention_score>();stage.template operator()<ng::attention_softmax>();stage.template operator()<ng::attention_value>();for(int slot:{5,6,7,15})check(r.data[slot]==inc.data[slot],"round2 attention full buffer parity");
 hash(inc.data[5].data(),inc.data[5].size()*4);++attention_cases;
}
}
int main(){try{
 std::vector<float> arena(192ull*1024*1024);
 for(int capacity:{4096,32768})for(int n:{2047,2048,2049,2051,2052,4095,4096,8192,32767})if(n<=capacity){
  for(int pattern=0;pattern<3;++pattern){Selection input(capacity,n,pattern);auto want=reference(input,arena);check(want.size()==2051,"selection width");int count=std::min(n/4,512)*4+n%4;std::set<int> seen;
   for(int j=0;j<2051;++j){if(j<count){check(want[j]>=0&&want[j]<n,"causal selection");check(seen.insert(want[j]).second,"unique selection");}else check(want[j]==-1,"selection suffix");}
   for(int j=0;j<n%4;++j)check(want[std::min(n/4,512)*4+j]==n-n%4+j,"tail admission");
   if(pattern==1)for(int j=0;j<std::min(n/4,512)*4;++j)check(want[j]==j,"lower block tie wins");
   for(int backend=0;backend<3;++backend){auto f=input;auto a=f.args();if(backend==0)ng::cpu(f.s,a);else if(backend==1){std::vector<float> scratch(round2::scratch_floats(f.s));round2::cpu_stage<ng::select,0>(f.s,a,scratch.data());round2::cpu_stage<ng::select,1>(f.s,a,scratch.data());}else specialised::cpu_class<ng::select>(f.s,a);
    check(!a.i(15)[0],"finite selection status");check(std::equal(want.begin(),want.end(),a.i(2)),"exact real-core selection parity");hash(a.i(2),2051*4);
   }
   if(pattern==0)attention(capacity,n,want,arena);++cases;
  }
  Selection invalid(capacity,n,0);invalid.args().put(0,0,INFINITY);reference(invalid,arena,true);
  for(int backend=0;backend<3;++backend){auto f=invalid;auto a=f.args();if(backend==0)ng::cpu(f.s,a);else if(backend==1){std::vector<float> scratch(round2::scratch_floats(f.s));round2::cpu_stage<ng::select,0>(f.s,a,scratch.data());round2::cpu_stage<ng::select,1>(f.s,a,scratch.data());}else specialised::cpu_class<ng::select>(f.s,a);check(a.i(15)[0]==1,"nonfinite rejected");for(int j=0;j<2051;++j)check(a.i(2)[j]==-1,"nonfinite selection cleared");++nonfinite_cases;}
 }
 std::cout<<"{\"passed\":true,\"device_executed\":false,\"checks\":"<<checks<<",\"selection_fixtures\":"<<cases<<",\"attention_fixtures\":"<<attention_cases<<",\"nonfinite_backend_fixtures\":"<<nonfinite_cases<<",\"selection_backends\":3,\"attention_candidates\":3,\"diagnostic_fnv64\":"<<digest<<"}\n";
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
