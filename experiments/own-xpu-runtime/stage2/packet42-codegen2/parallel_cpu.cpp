#define integrated p42_reference_integrated
#define ng p42_reference_ng
#define detmath p42_reference_detmath
#define rope_constants p42_reference_rope_constants
#include "../packet29-merged/prototype/snapshot/reference.hpp"
#undef integrated
#undef ng
#undef detmath
#undef rope_constants
#include "parallel.hpp"
#include <fstream>
#include <iostream>
#include <map>
#include <cstring>
struct Stat{uint64_t checks=0,failures=0,hash=1469598103934665603ULL;};std::map<std::string,Stat> stats;
void check(const std::string& n,const void* a,const void* b,size_t bytes){auto&s=stats[n];auto x=static_cast<const uint8_t*>(a),y=static_cast<const uint8_t*>(b);for(size_t i=0;i<bytes;++i){++s.checks;s.failures+=x[i]!=y[i];s.hash=(s.hash^x[i])*1099511628211ULL;}}
struct Fixture{
 ng::Shape s;std::array<std::vector<uint8_t>,19>d,expected;
 explicit Fixture(const char* file){std::ifstream in(file,std::ios::binary);in.read(reinterpret_cast<char*>(&s),sizeof s);for(unsigned j=0;j<16;++j){uint32_t n,o;in.read(reinterpret_cast<char*>(&n),4);in.read(reinterpret_cast<char*>(&o),4);if(!in||n>128*1024*1024)throw std::runtime_error("fixture header");d[j].resize(n);in.read(reinterpret_cast<char*>(d[j].data()),n);if(o){expected[j].resize(n);in.read(reinterpret_cast<char*>(expected[j].data()),n);}}if(!in||in.peek()!=EOF)throw std::runtime_error("fixture bytes");int32_t c[3];std::memcpy(c,d[15].data(),12);for(unsigned j:{15,17,18})d[j].resize(4);std::memcpy(d[15].data(),c+2,4);std::memcpy(d[17].data(),c,4);std::memcpy(d[18].data(),c+1,4);}
 void reference(){p42_reference_ng::Shape shape;std::memcpy(&shape,&s,sizeof s);p42_reference_ng::Args a;for(unsigned j=0;j<15;++j)a.p[j]=d[j].data();int32_t c[3];std::memcpy(c,d[17].data(),4);std::memcpy(c+1,d[18].data(),4);std::memcpy(c+2,d[15].data(),4);a.p[15]=c;p42_reference_ng::reference::cpu(shape,a);std::memcpy(d[15].data(),c+2,4);}
 ng::Args args(){ng::Args a;for(unsigned j=0;j<19;++j)a.p[j]=d[j].data();return a;}
};

template<iq3::Type T>void dense(){constexpr unsigned K=6144,G=T==iq3::Type::Q6_K?16:32;std::array<uint8_t,K+4*K/G>w;std::array<uint16_t,K>x;
 for(unsigned trial=0;trial<20;++trial){for(unsigned j=0;j<K;++j){w[j]=uint8_t(j*29+trial*11);x[j]=iq3::bf16_bits(float(int((j*17)%127)-63)/128.f);}for(unsigned j=0;j<K/G;++j){float scale=float(int((j+trial)%31)-15)/16.f;uint32_t bits=std::bit_cast<uint32_t>(scale);std::memcpy(w.data()+K+4*j,&bits,4);}float parts[4][32],ref[4][32];for(unsigned lane=0;lane<32;++lane){auto v=p42parallel::dense_parts<T>(w.data(),x.data(),lane);for(unsigned p=0;p<4;++p){auto b=iq3::kopt2::bounds(K,p,4);parts[p][lane]=v[p];ref[p][lane]=p28::dense_lane<T,K>(w.data(),x.data(),b.first,b.second,lane);check("dense.lanes",&parts[p][lane],&ref[p][lane],4);}}
 float t[4],r[4];for(int p=0;p<4;++p){t[p]=iq3::tree32(parts[p]);r[p]=iq3::tree32(ref[p]);}float a=(t[0]+t[1])+(t[2]+t[3]),b=(r[0]+r[1])+(r[2]+r[3]);check("dense.fp32",&a,&b,4);uint16_t aa=iq3::bf16_bits(a),bb=iq3::bf16_bits(p28::dense_row<T,K>(w.data(),x.data(),4));check("dense.bf16",&aa,&bb,2);
 }
}
void run(const std::string& root,const std::string& name,int mutate=0){Fixture a((root+"/"+name).c_str());if(mutate==1)*reinterpret_cast<int32_t*>(a.d[17].data())=-1;if(mutate==2)*reinterpret_cast<int32_t*>(a.d[18].data())=0;if(mutate==3)*reinterpret_cast<int32_t*>(a.d[15].data())=1;Fixture b=a,c=a;c.reference();
 if(a.s.op==ng::route_gather){std::vector<float> scratch(specialised::scratch_floats(a.s));p42parallel::route_host(a.s,a.args(),scratch.data(),specialised::HostGuard{});specialised::cpu(b.s,b.args());}
 else{p42parallel::gdn_host(a.s,a.args());round2::gdn_host(b.s,b.args());}
 for(unsigned j=0;j<16;++j)if(!a.expected[j].empty()||j==15){check(name+".incumbent",a.d[j].data(),b.d[j].data(),a.d[j].size());check(name+".reference",a.d[j].data(),c.d[j].data(),a.d[j].size());}
}
int main(int argc,char**argv){try{if(argc!=2)throw std::invalid_argument("fixtures required");dense<iq3::Type::Q6_K>();dense<iq3::Type::Q8_0>();
 for(auto n:{"route-gather-1.fixture","route-gather-3.fixture","route-nan.fixture","route-ties.fixture","route-varied.fixture","gdn-1.fixture","gdn-packed-1.fixture","gdn-runtime-f32-1.fixture"})run(argv[1],n);
 for(int m=1;m<4;++m){run(argv[1],"route-gather-1.fixture",m);run(argv[1],"gdn-runtime-f32-1.fixture",m);}
 // Odd rank sizes exercise integer partition identity.
 for(unsigned n:{1u,3u,17u,255u,512u}){std::vector<float> v(n);for(unsigned j=0;j<n;++j)v[j]=float(j%7);for(unsigned j=0;j<n;++j){unsigned a=0,b=0;for(unsigned k=0;k<n;++k)b+=v[k]>v[j]||(v[k]==v[j]&&k<j);for(unsigned lane=0;lane<32;++lane)for(unsigned k=lane;k<n;k+=32)a+=v[k]>v[j]||(v[k]==v[j]&&k<j);check("route.odd-ranks",&a,&b,4);}}
 for(float den:{1.f,3.f,0.125f,512.f})for(unsigned trial=0;trial<4;++trial){std::array<float,512> ex{};for(unsigned j=0;j<512;++j)ex[j]=trial==0?1.f:trial==1?(j%2?0.f:-0.f):float((j*17)%71)/32.f;
 if(trial==3){ex[19]=INFINITY;ex[27]=iq3::bits_float(0x7fc10000);}for(unsigned j=0;j<512;++j){unsigned actual=0,expected=0;float v=ex[j]/den;for(unsigned k=0;k<512;++k){float x=ex[k]/den;expected+=x>v||(x==v&&k<j);}for(unsigned lane=0;lane<32;++lane)actual+=p42parallel::rank_lane<512>(ex.data(),den,j,lane);check(trial==3?"route.helper-invalid-diagnostic":"route.helper512",&actual,&expected,4);}}
 bool pass=true;std::cout<<"{\"device_executed\":false,\"rows\":{";unsigned count=0;for(auto&[n,s]:stats){pass&=!s.failures;if(count++)std::cout<<',';std::cout<<'"'<<n<<"\":{\"checks\":"<<s.checks<<",\"failures\":"<<s.failures<<",\"hash\":\""<<std::hex<<s.hash<<std::dec<<"\"}";}std::cout<<"},\"passed\":"<<(pass?"true":"false")<<"}\n";return pass?0:1;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 2;}}
