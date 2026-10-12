#define OWN_RT_HOST_ONLY
#include "p30_attention.hpp"
#include "core_v2.hpp"
#include <iostream>
#include <set>
namespace {
unsigned checks=0;
void require(bool ok,const char* what){++checks;if(!ok)throw std::runtime_error(what);}
void incumbent(p30::attention::Fixture& f){auto s=f.shape;auto a=f.args();for(int op:{ng::attention_score,ng::attention_softmax,ng::attention_value}){s.op=op;ng::cpu(s,a);}}
// Actual arithmetic-v2 reference core. Scratch arena stays below 512 MiB.
int core(p30::attention::Fixture& f,std::vector<float>& scratch){
 integrated::Core c;c.pool={scratch.data(),0,scratch.size(),0};c.op=integrated::Op::qsa_attention;c.g.context=f.shape.capacity;c.g.budget=f.shape.budget;auto a=f.args();c.position=a.i(17)[0];
 for(int slot=0;slot<5;++slot){int n=slot<2?6144:slot<4?f.shape.capacity*512:f.shape.budget+3;c.inputs[slot]=c.make(n);for(int j=0;j<n;++j)c.inputs[slot][j]=slot==4?float(a.i(slot)[j]):a.b(slot,j);}
 c.run();if(c.failed||c.pool.failed)return 1;for(int j=0;j<6144;++j)a.put(5,j,c.out(0)[j]);return 0;
}
}
int main(){try{
 using namespace p30::attention;std::vector<float> scratch(128ull*1024*1024);
 // Exhaustive odd-tail boundaries, cancellation, ties and signed zeros.
 for(int n=1;n<=2051;++n){std::vector<float> x(n);for(int j=0;j<n;++j)x[j]=j%11==0?-0.f:float((j*17)%37-18)*std::ldexp(1.f,j%19-9);auto y=x;require(std::bit_cast<uint32_t>(blocked_tree(x.data(),n))==std::bit_cast<uint32_t>(tree(y.data(),n)),"blocked tree identity");}
 unsigned valid_fixtures=0;
 std::vector<std::array<int,3>> cases{{1,1,4},{1,2,4},{3,3,4},{3,4,4},{87,7,4},{87,87,2048},{87,88,2048},{255,255,2048},{255,256,2048},{2050,2051,2048}};for(int n=88;n<=152;++n)cases.push_back({n-1,n,2048});
 for(auto [pos,n,budget]:cases){
  Fixture base(pos,n,budget,pos<256?256:4096),inc=base,ref=base;incumbent(inc);require(core(ref,scratch)==0,"core finite fixture");require(inc.data[5]==ref.data[5],"incumbent == core");
  for(int v=0;v<variants;++v){auto test=base;validate(test.shape,test.args(),test.extents(),v);++checks;cpu(test.shape,test.args(),v);require(test.data[5]==inc.data[5],"candidate == incumbent output");require(test.data[15]==inc.data[15],"candidate == incumbent error");require(test.data[6]==inc.data[6],"full score scratch == incumbent");require(test.data[7]==inc.data[7],"full probability scratch == incumbent");
   auto a=test.args(),b=inc.args();for(int h=0;h<24;++h)for(int j=0;j<n;++j){int at=h*(budget+3)+j;require(std::bit_cast<uint32_t>(a.f(6)[at])==std::bit_cast<uint32_t>(b.f(6)[at]),"score identity");require(std::bit_cast<uint32_t>(a.f(7)[at])==std::bit_cast<uint32_t>(b.f(7)[at]),"probability identity");}
  }++valid_fixtures;
 }
 // Explicit existing disagreement: empty selection leaves incumbent untouched;
 // Core rejects empty attention. This is a diagnostic, never a triple pass.
 Fixture empty(0,0,4,256),ei=empty,er=empty;incumbent(ei);require(core(er,scratch)==1,"core rejects empty");for(int v=0;v<variants;++v){auto ec=empty;cpu(ec.shape,ec.args(),v);require(ec.data[5]==ei.data[5]&&ec.data[15]==ei.data[15],"empty incumbent semantics");}
 // Real qsa_select tie fixture: zero vectors => stable ascending block IDs,
 // then append the unpooled tail. This exercises the runtime selection path.
 {ng::Shape s{ng::select,1,2560,4,0,0,128,4};auto ext=ng::required_bytes(s);std::array<std::vector<uint32_t>,19> d;ng::Args a;for(int j=0;j<19;++j){d[j].resize((ext[j]+3)/4);a.p[j]=d[j].data();}a.i(17)[0]=10;a.i(18)[0]=1;ng::cpu(s,a);int want[]={0,1,2,3,8,9,10};for(int j=0;j<7;++j)require(a.i(2)[j]==want[j],"selection stable ties");
  integrated::Core c;c.pool={scratch.data(),0,scratch.size(),0};c.op=integrated::Op::qsa_select;c.g.context=128;c.g.budget=4;c.position=10;c.inputs[0]=c.make(512);c.inputs[1]=c.make(32*128);c.run();require(!c.failed,"core selection ties");for(int j=0;j<7;++j)require(int(c.out(0)[j])==want[j],"core stable ties");}
 // Device-path argument validation, all variants: truncated, null, alias,
 // bad shape, and invalid selected ID control behavior.
 for(int v=0;v<variants;++v){Fixture f(87,88,2048,256);auto ext=f.extents();auto a=f.args();validate(f.shape,a,ext,v);++checks;
  for(int mode=0;mode<5;++mode){auto bad=a;auto sz=ext;auto s=f.shape;if(mode==0)sz[2]=0;if(mode==1)bad.p[5]=nullptr;if(mode==2)bad.p[5]=bad.p[0];if(mode==3)s.extra=3000;if(mode==4)bad.p[2]=reinterpret_cast<void*>(UINTPTR_MAX-1);bool caught=false;try{validate(s,bad,sz,v);}catch(const std::invalid_argument&){caught=true;}require(caught,"argument rejection");}
  a.i(4)[0]=4096;cpu(f.shape,a,v);require(a.i(15)[0]==1,"invalid selected ID");
 }
 std::cout<<"{\"checks\":"<<checks<<",\"finite_fixtures\":"<<valid_fixtures<<",\"variants\":2,\"empty_core_incumbent_disagreement\":true,\"device_ran\":false,\"passed\":true}\n";return 0;
 }catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
