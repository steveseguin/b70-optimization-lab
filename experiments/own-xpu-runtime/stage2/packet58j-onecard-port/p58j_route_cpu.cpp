#include "p78_route.hpp"
#include "failure.hpp"
#include <filesystem>
#include <fstream>
#include <iostream>
void require(bool v,const std::string&s){if(!v)throw std::runtime_error(s);}
uint32_t next(uint32_t&s){s=s*1664525u+1013904223u;return s;}
struct Recorder {std::ofstream a,b;unsigned count=0;Recorder(const std::filesystem::path&p):a(p/"expected.bin"),b(p/"candidate.bin"){}
 void compare(const std::vector<uint8_t>&x,const std::vector<uint8_t>&y,const std::string&s){require(x==y,s);a<<packet26::hash(x.data(),x.size())<<'\n';b<<packet26::hash(y.data(),y.size())<<'\n';}};
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
}
int main(int argc,char**argv){try{require(argc==2,"output");Recorder r(argv[1]);p78test::route(r,true);require(r.count==2048,"cases");std::cout<<"2048 route byte checks PASS\n";return 0;}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
