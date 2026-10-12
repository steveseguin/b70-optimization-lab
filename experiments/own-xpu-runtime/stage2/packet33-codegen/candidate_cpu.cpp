// CPU-only. Exact bytes, no NaN equivalence, fixtures borrowed read-only.
#define integrated p33_reference_integrated
#define ng p33_reference_ng
#define detmath p33_reference_detmath
#define rope_constants p33_reference_rope_constants
#include "../packet29-merged/prototype/snapshot/reference.hpp"
#undef integrated
#undef ng
#undef detmath
#undef rope_constants
#include "candidates.hpp"
#include "p33_submit.hpp"
#include "build/route_gate_core.hpp"
#include <fstream>
#include <iostream>
#include <map>
#include <cstring>
struct Stat{uint64_t checks=0,failures=0,nonfinite_checks=0,nonfinite_failures=0,hash=1469598103934665603ULL;};
std::map<std::string,Stat> stats;
void check(const char* name,float a,float b,bool finite=true){auto& s=stats[name];auto aa=std::bit_cast<uint32_t>(a),bb=std::bit_cast<uint32_t>(b);if(finite){++s.checks;s.failures+=aa!=bb;s.hash^=aa;s.hash*=1099511628211ULL;}else{++s.nonfinite_checks;s.nonfinite_failures+=aa!=bb;}}
constexpr std::array<uint16_t,20> scales{0,0x8000,1,0x8001,0x03ff,0x83ff,0x0400,0x8400,0x3555,0xb555,0x3c00,0xbc00,0x7bff,0xfbff,0x7c00,0xfc00,0x7e01,0xfe01,0x7c01,0xfc01};
constexpr std::array<uint16_t,16> inputs{0,0x8000,1,0x8001,0x7f,0x807f,0x80,0x8080,0x3f80,0xbf80,0x7f80,0xff80,0x7fc1,0xffc1,0x7f81,0xff81};
template<unsigned K>void down(){
 for(unsigned sc=0;sc<scales.size();++sc)for(unsigned pattern=0;pattern<3;++pattern)for(unsigned im=0;im<18;++im){
  std::array<uint8_t,((K+31)/32)*18>w{};std::array<uint16_t,K>x{};bool finite=true;
  for(unsigned b=0;b<(K+31)/32;++b){auto s=scales[pattern==2?(sc+b)%scales.size():sc];finite=finite&&((s&0x7c00)!=0x7c00);w[b*18]=uint8_t(s);w[b*18+1]=uint8_t(s>>8);for(unsigned c=0;c<16;++c)w[b*18+2+c]=uint8_t(((c+b)%16)|(((pattern==1?c:15-c)+b)%16<<4));}
  for(unsigned i=0;i<K;++i){x[i]=im<inputs.size()?inputs[im]:im==16?inputs[i%inputs.size()]:iq3::bf16_bits(float(int((i*17)%127)-63)/128.f);finite=finite&&((x[i]&0x7f80)!=0x7f80);}
  float a[32]{},b[32]{},ref[32]{};
  for(unsigned lane=0;lane<32;++lane){a[lane]=p33::down_lane<0,K>(w.data(),x.data(),lane);b[lane]=p33::down_lane<1,K>(w.data(),x.data(),lane);
   for(unsigned k=lane*8;k<K;k+=256)for(unsigned j=0;j<8&&k+j<K;++j){float v=iq3::element(iq3::Type::IQ4_NL,w.data(),k+j);float in=iq3::bits_float(uint32_t(x[k+j])<<16);float product=v*in;ref[lane]=ref[lane]+product;}
   check("down.bank",a[lane],ref[lane],finite);check("down.select",b[lane],ref[lane],finite);
  }
  auto r=iq3::tree32(ref),aa=iq3::tree32(a),bb=iq3::tree32(b);check("down.bank",aa,r,finite);check("down.select",bb,r,finite);
  check("down.bank",iq3::bits_float(uint32_t(iq3::bf16_bits(aa))<<16),iq3::bits_float(uint32_t(iq3::bf16_bits(r))<<16),finite);
  check("down.select",iq3::bits_float(uint32_t(iq3::bf16_bits(bb))<<16),iq3::bits_float(uint32_t(iq3::bf16_bits(r))<<16),finite);
 }
}
template<iq3::Type T,unsigned K>void expert(){
 std::array<uint8_t,K/iq3::layout(T).elements*iq3::layout(T).bytes>w{},v{};std::array<uint16_t,K>x{};
 for(unsigned trial=0;trial<24;++trial){for(unsigned j=0;j<w.size();++j){w[j]=uint8_t(j*29+trial*11);v[j]=uint8_t(j*17+trial*19);}bool finite=trial<14;
  for(unsigned j=0;j<w.size();j+=iq3::layout(T).bytes){w[j]=v[j]=scales[trial%20];w[j+1]=v[j+1]=scales[trial%20]>>8;}
  for(unsigned j=0;j<K;++j)x[j]=iq3::bf16_bits(float(int((j*17)%127)-63)/128.f);
  for(unsigned end:{256u,K})for(unsigned lane=0;lane<32;++lane){auto a=p33::expert_lane<T,K,true>(w.data(),v.data(),x.data(),0,end,lane);auto b=p28::expert_lane<T,K,false,true>(w.data(),v.data(),x.data(),0,end,lane,p28::ExpertByteTables{},iq3::kopt3::HostShare{});
   check("expert.restrict",a[0],b[0],finite);check("expert.restrict",a[1],b[1],finite);
   float r=iq3::kopt3::dot<T>(w.data(),x.data(),iq3::Type::BF16,0,end,lane,iq3::kopt3::ConstantTables{},iq3::kopt3::HostShare{});check("expert.reference",a[0],r,finite);
  }
 }
}
template<iq3::Type T,unsigned K>void dense(){
 constexpr unsigned group=T==iq3::Type::Q6_K?16:32;std::array<uint8_t,K+4*K/group>w{};std::array<uint16_t,K>x{};
 for(unsigned trial=0;trial<20;++trial){for(unsigned j=0;j<K;++j){w[j]=uint8_t(j*29+trial*11);x[j]=iq3::bf16_bits(float(int((j*17)%127)-63)/128.f);}float scale=iq3::half(scales[trial]);uint32_t bits=std::bit_cast<uint32_t>(scale);for(unsigned j=0;j<K/group;++j)std::memcpy(w.data()+K+4*j,&bits,4);
  for(unsigned end:{1u,3u,17u,255u,K})for(unsigned lane=0;lane<32;++lane){float a=p33::dense_lane<T,K>(w.data(),x.data(),0,end,lane);float b=p28::dense_lane<T,K>(w.data(),x.data(),0,end,lane);check("dense.aligned",a,b,trial<14);}
 }
}
template<iq3::Type T,unsigned K>void dense_production(){
 constexpr unsigned group=T==iq3::Type::Q6_K?16:32;std::array<uint8_t,K+4*K/group>w{};std::array<uint16_t,K>x{};
 for(unsigned trial=0;trial<20;++trial){for(unsigned j=0;j<K;++j){w[j]=uint8_t(j*29+trial*11);x[j]=iq3::bf16_bits(float(int((j*17)%127)-63)/128.f);}uint32_t bits=std::bit_cast<uint32_t>(iq3::half(scales[trial]));for(unsigned j=0;j<K/group;++j){uint32_t group_bits=trial<14?std::bit_cast<uint32_t>(iq3::half(scales[(trial+j)%14])):bits;std::memcpy(w.data()+K+4*j,&group_bits,4);}
  for(unsigned split:{1u,4u}){float parts[4]{};
   for(unsigned part=0;part<split;++part){auto bounds=iq3::kopt2::bounds(K,part,split);float lanes[32]{},oracle[32]{};
    for(unsigned lane=0;lane<32;++lane){lanes[lane]=p33::dense_lane<T,K>(w.data(),x.data(),unsigned(bounds.first),unsigned(bounds.second),lane);oracle[lane]=p28::dense_lane<T,K>(w.data(),x.data(),unsigned(bounds.first),unsigned(bounds.second),lane);check("dense.production-lane",lanes[lane],oracle[lane],trial<14);}
    parts[part]=iq3::tree32(lanes);check("dense.production-tree",parts[part],iq3::tree32(oracle),trial<14);
   }
   float value=split==1?parts[0]:(parts[0]+parts[1])+(parts[2]+parts[3]);float ref=p28::dense_row<T,K>(w.data(),x.data(),split);check("dense.production-row",value,ref,trial<14);check("dense.production-bf16",float(iq3::bf16_bits(value)),float(iq3::bf16_bits(ref)),trial<14);
  }
 }
}
template<iq3::Type T,unsigned K>void expert_production(){
 std::array<uint8_t,K/iq3::layout(T).elements*iq3::layout(T).bytes>w{},v{};std::array<uint16_t,K>x{};
 for(unsigned trial=0;trial<20;++trial){for(unsigned j=0;j<w.size();++j){w[j]=uint8_t(j*29+trial*11);v[j]=uint8_t(j*17+trial*19);}for(unsigned j=0;j<w.size();j+=iq3::layout(T).bytes){w[j]=v[j]=scales[trial];w[j+1]=v[j+1]=scales[trial]>>8;}for(unsigned j=0;j<K;++j)x[j]=iq3::bf16_bits(float(int((j*17)%127)-63)/128.f);
  float values[2][32]{},oracle[2][32]{};for(unsigned lane=0;lane<32;++lane){auto pair=p33::expert_lane<T,K,true>(w.data(),v.data(),x.data(),0,K,lane);auto one=p33::expert_lane<T,K,false>(w.data(),v.data(),x.data(),0,K,lane);check("expert.production-unpaired",pair[0],one[0],trial<14);for(unsigned j=0;j<2;++j){values[j][lane]=pair[j];oracle[j][lane]=iq3::kopt3::dot<T>(j?v.data():w.data(),x.data(),iq3::Type::BF16,0,K,lane,iq3::kopt3::ConstantTables{},iq3::kopt3::HostShare{});check("expert.production-lane",values[j][lane],oracle[j][lane],trial<14);}}
  for(unsigned j=0;j<2;++j){float a=iq3::tree32(values[j]),b=iq3::tree32(oracle[j]);check("expert.production-tree",a,b,trial<14);check("expert.production-bf16",float(iq3::bf16_bits(a)),float(iq3::bf16_bits(b)),trial<14);}
 }
}
template<unsigned N,unsigned Top>void route(){
 std::array<float,N>x{};for(unsigned trial=0;trial<9;++trial){for(unsigned k=0;k<N;++k)x[k]=trial==0?1.f:trial==8?iq3::bits_float(0x7fc10000):float((k*17+trial*23)%71);
  for(unsigned j=0;j<N;++j){unsigned a=p33::route_rank<N,Top>(x.data(),j),b=0;for(unsigned k=0;k<N&&b<Top;++k)b+=x[k]>x[j]||(x[k]==x[j]&&k<j);check("route.rank4",float(std::min(a,Top)),float(b));}
 }
}
void route_stages(){
 for(unsigned trial=0;trial<12;++trial){std::array<float,512>input{},scratch0{},scratch1{};std::array<float,10>prob0{},prob1{};std::array<int32_t,10>ids0{},ids1{};std::array<int32_t,30>gate0{},gate1{},down0{},down1{};uint32_t error0=0,error1=0,active=trial==10?0:1;std::array<float,514>local0{},local1{};
  for(unsigned k=0;k<512;++k)input[k]=trial==0?1.f:float(int((k*17+trial*23)%71)-35)/32.f;if(trial==11)input[31]=iq3::bits_float(0x7fc10000);
  p33_route_ref::SimpleArgs a{input.data(),ids0.data(),prob0.data(),gate0.data(),down0.data(),scratch0.data(),&error0,&active,512,10,640,2560};
  p33_route_new::SimpleArgs b{input.data(),ids1.data(),prob1.data(),gate1.data(),down1.data(),scratch1.data(),&error1,&active,512,10,640,2560};
  auto stage=[&]<int Stage>(){for(int group=0;group<(Stage==1?16:1);++group){p33_route_ref::simple_group<integrated::Op::route,Stage,flash::Scalar::f32,512,10>(a,group,ng::HostTeam{local0.data()});p33_route_new::simple_group<integrated::Op::route,Stage,flash::Scalar::f32,512,10>(b,group,ng::HostTeam{local1.data()});}};
  stage.template operator()<0>();stage.template operator()<1>();stage.template operator()<2>();
  for(unsigned j=0;j<10;++j){check("route.outputs",prob1[j],prob0[j]);check("route.outputs",float(ids1[j]),float(ids0[j]));}for(unsigned j=0;j<30;++j){check("route.outputs",float(gate1[j]),float(gate0[j]));check("route.outputs",float(down1[j]),float(down0[j]));}check("route.outputs",float(error1),float(error0));
 }
}
struct Fixture{
 ng::Shape s;std::array<std::vector<uint8_t>,19>d,expected;
 explicit Fixture(const char* file){std::ifstream in(file,std::ios::binary);in.read(reinterpret_cast<char*>(&s),sizeof s);for(unsigned j=0;j<16;++j){uint32_t n,o;in.read(reinterpret_cast<char*>(&n),4);in.read(reinterpret_cast<char*>(&o),4);if(!in||n>128*1024*1024)throw std::runtime_error("fixture header");d[j].resize(n);in.read(reinterpret_cast<char*>(d[j].data()),n);if(o){expected[j].resize(n);in.read(reinterpret_cast<char*>(expected[j].data()),n);}}if(!in||in.peek()!=EOF)throw std::runtime_error("fixture bytes");int32_t c[3];std::memcpy(c,d[15].data(),12);for(unsigned j:{15,17,18})d[j].resize(4);std::memcpy(d[15].data(),c+2,4);std::memcpy(d[17].data(),c,4);std::memcpy(d[18].data(),c+1,4);}
 void reference(){p33_reference_ng::Shape shape;std::memcpy(&shape,&s,sizeof s);p33_reference_ng::Args a;for(unsigned j=0;j<15;++j)a.p[j]=d[j].data();int32_t c[3];std::memcpy(c,d[17].data(),4);std::memcpy(c+1,d[18].data(),4);std::memcpy(c+2,d[15].data(),4);a.p[15]=c;p33_reference_ng::reference::cpu(shape,a);std::memcpy(d[15].data(),c+2,4);}
 ng::Args args(){ng::Args a;for(unsigned j=0;j<19;++j)a.p[j]=d[j].data();return a;}
};
template<int Tokens>void qsa(const std::string& root){auto file=root+"/qsa-attention-"+std::to_string(Tokens)+".fixture";Fixture a(file.c_str()),b=a,c=a;c.reference();std::vector<float> local(2052),other(2052);float global=0,global2=0;
 if(a.s.tokens!=Tokens||a.s.capacity!=128||a.s.budget!=2048)throw std::runtime_error("QSA specialization shape");
 auto stage=[&]<ng::Op Op>(){a.s.op=b.s.op=Op;for(int g=0;g<round2::groups(a.s);++g){p33::qsa_group<Op,0,128,2048,Tokens>(a.s,a.args(),g,&global,ng::HostTeam{local.data()});round2::group<Op,0>(b.s,b.args(),g,&global2,ng::HostTeam{other.data()});}};
 stage.template operator()<ng::attention_score>();stage.template operator()<ng::attention_softmax>();stage.template operator()<ng::attention_value>();
 for(unsigned slot:{5,6,7,15})for(unsigned j=0;j<a.d[slot].size();++j){check("qsa.specialized",float(a.d[slot][j]),float(b.d[slot][j]));check("qsa.fixture-reference",float(a.d[slot][j]),float(c.d[slot][j]));if(slot!=15){check("qsa.stored-expected-diagnostic",float(a.d[slot][j]),float(a.expected[slot][j]));if(a.d[slot][j]!=a.expected[slot][j])std::cerr<<"fixture mismatch token="<<Tokens<<" slot="<<slot<<" byte="<<j<<" got="<<unsigned(a.d[slot][j])<<" reference="<<unsigned(a.expected[slot][j])<<" unchanged="<<unsigned(b.d[slot][j])<<"\n";}}
}
int main(int argc,char**argv){try{if(argc!=2)throw std::runtime_error("fixture directory argument required");
 for(unsigned q=0;q<16;++q){check("level.exhaustive",float(p33::level_bank(q)),float(p28::iq4_bytes[q]));check("level.exhaustive",float(p33::level_select(q)),float(p28::iq4_bytes[q]));}
 down<640>();down<1>();down<3>();down<17>();down<255>();down<639>();
 expert<iq3::Type::IQ2_S,512>();expert<iq3::Type::IQ3_S,512>();expert<iq3::Type::IQ3_XXS,512>();dense<iq3::Type::Q6_K,512>();dense<iq3::Type::Q8_0,640>();expert_production<iq3::Type::IQ2_S,2560>();expert_production<iq3::Type::IQ3_S,2560>();dense_production<iq3::Type::Q6_K,2560>();dense_production<iq3::Type::Q8_0,2560>();route<512,10>();route<17,3>();route<3,1>();route_stages();qsa<1>(argv[1]);qsa<3>(argv[1]);
 bool pass=true;std::cout<<"{\"device_executed\":false,\"nan_tolerance\":false,\"nonfinite_qualified\":false,\"candidates\":{";unsigned n=0;for(auto&[name,s]:stats){if(n++)std::cout<<',';pass=pass&&(name=="qsa.stored-expected-diagnostic"||!s.failures);std::cout<<'"'<<name<<"\":{\"checks\":"<<s.checks<<",\"failures\":"<<s.failures<<",\"nonfinite_checks\":"<<s.nonfinite_checks<<",\"nonfinite_failures\":"<<s.nonfinite_failures<<",\"hash\":\""<<std::hex<<s.hash<<std::dec<<"\"}";}std::cout<<"},\"passed\":"<<(pass?"true":"false")<<"}\n";return pass?0:1;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 2;}}
