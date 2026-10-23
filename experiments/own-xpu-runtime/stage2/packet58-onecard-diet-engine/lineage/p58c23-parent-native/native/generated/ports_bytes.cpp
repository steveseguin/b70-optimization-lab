// Real operator dimensions; synthetic weights only. No model or device access.
#define P60_FIXTURE_DATA_ONLY
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58-onecard-diet-engine/build/native/fixture.cpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58-onecard-diet-engine/build/native/p58ag_expert.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58-onecard-diet-engine/frozen-inputs/repo/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/build/checked/experiments/own-xpu-runtime/stage2/packet58j-onecard-port/p100_down.hpp"
#include "/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet58-onecard-diet-engine/build/native/p109_fusion.hpp"
#include <random>
extern "C" void p109_production_ng(ng::Shape,ng::Args);
static void check(bool ok,const char* msg){if(!ok)throw std::runtime_error(msg);}
static void bytes(std::ofstream& out,const auto& v){out.write(reinterpret_cast<const char*>(v.data()),v.size()*sizeof(v[0]));}
int main(int argc,char**argv){try{
 check(argc==2,"output directory");std::filesystem::create_directories(argv[1]);
 std::ofstream expected(std::filesystem::path(argv[1])/"expected.bin",std::ios::binary),actual(std::filesystem::path(argv[1])/"actual.bin",std::ios::binary);
 std::vector<float> table(65536);for(unsigned i=0;i<65536;++i){table[i]=iq3::half(uint16_t(i));float ref=iq3::half(uint16_t(i));check(std::memcmp(&ref,&table[i],4)==0,"exhaustive half bits");}bytes(expected,table);bytes(actual,table);
 constexpr unsigned rows=640,count=10,experts=512,rb=820;
 std::mt19937 rng(5807);std::vector<uint8_t> gate(count*rows*rb),up(gate.size()),raw(rb);
 for(auto* bank:{&gate,&up})for(unsigned r=0;r<count*rows;++r){for(auto& v:raw)v=uint8_t(rng());for(unsigned k=0;k<10;++k){uint16_t h=uint16_t(0x2000+(rng()%0x1000));raw[k*82]=h;raw[k*82+1]=h>>8;}p49bgemv::repack_row(iq3::Type::IQ2_S,2560,raw.data(),bank->data()+r*rb);}
 std::vector<p58::Pointer> gp(experts),uptr(experts);for(unsigned e=0;e<experts;++e){gp[e]={uint64_t(gate.data()+(e%count)*rows*rb),0};uptr[e]={uint64_t(up.data()+(e%count)*rows*rb),0};}
 std::vector<iq3::Route> routes(count);for(unsigned i=0;i<count;++i)routes[i]={i==9?511u:i,0,rows};
 std::vector<uint8_t> down(count*2560*360),downraw(360);for(unsigned r=0;r<count*2560;++r){for(auto& v:downraw)v=uint8_t(rng());for(unsigned b=0;b<20;++b){uint16_t h=0x2400;downraw[b*18]=h;downraw[b*18+1]=h>>8;}p49bgemv::repack_row(iq3::Type::IQ4_NL,640,downraw.data(),down.data()+r*360);}
 auto tiled=p100::transpose(down.data(),count*2560);std::vector<p58::Pointer> dp(experts);for(unsigned e=0;e<experts;++e)dp[e]={uint64_t(tiled.data()+(e%count)*2560*360),0};
 std::vector<uint8_t> shared(2560*760);for(unsigned r=0;r<2560;++r){for(unsigned k=0;k<640;++k)shared[r*760+k]=uint8_t(int(rng()%17)-8);for(unsigned b=0;b<20;++b){float s=1.f/128;std::memcpy(shared.data()+r*760+640+b*4,&s,4);}}
 unsigned cases=0;
 // Profile 0 is HC fusion baseline; 1 wide HC; 2 wide64; 3 halfcache;
 // 4 small fusion; 5 complete composition. Every profile consumes HC output
 // in expert GEMV then exact activation, down and ordered mixture/blend.
 for(unsigned scenario=0;scenario<4;++scenario){
  std::vector<uint8_t> baseline;
  for(unsigned profile=0;profile<6;++profile){
   Data hc;hc.init(580+scenario);if(scenario==1)hc.x[17]=0x7fc5;if(scenario==2)hc.x[0]=0x8000;if(scenario==3)hc.position=4095;
   p60::host_norm(hc.bound());p60::host_low_inject(hc.bound());if(profile==1||profile==5)p73hc::host(hc.bound());else p60::host_gate_mix(hc.bound());
   for(auto& route:routes)route.row_count=rows;
   std::vector<uint16_t> y(rows*count),z(y.size()),act(y.size()),d(2560*count),mix(2560),out(2560),sh(2560);std::vector<uint32_t> status(count),peer_status(count);std::vector<float> workspace(8);
   uint32_t error=0,active=1,position=hc.position;
   std::vector<uint32_t> routeids(10),routedown(30);std::vector<float> prob(10),route_scratch(1088,-7.f);
   std::vector<uint16_t> sg(640),su(640),sa(640);for(unsigned i=0;i<640;++i){sg[i]=hc.act[i%320];su[i]=hc.mix[i];}
   integrated::Spec rs{};rs.g.h=2560;rs.g.mid=640;rs.g.top=10;rs.g.context=4096;rs.ni=1;rs.no=4;rs.nw=0;rs.site.shape[1]=10;rs.sizes[0]=512;rs.types[0]=flash::Scalar::bf16;rs.types[1]=rs.types[3]=rs.types[4]=flash::Scalar::u32;rs.types[2]=flash::Scalar::f32;
   std::array<void*,12> rp{hc.mix.data(),routeids.data(),prob.data(),routes.data(),routedown.data(),route_scratch.data(),&error,&position,&active,sg.data(),su.data(),sa.data()};
   if(profile==4||profile==5){p109route::Kernel op;op.spec=rs;op.run(rp);}
   else {p49droute::host<4,32>(route42::bind(rs,std::span<void*const>(rp.data(),9)));ng::Shape s{};s.op=ng::activation;s.width=640;s.extra=1;s.capacity=4096;ng::Args a{};a.p[0]=sg.data();a.p[1]=su.data();a.p[2]=sa.data();a.p[15]=&error;a.p[17]=&position;a.p[18]=&active;p109_production_ng(s,a);}
   std::array<void*,20> p{};p[0]=gp.data();p[1]=uptr.data();p[2]=hc.mix.data();p[3]=y.data();p[4]=z.data();p[5]=routes.data();p[6]=status.data();p[7]=peer_status.data();p[8]=workspace.data();p[16]=&error;p[17]=&active;p[18]=&position;p[19]=table.data();
   if(profile==2){p58ag_exp::Kernel<iq3::Type::IQ2_S,2560,64,false,true,0,false> op;op.indirect=true;op.run(p);}
   else if(profile==3||profile==5){p58ag_exp::Kernel<iq3::Type::IQ2_S,2560,64,false,true> op;op.indirect=true;op.run(p);}
   else {p49dvirtual::GateKernel op;op.indirect=true;op.run(std::span<void*const>(p.data(),19));}
   for(unsigned i=0;i<act.size();++i)act[i]=iq3::bf16_bits(ng::silu(iq3::bits_float(uint32_t(y[i])<<16))*iq3::bits_float(uint32_t(z[i])<<16));
   for(auto& route:routes)route.row_count=2560;
   p[0]=p[1]=dp.data();p[2]=act.data();p[3]=p[4]=d.data();p100::Kernel<2> downop;downop.indirect=true;downop.run(std::span<void*const>(p.data(),19));
   float one=1;uint16_t sharedgate=0x3f00;
   std::array<void*,12> tailp{shared.data(),sa.data(),sh.data(),d.data(),prob.data(),mix.data(),&sharedgate,&one,out.data(),&error,&position,&active};
   if(profile==4||profile==5){p109::SharedDown op;op.capacity=4096;op.run(tailp);}
   else {
    for(unsigned r=0;r<2560;++r){float lanes[32];for(unsigned lane=0;lane<32;++lane)lanes[lane]=p33::dense_lane<iq3::Type::Q8_0,640>(shared.data()+r*760,sa.data(),0,640,lane);sh[r]=iq3::bf16_bits(iq3::tree32(lanes));mix[r]=iq3::bf16_bits(iq3::kopt4::combine(d.data(),prob.data(),2560,r));}
    ng::Shape s{};s.op=ng::moe_combine;s.width=2560;s.extra=1;s.capacity=4096;ng::Args a{};a.p[0]=mix.data();a.p[1]=&one;a.p[2]=sh.data();a.p[3]=&sharedgate;a.p[4]=out.data();a.p[15]=&error;a.p[17]=&position;a.p[18]=&active;
    p109_production_ng(s,a);
   }
   std::vector<uint8_t> record;auto append=[&](const auto& v){auto* ptr=reinterpret_cast<const uint8_t*>(v.data());record.insert(record.end(),ptr,ptr+v.size()*sizeof(v[0]));};
   append(hc.norm);append(hc.low);append(hc.act);append(hc.gate);append(hc.mix);append(hc.inject);append(hc.scratch);append(hc.workspace);append(routeids);append(routes);append(routedown);append(prob);append(route_scratch);append(sa);append(y);append(z);append(act);append(status);append(peer_status);append(d);append(sh);append(mix);append(out);append(std::array<uint32_t,1>{error});
   if(profile==0)baseline=record;else {check(record==baseline,"composed exact bytes");bytes(expected,baseline);bytes(actual,record);++cases;}
  }
 }
 std::cout<<"{\"passed\":true,\"device_executed\":false,\"cases\":"<<cases<<",\"all_half_patterns\":65536,\"profiles\":6,\"real_shapes\":true,\"indirect_experts\":512,\"selected_experts\":10}\n";
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
