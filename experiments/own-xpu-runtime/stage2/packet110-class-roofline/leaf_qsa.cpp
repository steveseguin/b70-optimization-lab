#include "build/qsa_trace.hpp"
#include "failure.hpp"
#include <fstream>
#include <iostream>
int main(int argc,char**argv){try{
 if(argc!=2)throw std::invalid_argument("output required");std::ofstream out(argv[1]);unsigned checks=0;
 for(int context:{1,31,32,33,127,128,129,130,4096})for(int pattern:{0,1,2,3,4,5}){
  p47ref::Fixture a(context,1,0x107+context,pattern);
  if(pattern==3)static_cast<uint16_t*>(a.args().p[0])[0]=0x7fc1;
  if(pattern==4){static_cast<uint16_t*>(a.args().p[2])[0]=0x7f80;static_cast<uint16_t*>(a.args().p[3])[0]=0xffd5;}
  if(pattern==5){static_cast<uint16_t*>(a.args().p[1])[0]=0x7f80;static_cast<uint16_t*>(a.args().p[1])[1]=0xff80;}
  auto b=a,c=a;std::array<float,6144> before{},after{};
  auto s=a.shape;s.capacity=4096; // fixture allocated just occupied bytes; all IDs in range
  p47ref::cpu_split(s,a.args(),before.data());p107::qsa_host(b.args());p107::qsa_trace(c.args(),after.data());
  if(std::memcmp(before.data(),after.data(),sizeof(before)))throw std::runtime_error("QSA FP32 pre-gate bytes context="+std::to_string(context)+" pattern="+std::to_string(pattern));
  if(c.data!=b.data)throw std::runtime_error("instrumented candidate differs from actual mirror");
  for(int j=0;j<19;++j)if(a.data[j]!=b.data[j])throw std::runtime_error("QSA bytes context="+std::to_string(context)+" pattern="+std::to_string(pattern)+" slot="+std::to_string(j));
  auto&v=a.data[5];out<<context<<' '<<pattern<<' '<<packet26::hash(v.data(),v.size()*4)<<' '<<packet26::hash(before.data(),sizeof(before))<<'\n';++checks;
 }
 for(int control:{0,1,2,3}){p47ref::Fixture a(128,1,107),b=a;auto aa=a.args(),bb=b.args();aa.i(18)[0]=bb.i(18)[0]=control==0?0:1;aa.i(15)[0]=bb.i(15)[0]=control==1?7:0;aa.i(17)[0]=bb.i(17)[0]=control==2?-1:control==3?4096:127;
  if(p107::host_admit(aa))p47ref::cpu_split(p107::qsa_shape(),aa);p107::qsa_host(bb);for(int j=0;j<19;++j)if(a.data[j]!=b.data[j])throw std::runtime_error("QSA control bytes");++checks;}
 std::cout<<checks<<" QSA raw-byte checks PASS\n";return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
