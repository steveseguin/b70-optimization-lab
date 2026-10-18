// Direct production/candidate byte oracle, including exceptional arithmetic.
#include "p119_warm.hpp"
#include <filesystem>
#include <fstream>
#include <iostream>
#include <cstring>
using iq3::Type;
void require(bool v,const char*msg){if(!v)throw std::runtime_error(msg);}
uint32_t next(uint32_t&s){s=s*1664525u+1013904223u;return s;}
int main(int argc,char**argv){try{
 require(argc==2,"output directory");const std::filesystem::path out=argv[1];
 std::ofstream expected(out/"expected.bin",std::ios::binary),candidate(out/"candidate.bin",std::ios::binary),cases(out/"cases.jsonl");
 auto equal=[&](const void*a,const void*b,size_t n){require(!std::memcmp(a,b,n),"byte mismatch");expected.write((const char*)a,n);candidate.write((const char*)b,n);};
 constexpr unsigned rows=640,count=10,experts=12,K=2560;constexpr size_t stride=p90::expert_stride(K);
 uint32_t seed=119;std::vector<uint8_t> w(size_t(rows)*experts*stride),up(w.size()),down(experts*p119::expert_bytes);
 for(auto* bank:{&w,&up})for(size_t r=0;r<size_t(rows)*experts;++r){auto* p=bank->data()+r*stride;for(size_t i=0;i<stride;++i)p[i]=next(seed)>>24;
  for(unsigned b=0;b<10;++b){float scale=float(int(next(seed)%17)-8)/64;std::memcpy(p+800+4*b,&scale,4);}}
 for(auto&v:down)v=next(seed)>>24;
 const auto original_down=down;
 size_t chain_checks=0,comparisons=0;
 for(unsigned scenario=0;scenario<10;++scenario){
  std::vector<uint16_t>x(K);for(auto&v:x)v=iq3::bf16_bits(float(int(next(seed)%33)-16)/32);
  if(scenario==1){x[0]=0x7fc1;x[8]=0xffd5;}if(scenario==2){x[0]=0x7f80;x[8]=0xff80;}
  if(scenario==3){x[0]=1;x[1]=0x8001;x[8]=0;x[9]=0x8000;}
  std::vector<iq3::Route>routes(count);for(unsigned i=0;i<count;++i)routes[i]={(3*i+1)%experts,0,rows};
  if(scenario>=4&&scenario<=6)routes[2].expert_id=experts;
  if(scenario==7){routes[0].row_count=0;routes[1].row_begin=1;routes[1].row_count=rows-2;routes[2].row_begin=rows;routes[2].row_count=1;}
  if(scenario==8){routes[0].expert_id=routes[1].expert_id;routes[count-1].expert_id=experts-1;}
  if(scenario==9){uint32_t bits=0x7fc00119;std::memcpy(w.data()+800,&bits,4);bits=0xff800000;std::memcpy(up.data()+800,&bits,4);routes[0].expert_id=0;}
  std::vector<uint16_t> y(rows*count,0xbeef),py(y),z(y),pz(y);
  std::vector<uint32_t>status(count,9),peer_status(status),cs(status),cps(status);
  uint32_t error=scenario==6?7:0,ce=error,active=scenario==5?0:1,position=4095;
  std::array<void*,19>a{};a[0]=w.data();a[1]=up.data();a[2]=x.data();a[3]=y.data();a[4]=py.data();a[5]=routes.data();a[6]=status.data();a[7]=peer_status.data();a[9]=down.data();a[16]=&error;a[17]=&active;a[18]=&position;
  auto b=a;b[3]=z.data();b[4]=pz.data();b[6]=cs.data();b[7]=cps.data();b[16]=&ce;
  p90exp::Kernel<Type::IQ2_S,K,64,false,true> reference;reference.rows=rows;reference.count=count;reference.experts=experts;reference.run(a);
  p119::Kernel warmed;warmed.rows=rows;warmed.count=count;warmed.experts=experts;warmed.run(b);
  equal(y.data(),z.data(),y.size()*2);equal(py.data(),pz.data(),py.size()*2);equal(status.data(),cs.data(),status.size()*4);equal(peer_status.data(),cps.data(),peer_status.size()*4);equal(&error,&ce,4);comparisons+=5;
  for(unsigned r:{0u,1u,7u,8u,639u,640u,rows*experts-1})for(unsigned stream=0;stream<2;++stream)for(unsigned lane=0;lane<4;++lane){
   const auto*weight=(stream?up:w).data()+r*stride;
   auto c=p90exp::wide_chains<Type::IQ2_S,K,8>(weight,x.data(),lane);
   auto d=p119::wide_chains<Type::IQ2_S,K,8>(weight,x.data(),lane,down.data()+(r/rows)*p119::expert_bytes,(r%rows)*8+stream*4+lane,p119::full_lines);
   equal(c.data(),d.data(),sizeof(c));chain_checks+=8;
  }
  cases<<"{\"scenario\":"<<scenario<<",\"passed\":true}\n";
 }
 require(down==original_down,"warming wrote weights");
 // Exact address coverage, no duplicate loads, cache capacity cap, last expert bound.
 for(uint64_t cache:{0ull,1ull,1024ull,4ull<<20,8ull<<20,16ull<<20,32ull<<20}){
  auto limit=p119::warm_lines(cache);require(uint64_t(limit)*count*64<=cache/4*3,"cache budget");
  std::vector<unsigned> coverage(p119::full_lines);
  for(unsigned row=0;row<640;++row)for(unsigned stream=0;stream<2;++stream)for(unsigned lane=0;lane<4;++lane)for(unsigned step=7;step<10;++step){unsigned line=row*8+stream*4+lane+(step-7)*5120;if(line<limit)++coverage[line];}
  for(unsigned i=0;i<coverage.size();++i)require(coverage[i]==unsigned(i<limit),"unique bounded line coverage");
 }
 std::ofstream f(out/"native.json");f<<"{\"passed\":true,\"device_executed\":false,\"cases\":10,\"output_status_checks\":"<<comparisons<<",\"raw_fp32_chain_checks\":"<<chain_checks<<",\"weight_bytes_unchanged\":"<<down.size()<<",\"cache_mapping_checks\":7}";
 return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
