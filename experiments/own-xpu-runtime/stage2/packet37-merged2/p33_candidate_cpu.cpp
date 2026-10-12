// CPU-only. Exact bytes, no NaN equivalence, fixtures borrowed read-only.
#define integrated p33_reference_integrated
#define ng p33_reference_ng
#define detmath p33_reference_detmath
#define rope_constants p33_reference_rope_constants
#include "prototype/snapshot/reference.hpp"
#undef integrated
#undef ng
#undef detmath
#undef rope_constants
#include "p33_candidates.hpp"
#include "p33_submit.hpp"

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
// Every runtime dense class is checked in every supported format at its K,
// both split1 and split4. Direct expanded core is the oracle, not this candidate.
template<iq3::Type T,unsigned K>void dense_class(const std::string& label){
 std::vector<uint8_t>w(iq3::expanded::row_bytes(T,K));std::array<uint16_t,K>x{};
 const std::string prefix="dense."+label+"."+std::to_string(unsigned(T));
 for(unsigned trial=0;trial<20;++trial){
  bool finite=trial<14;uint32_t bits=std::bit_cast<uint32_t>(iq3::half(scales[trial]));
  for(unsigned j=0;j<K;++j){
   x[j]=iq3::bf16_bits(float(int((j*17)%127)-63)/128.f);
   if constexpr(T==iq3::Type::Q6_K||T==iq3::Type::Q8_0)w[j]=uint8_t(j*29+trial*11);
   else if constexpr(T==iq3::Type::F32){float value=finite?float(int((j*19+trial)%127)-63)/32.f:iq3::bits_float(bits);std::memcpy(w.data()+4*j,&value,4);}
   else {uint16_t value=finite?iq3::bf16_bits(float(int((j*19+trial)%127)-63)/32.f):iq3::bf16_bits(iq3::bits_float(bits));std::memcpy(w.data()+2*j,&value,2);}
  }
  if constexpr(T==iq3::Type::Q6_K||T==iq3::Type::Q8_0){constexpr unsigned group=T==iq3::Type::Q6_K?16:32;
   for(unsigned j=0;j<K/group;++j){uint32_t v=finite?std::bit_cast<uint32_t>(iq3::half(scales[(trial+j)%14])):bits;std::memcpy(w.data()+K+4*j,&v,4);}
  }
  for(unsigned split:{1u,4u}){float parts[4]{};const auto key=prefix+".split"+std::to_string(split);
   for(unsigned part=0;part<split;++part){auto bounds=iq3::kopt2::bounds(K,part,split);float lanes[32]{},oracle[32]{};
    for(unsigned lane=0;lane<32;++lane){lanes[lane]=p33::dense_lane<T,K>(w.data(),x.data(),bounds.first,bounds.second,lane);oracle[lane]=iq3::expanded::lane(T,w.data(),x.data(),iq3::Type::BF16,K,bounds.first,bounds.second,lane);check((key+".lane").c_str(),lanes[lane],oracle[lane],finite);check((key+".p28").c_str(),lanes[lane],p28::dense_lane<T,K>(w.data(),x.data(),bounds.first,bounds.second,lane),finite);}
    parts[part]=iq3::tree32(lanes);check((key+".tree").c_str(),parts[part],iq3::tree32(oracle),finite);
   }
   float v=split==1?parts[0]:(parts[0]+parts[1])+(parts[2]+parts[3]);float ref=iq3::expanded::row(T,w.data(),x.data(),iq3::Type::BF16,K,split);
   check((key+".row").c_str(),v,ref,finite);check((key+".bf16").c_str(),float(iq3::bf16_bits(v)),float(iq3::bf16_bits(ref)),finite);
  }
  // Partial tails, unaligned starts crossing quant scale groups, and empty ranges.
  for(auto range:std::array<std::array<unsigned,2>,8>{{{0,1},{0,3},{0,17},{0,255},{0,K-1},{3,33},{15,257},{K,K}}})
   for(unsigned lane=0;lane<32;++lane)check((prefix+".odd-range").c_str(),p33::dense_lane<T,K>(w.data(),x.data(),range[0],range[1],lane),iq3::expanded::lane(T,w.data(),x.data(),iq3::Type::BF16,K,range[0],range[1],lane),finite);
 }
}
template<unsigned K>void dense_formats(const std::string& label){
 if constexpr(K%256==0)dense_class<iq3::Type::Q6_K,K>(label);
 dense_class<iq3::Type::Q8_0,K>(label);dense_class<iq3::Type::F32,K>(label);dense_class<iq3::Type::BF16,K>(label);
}
void dense_all(){for(const auto& shape:p28::shapes)if(!p28::expert(shape.type)){
 switch(shape.k){case 320:dense_formats<320>(shape.label);break;case 640:dense_formats<640>(shape.label);break;case 2560:dense_formats<2560>(shape.label);break;case 6144:dense_formats<6144>(shape.label);break;case 10240:dense_formats<10240>(shape.label);break;default:throw std::runtime_error("ungated dense shape");}
}}
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
 expert<iq3::Type::IQ2_S,512>();expert<iq3::Type::IQ3_S,512>();expert<iq3::Type::IQ3_XXS,512>();expert_production<iq3::Type::IQ2_S,2560>();expert_production<iq3::Type::IQ3_S,2560>();dense_all();qsa<1>(argv[1]);qsa<3>(argv[1]);
 bool pass=true;std::cout<<"{\"device_executed\":false,\"nan_tolerance\":false,\"nonfinite_qualified\":false,\"candidates\":{";unsigned n=0;for(auto&[name,s]:stats){if(n++)std::cout<<',';pass=pass&&(name=="qsa.stored-expected-diagnostic"||!s.failures);std::cout<<'"'<<name<<"\":{\"checks\":"<<s.checks<<",\"failures\":"<<s.failures<<",\"nonfinite_checks\":"<<s.nonfinite_checks<<",\"nonfinite_failures\":"<<s.nonfinite_failures<<",\"hash\":\""<<std::hex<<s.hash<<std::dec<<"\"}";}std::cout<<"},\"passed\":"<<(pass?"true":"false")<<"}\n";return pass?0:1;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 2;}}
