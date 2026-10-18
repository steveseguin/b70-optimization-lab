#include "p72_attention.hpp"
#include <filesystem>
#include <fstream>
#include <iostream>
void require(bool ok,const char* s){if(!ok)throw std::runtime_error(s);}
int main(int argc,char**argv){try{
 require(argc==2,"output required");std::filesystem::path out=argv[1];std::filesystem::create_directories(out);
 std::ofstream expected(out/"expected.bin",std::ios::binary),actual(out/"candidate.bin",std::ios::binary),cases(out/"cases.jsonl");
 unsigned count=0,chain_checks=0;uint32_t seed=72;
 auto rng=[&](){seed=seed*1664525u+1013904223u;return seed;};
 for(unsigned rows:{1u,17u,2560u}){
  auto rb=integrated::arithmetic::row_bytes(iq3::Type::Q6_K,6144,7);
  std::vector<uint8_t>w(rows*rb);for(auto&v:w)v=rng()>>24;
  for(unsigned r=0;r<rows;++r)for(unsigned k=0;k<384;++k){float s=float(int(rng()%129)-64)/1024.f;std::memcpy(w.data()+r*rb+6144+4*k,&s,4);}
  for(unsigned scenario=0;scenario<8;++scenario){
   std::vector<uint16_t>x(6144);for(auto&v:x)v=iq3::bf16_bits(float(int(rng()%33)-16)/32.f);
   if(scenario==5){x[0]=0x7fc1;x[8]=0xffd5;}
   if(scenario==6){x[0]=0x7f80;x[8]=0xff80;}
   if(scenario==7){x[0]=1;x[1]=0x8001;x[8]=0;x[9]=0x8000;}
   std::vector<uint16_t>ey(rows,0x7e31),ay=ey,es(rows*4,0x3d80),as=es;
   std::array<uint16_t,4>inject{0x3f00,0xbe80,0x3e00,0xbf00};
   uint32_t active=scenario==1?0:1,ee=scenario==2?7:0,ae=ee,pos=scenario==3?4096:scenario==4?0xffffffff:23;
   auto pointers=[&](auto&y,auto&s,uint32_t&e){std::array<void*,19>p{};p[0]=w.data();p[2]=x.data();p[3]=y.data();p[11]=s.data();p[12]=inject.data();p[16]=&e;p[17]=&active;p[18]=&pos;return p;};
   p49c::DenseKernel<iq3::Type::Q6_K,6144,4,p39::Kind::attention_combine>baseline;
   p72::AttentionKernel candidate;baseline.shape.rows=candidate.shape.rows=rows;baseline.shape.rb=candidate.shape.rb=rb;baseline.shape.capacity=candidate.shape.capacity=4096;
   auto ep=pointers(ey,es,ee),ap=pointers(ay,as,ae);baseline.run(ep);candidate.run(ap);
   auto compare=[&](const void*a,const void*b,size_t n){require(std::memcmp(a,b,n)==0,"operator bytes differ");expected.write(static_cast<const char*>(a),n);actual.write(static_cast<const char*>(b),n);};
   compare(ey.data(),ay.data(),rows*2);compare(es.data(),as.data(),rows*8);compare(&ee,&ae,4);
   for(unsigned row=0;row<std::min(rows,17u);++row)for(unsigned part=0;part<4;++part){
    auto bounds=iq3::kopt2::bounds(6144,part,4);float original[32],packed[16];
    for(unsigned physical=0;physical<16;++physical){auto v=p72::chains(w.data()+row*rb,x.data(),bounds.first,bounds.second,physical);
     for(unsigned c=0;c<2;++c){original[physical*2+c]=p49c::dense_lane<iq3::Type::Q6_K,6144>(w.data()+row*rb,x.data(),bounds.first,bounds.second,physical*2+c);compare(&original[physical*2+c],&v[c],4);++chain_checks;}
     packed[physical]=v[0]+v[1];
    }
    for(unsigned width=1;width<16;width*=2)for(unsigned k=0;k<16;k+=2*width)packed[k]=packed[k]+packed[k+width];
    auto root=iq3::tree32(original);compare(&root,packed,4);
   }
   cases<<"{\"rows\":"<<rows<<",\"scenario\":"<<scenario<<",\"passed\":true}\n";++count;
  }
 }
 expected.close();actual.close();cases.close();require(bool(expected)&&bool(actual)&&bool(cases),"flush");
 std::ofstream(out/"native.json")<<"{\"passed\":true,\"device_executed\":false,\"cases\":"<<count<<",\"raw_chain_checks\":"<<chain_checks<<"}\n";
 std::cout<<count<<" operator cases, "<<chain_checks<<" raw chains PASS\n";
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
