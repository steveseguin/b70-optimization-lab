// CPU execution only. Compare complete output and scratch bytes, no tolerance.
#include "p78_route.hpp"
#include "p78_norm.hpp"
#define main p73_unused_fixture_main
#include "p73_cpu.cpp"
#undef main
#include <limits>

namespace p78test {
template<class T>std::vector<uint8_t> bytes(const std::vector<T>&v){auto*p=reinterpret_cast<const uint8_t*>(v.data());return {p,p+v.size()*sizeof(T)};}
struct RouteOutput {
 std::vector<int32_t> ids=std::vector<int32_t>(10,-7),up=std::vector<int32_t>(30,-5),down=std::vector<int32_t>(30,-4);
 std::vector<float> weights=std::vector<float>(10,-6),scratch=std::vector<float>(1088,-7.25f);
 uint32_t error=0,active=1;
 std::vector<uint8_t> snapshot(){auto b=bytes(ids);for(auto v:{bytes(up),bytes(down),bytes(weights),bytes(scratch)})b.insert(b.end(),v.begin(),v.end());auto*p=reinterpret_cast<uint8_t*>(&error);b.insert(b.end(),p,p+4);return b;}
 route42::Args args(void*x,flash::Scalar type,unsigned outputs){route42::Args a{};a.input=x;a.input_type=type;a.n=512;a.top=10;a.mid=640;a.h=2560;a.no=outputs;a.output[0]=ids.data();a.output[1]=weights.data();a.output[2]=up.data();a.output[3]=down.data();a.output_type[0]=a.output_type[2]=a.output_type[3]=flash::Scalar::i32;a.output_type[1]=flash::Scalar::f32;a.scratch=scratch.data();a.error=&error;a.active=&active;return a;}
};
void route(Recorder&r,bool fast){
 uint32_t seed=0x780049;
 for(unsigned scenario=0;scenario<512;++scenario)for(bool bf16:{false,true})for(unsigned no:{2u,4u}){
  std::vector<float>x(512);std::vector<uint16_t>xb(512);
  for(unsigned j=0;j<512;++j){
   float v=float(int(next(seed)%65537)-32768)/257.f;
   switch(scenario%16){
    case 0:v=0.f;break;
    case 1:v=float(j%7);break;
    case 2:v=j<502?-100.f:100.f;break;
    case 3:v=j==511?80.f:-80.f;break;
    case 4:v=std::bit_cast<float>(0x3f800000u+(j%23));break;
    case 5:v=j%2?-0.f:0.f;break;
    case 6:v=std::bit_cast<float>(1u+j);break;
    case 7:v=float(511-j);break;
    case 8:v=float(j);break;
    case 9:v=float(int(next(seed)%5)-2);break;
    default:break;
   }
   x[j]=v;xb[j]=iq3::bf16_bits(v);
  }
  RouteOutput a,b;
  if(scenario==510)a.active=b.active=0;
  if(scenario==511)a.error=b.error=7;
  auto aa=a.args(bf16?static_cast<void*>(xb.data()):x.data(),bf16?flash::Scalar::bf16:flash::Scalar::f32,no);
  auto ab=b.args(bf16?static_cast<void*>(xb.data()):x.data(),bf16?flash::Scalar::bf16:flash::Scalar::f32,no);
  p49droute::host<4,32>(aa);if(fast)p78route::host(ab);else p49droute::host<4,32>(ab);
  r.compare(a.snapshot(),b.snapshot(),"route scenario="+std::to_string(scenario));++r.count;
 }
}
void norm(Recorder&r,bool subgroup){
 uint32_t seed=0x780060;
 for(unsigned scenario=0;scenario<40;++scenario){
  std::vector<uint16_t>x(10240),expected(10240,0x7e31),actual(expected);std::vector<float>gain(10240),sa(320,-7.25f),sb(sa);
  for(unsigned i=0;i<10240;++i){x[i]=iq3::bf16_bits(float(int(next(seed)%1025)-512)/32.f);gain[i]=float(int(next(seed)%127)-63)/64.f;}
  if(scenario==1)std::fill(x.begin(),x.end(),0);
  if(scenario==2){x[0]=1;x[1]=0x8001;x[32]=0x8000;}
  if(scenario==3)x[0]=0x7fc1;
  if(scenario==4){x[0]=0x7f80;x[32]=0xff80;}
  uint32_t ac=scenario==5?0:1,ea=scenario==6?7:0,eb=ea,pos=scenario==7?4096:0;
  p60::Bound b{};b.x=x.data();b.gain=gain.data();b.active=&ac;b.position=&pos;b.error=&ea;b.norm=expected.data();b.scratch=sa.data();p60::host_norm(b);
  b.error=&eb;b.norm=actual.data();b.scratch=sb.data();if(subgroup)p78norm::host(b);else p60::host_norm(b);
  r.compare(bytes(expected),bytes(actual),"HC norm values "+std::to_string(scenario));r.compare(bytes(sa),bytes(sb),"HC norm FP32 partials");require(ea==eb,"HC norm error");++r.count;
 }
}
}
int main(int argc,char**argv){try{
 require(argc==5,"ROUTE NORM HC OUTPUT");
 std::filesystem::path out=argv[4];std::filesystem::create_directories(out);Recorder r(out);
 p78test::route(r,std::string(argv[1])=="fast");
 p78test::norm(r,std::string(argv[2])=="fused");
 for(unsigned scenario=0;scenario<8;++scenario)run_hc(r,scenario,std::string(argv[3])=="hc-wide");
 require(r.count==2096,"case count");
 std::cout<<"{\"passed\":true,\"device_executed\":false,\"cases\":"<<r.count<<"}\n";
 return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
