#ifndef OWN_RT_HOST_ONLY
#define OWN_RT_HOST_ONLY
#endif
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58am-demand-transfer/vendor/experiments/own-xpu-runtime/stage2/packet58ag-onecard-ports/build/native/p60_math.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58am-demand-transfer/vendor/experiments/own-xpu-runtime/stage2/packet58ag-onecard-ports/build/native/p73_hc.hpp"
#include <fstream>
#include <random>
#include <iostream>
#include <filesystem>
namespace {
using namespace p60;
struct Data {
 std::vector<uint16_t> x=std::vector<uint16_t>(K),norm=x,low=std::vector<uint16_t>(L),act=low,gate=x,mix=std::vector<uint16_t>(H),inject=std::vector<uint16_t>(S);
 std::vector<float> gain=std::vector<float>(K),scratch=std::vector<float>(320),workspace=std::vector<float>(32);
 std::vector<uint8_t> lw=std::vector<uint8_t>(L*iq3::expanded::row_bytes(Type::Q8_0,K)),gw=std::vector<uint8_t>(K*iq3::expanded::row_bytes(Type::Q8_0,L)),iw=std::vector<uint8_t>(S*K*4);
 uint32_t error=0,active=1,position=127;
 Bound bound(){return {x.data(),gain.data(),lw.data(),gw.data(),iw.data(),norm.data(),low.data(),act.data(),gate.data(),mix.data(),inject.data(),scratch.data(),workspace.data(),&error,&active,&position};}
 void init(unsigned seed){std::mt19937 rng(seed);auto f=[&](){return float(int(rng()%2049)-1024)/1024.f;};
  for(auto&v:x)v=iq3::bf16_bits(f());for(auto&v:gain)v=f();
  auto weights=[&](auto&w,unsigned rows,unsigned cols){size_t rb=iq3::expanded::row_bytes(Type::Q8_0,cols);
   for(unsigned r=0;r<rows;++r){auto p=w.data()+r*rb;for(unsigned k=0;k<cols;++k)p[k]=uint8_t(int(rng()%255)-127);for(unsigned k=0;k<cols/32;++k){float scale=f()/64.f;std::memcpy(p+cols+k*4,&scale,4);}}};
  weights(lw,L,K);weights(gw,K,L);for(unsigned i=0;i<S*K;++i){float v=f()/16.f;std::memcpy(iw.data()+i*4,&v,4);}
  for(auto*v:{&norm,&low,&act,&gate,&mix,&inject})std::fill(v->begin(),v->end(),uint16_t(0x3f01));
  std::fill(scratch.begin(),scratch.end(),-13.f);std::fill(workspace.begin(),workspace.end(),-17.f);
 }
 void write(std::ofstream&o){for(auto*v:{&norm,&low,&act,&gate,&mix,&inject})o.write(reinterpret_cast<const char*>(v->data()),v->size()*2);for(auto*v:{&scratch,&workspace})o.write(reinterpret_cast<const char*>(v->data()),v->size()*4);o.write(reinterpret_cast<const char*>(&error),4);}
};
template<Type T,unsigned N,unsigned Split,p39::Kind E> void production_dense(Bound b,const uint8_t*w,const uint16_t*x,uint16_t*y,unsigned rows){
 p49c::DenseKernel<T,N,Split,E> op;op.shape.rows=rows;op.shape.rb=integrated::arithmetic::row_bytes(T,N,Split==4?7:6);op.shape.capacity=b.capacity;
 std::array<void*,19> p{};p[0]=const_cast<uint8_t*>(w);p[2]=const_cast<uint16_t*>(x);p[3]=y;p[8]=b.workspace;p[10]=b.act;p[16]=b.error;p[17]=const_cast<uint32_t*>(b.active);p[18]=const_cast<uint32_t*>(b.position);op.run(p);
}
void reference(Bound b){
 ng::Shape s{};s.op=ng::norm;s.tokens=1;s.width=H;s.heads=S;s.capacity=b.capacity;s.flags=8;
 ng::Args a{};a.p[0]=const_cast<uint16_t*>(b.x);a.p[1]=const_cast<float*>(b.gain);a.p[2]=b.norm;a.p[14]=b.scratch;a.p[15]=b.error;a.p[17]=const_cast<uint32_t*>(b.position);a.p[18]=const_cast<uint32_t*>(b.active);
 for(size_t i=0;i<specialised::work_items(s,0);++i)specialised::body<ng::norm,0>(s,a,i,b.scratch,specialised::HostGuard{});
 for(size_t i=0;i<specialised::work_items(s,1);++i)specialised::body<ng::norm,1>(s,a,i,b.scratch,specialised::HostGuard{});
 production_dense<Type::Q8_0,K,4,p39::Kind::silu_div4>(b,b.low_w,b.norm,b.low,L);
 production_dense<Type::Q8_0,L,1,p39::Kind::expert_checks>(b,b.gate_w,b.act,b.gate,K);
 // Production ng::mix body and its exact stream-order reduction.
 s.op=ng::mix;ng::Args mix{};mix.p[0]=b.norm;mix.p[1]=b.gate;mix.p[2]=b.mix;mix.p[15]=b.error;mix.p[17]=const_cast<uint32_t*>(b.position);mix.p[18]=const_cast<uint32_t*>(b.active);
 std::vector<float> tmp(ng::local_floats(s));for(int g=0;g<ng::groups(s);++g)ng::group(s,mix,g,ng::HostTeam{tmp.data()});
 // Packet33 and packet28 inject share this scalar reference. Retain native
 // split scratch explicitly: the normal CPU lowering does not materialize it.
 for(unsigned r=0;r<S;++r){float parts[4];for(unsigned p=0;p<4;++p){auto bounds=iq3::kopt2::bounds(K,p,4);float lanes[32];for(unsigned l=0;l<32;++l)lanes[l]=p28::dense_lane<Type::F32,K>(b.inject_w+r*K*4,b.norm,bounds.first,bounds.second,l);parts[p]=iq3::tree32(lanes);b.workspace[r*8+p]=parts[p];}b.inject[r]=iq3::bf16_bits((parts[0]+parts[1])+(parts[2]+parts[3]));}
}
}
#ifndef P60_FIXTURE_DATA_ONLY
int main(int argc,char**argv){try{
 if(argc!=2)throw std::runtime_error("output directory required");std::filesystem::create_directories(argv[1]);
 std::ofstream expected(std::filesystem::path(argv[1])/"expected.bin",std::ios::binary),actual(std::filesystem::path(argv[1])/"actual.bin",std::ios::binary);
 unsigned cases=0;
 for(unsigned wide=0;wide<2;++wide)for(unsigned side=0;side<2;++side)for(unsigned scenario=0;scenario<9;++scenario){
  Data a;a.init(7+side*101);a.position=scenario==1?4095:127;
  if(scenario==2){a.x[0]=0x7fc1;a.x[2560]=0xffc1;}
  if(scenario==3){a.x[0]=0x7f80;a.x[2560]=0xff80;}
  if(scenario==4){for(unsigned i=0;i<a.x.size();++i)a.x[i]=i%2?0x8000:0;for(auto&g:a.gain)g=-0.f;}
  if(scenario==5)a.error=37;
  if(scenario==6)a.active=0;
  if(scenario==7)a.position=4096;
  if(scenario==8){a.gain[3]=iq3::bits_float(0x7fc12345);float inf=iq3::bits_float(0x7f800000);std::memcpy(a.iw.data(),&inf,4);}
  Data b=a;reference(a.bound());host_norm(b.bound());host_low_inject(b.bound());if(wide)p73hc::host(b.bound());else host_gate_mix(b.bound());
  a.write(expected);b.write(actual);++cases;
 }
 expected.close();actual.close();if(!expected||!actual)throw std::runtime_error("fixture write failed");
 std::ifstream e(std::filesystem::path(argv[1])/"expected.bin",std::ios::binary),a(std::filesystem::path(argv[1])/"actual.bin",std::ios::binary);size_t at=0;char x,y;while(e.get(x)){if(!a.get(y)||x!=y)throw std::runtime_error("first differing byte "+std::to_string(at));++at;}if(a.get(y))throw std::runtime_error("extra actual bytes");
 std::cout<<"{\"passed\":true,\"device_executed\":false,\"cases\":"<<cases<<",\"bytes_compared\":"<<at<<"}\n";
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
#endif
