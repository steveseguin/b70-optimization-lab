#include "cache_table.hpp"
#include "p49d_expert.hpp"
#include <cstring>
#include <iostream>
#include <vector>
extern "C" void p58_production(unsigned,unsigned,unsigned,unsigned,void**);
namespace {
size_t checks=0,values=0;uint64_t digest=1469598103934665603ull;bool portable=true;
void require(bool v,const char*m){++checks;if(!v)throw std::runtime_error(m);}
void bytes_equal(const void*a,const void*b,size_t n){require(!std::memcmp(a,b,n),"production byte mismatch");if(portable)for(size_t i=0;i<n;++i){digest^=static_cast<const uint8_t*>(a)[i];digest*=1099511628211ull;}values+=n;}
struct Arena{void*p;explicit Arena(size_t n):p(::operator new(n,std::align_val_t(256))){}~Arena(){::operator delete(p,std::align_val_t(256));}};
std::vector<uint8_t> bank(iq3::Type t,unsigned k,unsigned rows,unsigned experts,unsigned seed,bool compact){
 auto f=iq3::layout(t);unsigned source_rb=k/f.elements*f.bytes;unsigned rb=compact?p49bgemv::layout(t,k).row_bytes:source_rb;
 std::vector<uint8_t> out(size_t(rb)*rows*experts),raw(source_rb);uint32_t state=seed;
 for(unsigned row=0;row<rows*experts;++row){for(auto&v:raw){state=state*1664525+1013904223;v=state>>24;}
  for(unsigned block=0;block<k/f.elements;++block){uint16_t scale=uint16_t(0x1400+(row+block)%0x400);std::memcpy(raw.data()+block*f.bytes,&scale,2);}
  auto*d=out.data()+size_t(row)*rb;if(compact)p49bgemv::repack_row(t,k,raw.data(),d);else std::memcpy(d,raw.data(),rb);
 }return out;
}
struct Result {std::vector<uint16_t> y,py;std::vector<uint32_t> status,peer_status;uint32_t error=0,active=1;
 Result(unsigned rows,unsigned count):y(rows*count,0xa5a5),py(rows*count,0xb6b6),status(count,91),peer_status(count,92){}
};
void invoke(unsigned kind,bool indirect,unsigned rows,unsigned count,unsigned experts,void*w,void*up,const std::vector<uint16_t>&x,const std::vector<iq3::Route>&routes,Result&r,bool reference){
 void*p[18]{};p[0]=w;p[1]=up;p[2]=const_cast<uint16_t*>(x.data());p[3]=r.y.data();p[4]=r.py.data();p[5]=const_cast<iq3::Route*>(routes.data());p[6]=r.status.data();p[7]=r.peer_status.data();p[16]=&r.error;p[17]=&r.active;
 if(reference){p58_production(kind,rows,count,experts,p);return;}
 if(kind==0){p49dvirtual::GateKernel k;k.rows=rows;k.count=count;k.experts=experts;k.indirect=indirect;k.run(p);}
 else if(kind==2){p49dvirtual::DownKernel k;k.rows=rows;k.count=count;k.experts=experts;k.indirect=indirect;k.run(p);}
 else {p39::Bound b{};b.indirect=indirect;b.rows=rows;b.count=count;b.experts=experts;b.rb=1100;b.w=static_cast<uint8_t*>(w);b.peer=static_cast<uint8_t*>(up);b.x=x.data();b.y=r.y.data();b.py=r.py.data();b.routes=routes.data();b.status=r.status.data();b.peer_status=r.peer_status.data();b.error=&r.error;b.active=&r.active;
  p39::host_gemv<iq3::Type::IQ3_S,2560,p39::Kind::expert_checks,true,1>(b);
 }
}
void compare(const Result&a,const Result&b){bytes_equal(a.y.data(),b.y.data(),a.y.size()*2);bytes_equal(a.py.data(),b.py.data(),a.py.size()*2);bytes_equal(a.status.data(),b.status.data(),a.status.size()*4);bytes_equal(a.peer_status.data(),b.peer_status.data(),a.peer_status.size()*4);bytes_equal(&a.error,&b.error,4);}
void suite(unsigned kind){constexpr unsigned experts=3,count=3,rows=640,down_rows=2560;auto type=kind?iq3::Type::IQ3_S:iq3::Type::IQ2_S;
 auto gate=bank(type,2560,rows,experts,5801,!kind),up=bank(type,2560,rows,experts,5802,!kind),down=bank(iq3::Type::IQ4_NL,640,down_rows,experts,5803,true);
 size_t gb=gate.size()/experts,ub=up.size()/experts,db=down.size()/experts,total=((gb+ub+db+255)&~size_t(255))*experts;Arena arena(total);
 std::vector<p58::Expert>descriptors;for(unsigned id=0;id<experts;++id)descriptors.push_back({uint64_t(gate.data()+id*gb),uint64_t(up.data()+id*ub),uint64_t(down.data()+id*db),gb,ub,db});
 for(unsigned mask:{0u,7u,5u}){p58::Cache cache(descriptors,uint64_t(arena.p),total);std::vector<uint32_t>admit;for(unsigned id=0;id<experts;++id)if(mask&(1u<<id))admit.push_back(id);auto plan=cache.prepare(admit);
  for(auto f:plan.fills){auto*d=static_cast<uint8_t*>(arena.p)+f.offset;std::memcpy(d,reinterpret_cast<void*>(f.gate),gb);std::memcpy(d+gb,reinterpret_cast<void*>(f.up),ub);std::memcpy(d+gb+ub,reinterpret_cast<void*>(f.down),db);}cache.commit(0,true,true);
  std::vector<p58::Pointer>gt,ut,dt;for(auto t:cache.table()){gt.push_back({t.gate,t.generation});ut.push_back({t.up,t.generation});dt.push_back({t.down,t.generation});}
  for(unsigned scenario=0;scenario<6;++scenario){portable=scenario<4;std::vector<uint16_t>x(2560);for(size_t i=0;i<x.size();++i)x[i]=iq3::bf16_bits(float(int((i*37+scenario*73)%257)-128)/512.f);
   if(scenario==3){x[0]=0x8000;x[1]=0x0001;x[8]=0x8001;}if(scenario==4)x[0]=0x7fc1;if(scenario==5){x[0]=0x7f80;x[8]=0xff80;}
   std::vector<iq3::Route>routes{{2,0,rows},{0,0,rows},{1,0,rows}};if(scenario==1)routes[1]={0,13,rows-13};if(scenario==2)routes[2]={experts,0,rows};
   Result expected(rows,count),actual(rows,count);invoke(kind,false,rows,count,experts,gate.data(),up.data(),x,routes,expected,true);invoke(kind,true,rows,count,experts,gt.data(),ut.data(),x,routes,actual,false);compare(expected,actual);
   // Complete expert pipeline: unchanged BF16 SiLU/product then production down.
   std::vector<uint16_t>middle(rows*count),middle_ref(rows*count);for(size_t i=0;i<middle.size();++i){middle[i]=p39::activation(actual.y[i],actual.py[i]);middle_ref[i]=p39::activation(expected.y[i],expected.py[i]);}bytes_equal(middle.data(),middle_ref.data(),middle.size()*2);
   std::vector<iq3::Route>dr{{2,0,down_rows},{0,0,down_rows},{1,0,down_rows}};if(scenario==1)dr[1]={0,11,down_rows-11};if(scenario==2)dr[2]={experts,0,down_rows};
   Result de(down_rows,count),da(down_rows,count);invoke(2,false,down_rows,count,experts,down.data(),down.data(),middle_ref,dr,de,true);invoke(2,true,down_rows,count,experts,dt.data(),dt.data(),middle,dr,da,false);compare(de,da);
  }cache.close();
 }
}
}
int main(){try{suite(0);suite(1);std::cout<<"{\"schema\":\"packet58.expert-pointer-cpu.v1\",\"passed\":true,\"device_executed\":false,\"production_reference\":\"packet49d-round3\",\"formats\":[\"IQ2_S/IQ4_NL\",\"IQ3_S/IQ4_NL\"],\"placements\":[\"all-miss\",\"all-hit\",\"mixed\"],\"canonical_digest_excludes_scenarios\":[4,5],\"scenarios\":6,\"cases\":36,\"checks\":"<<checks<<",\"compared_bytes\":"<<values<<",\"fnv1a64\":\""<<std::hex<<digest<<"\"}\n";}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
