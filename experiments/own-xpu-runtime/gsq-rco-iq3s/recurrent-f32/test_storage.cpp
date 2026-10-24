// Focused CPU-only proof source; compilation/execution are root-owned.
#include "source/kernels.hpp"
#include "source/plan.hpp"
#include "recurrent_policy.hpp"
#include <cstring>
#include <iostream>
#include <limits>
static unsigned checks;
static void check(bool b,const char* s){++checks;if(!b)throw std::runtime_error(s);}
static uint32_t bits(float x){return std::bit_cast<uint32_t>(x);}
template<class F>static void rejects(F f){bool threw=false;try{f();}catch(const std::invalid_argument&){threw=true;}check(threw,"required refusal");}
static void plan_check(){
 flash::Geometry g;g.context=4096;std::vector<bool> full(48);for(int i=0;i<48;++i)full[i]=(i%4==3);
 auto p=flash::Builder(g).build(full);unsigned states=0,histories=0,ple=0,kv=0;size_t delta[2]{};
 for(const auto& b:p.buffers){
  bool s=b.name.ends_with(".gdn.state"),h=b.name.ends_with(".gdn.history"),q=b.name.ends_with(".ple.history");
  if(s||h||q){check(b.type==flash::Scalar::f32,"F32 planned recurrence");size_t n=1;for(int d:b.shape)n*=d;check(b.card==0||b.card==1,"recurrence owner");delta[b.card]+=n*2;states+=s;histories+=h;ple+=q;}
  if(b.name.ends_with(".keys")||b.name.ends_with(".values")||b.name.ends_with(".raw")||b.name.ends_with(".pooled")){check(b.type==flash::Scalar::bf16,"unchanged BF16 KV");++kv;}
 }
 check(states==36&&histories==36&&ple==1,"exact73 recurrent buffers");check(kv==48,"12 attention layers four BF16 stores");
 check(delta[0]==29601792&&delta[1]==29417472,"per-primary-bank delta");
}
static void admissions(){
 enum class D{bf,f32,other};using recurrent_f32::admit;
 check(admit(D::f32,D::f32,D::bf,D::f32,0)==16,"F32 policy");check(admit(D::bf,D::bf,D::bf,D::f32,0)==0,"explicit legacy policy");
 rejects([&]{admit(D::f32,D::bf,D::bf,D::f32,0);});rejects([&]{admit(D::other,D::other,D::bf,D::f32,0);});rejects([&]{admit(D::f32,D::f32,D::bf,D::f32,7);});
 float stored=0;ng::Args storage;storage.p[5]=&stored;
 for(uint32_t raw:{0u,0x80000000u,1u,0x80000001u,0x3f800001u,0x7f800000u,0xff800000u,0x7fc12345u}){float value=std::bit_cast<float>(raw);storage.put_recurrent(5,0,value,16);check(bits(storage.recurrent(5,0,16))==raw,"F32 accessor preserves full bits");}
 ng::Shape s;s.op=ng::gdn;s.flags=16;auto n=ng::required_bytes(s);check(n[5]==3145728&&n[7]==n[5],"F32 native state extent");s.flags=0;check(ng::required_bytes(s)[5]==1572864,"legacy native extent");s.op=ng::norm;s.flags=16;rejects([&]{ng::validate(s);});
}
static void recurrence(){
 std::vector<uint16_t> qkv(10240),alpha(48),beta(48),y(6144);std::vector<float> av(48),dt(48),state(48*128*128,0),out(state.size(),-99);float scratch[512]{};int error=0,pos=0,active=1;
 ng::Args a;a.p[0]=qkv.data();a.p[1]=alpha.data();a.p[2]=beta.data();a.p[3]=av.data();a.p[4]=dt.data();a.p[5]=state.data();a.p[6]=y.data();a.p[7]=out.data();a.p[15]=&error;a.p[17]=&pos;a.p[18]=&active;
 ng::Shape s;s.op=ng::gdn;s.flags=2|8|16;s.capacity=4096;ng::HostTeam team{scratch};
 for(int k=0;k<128;++k)state[k]=1.f+float(k+1)/65536.f;
 ng::group(s,a,0,team);
 for(int k=0;k<128;++k){check(bits(out[k])==bits(state[k]),"non-BF16 F32 state survives zero update");check(bits(out[k])!=bits(ng::Args::bf(out[k])),"fixture distinguishes BF16 loss");}
 check(out[128]==-99,"untouched next state row");
 // Full-width FP32 state is fed back through the actual modified kernel.
 a.p[5]=out.data();qkv[2048]=ng::Args::bits(1.f);qkv[4096]=ng::Args::bits(0.1f);
 float expected=out[0];const float kn=detmath::sqrt(1.f+1e-6f),k=1.f/kn,v=ng::Args::bf(0.1f);
 for(int step=0;step<32;++step){float pred=expected*k;float delta=(v-pred)*0.5f;expected=expected+delta*k;ng::group(s,a,0,team);check(bits(out[0])==bits(expected),"ordered F32 repeated update");}
 auto before=out;active=0;ng::group(s,a,0,team);check(out==before,"inactive preserves state");active=1;error=1;ng::group(s,a,0,team);check(out==before,"sticky error preserves state");error=0;pos=4096;ng::group(s,a,0,team);check(error==1&&out==before,"invalid position no state write");
 // Byte-preserving storage demonstration only; production controller proof is separate.
 auto snapshot=out;std::fill(out.begin(),out.end(),0);std::memcpy(out.data(),snapshot.data(),out.size()*sizeof(float));check(std::memcmp(out.data(),snapshot.data(),out.size()*4)==0,"full-width storage roundtrip");
}
static void convolution(int dilation){
 int hist=3*dilation;std::vector<float> history(hist),next(hist,-99),weight(4,0.25f);for(int j=0;j<hist;++j)history[j]=1.f+float(j+1)/65536.f;
 uint16_t input=ng::Args::bits(0.25f),output=0;float scratch[1024]{};int error=0,pos=0,active=1;
 ng::Args a;a.p[0]=&input;a.p[1]=history.data();a.p[2]=weight.data();a.p[3]=&output;a.p[4]=next.data();a.p[15]=&error;a.p[17]=&pos;a.p[18]=&active;
 ng::Shape s;s.op=ng::conv;s.width=1;s.extra=dilation;s.flags=8|16;auto ext=ng::required_bytes(s);check(ext[1]==size_t(hist)*4&&ext[4]==ext[1],"conv F32 byte extent");
 ng::group(s,a,0,ng::HostTeam{scratch});for(int j=0;j<hist-1;++j)check(bits(next[j])==bits(history[j+1]),"F32 shifted conv history");check(bits(next.back())==bits(0.25f),"new BF16 activation widened exactly");
 float acc=0;for(int tap=0;tap<4;++tap)acc=acc+(tap==3?0.25f:history[tap*dilation])*0.25f;
 float expected=ng::silu(dilation==3?ng::Args::bf(acc):acc);check(output==ng::Args::bits(expected),"unchanged conv output rounding");
}
int main(){try{plan_check();admissions();recurrence();convolution(1);convolution(3);std::cout<<"{\"passed\":true,\"checks\":"<<checks<<",\"scope\":\"actual modified HostTeam recurrence/history plus graph and guard proof; no Device/model/controller qualification\"}\n";}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
