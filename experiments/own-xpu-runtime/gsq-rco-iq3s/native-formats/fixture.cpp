#include "packed.hpp"
#include <openssl/evp.h>
#include <iostream>
#include <map>
#include <cstring>
using namespace ownrt;
static void need(bool b,const char*s){if(!b)throw std::runtime_error(s);}
static std::string hash(const std::vector<uint8_t>&v){unsigned char b[32];unsigned n;EVP_Digest(v.data(),v.size(),b,&n,EVP_sha256(),nullptr);std::string s;for(auto x:b){s+="0123456789abcdef"[x>>4];s+="0123456789abcdef"[x&15];}return s;}
struct Fixture{
 Host*host=new Host;Device d{std::unique_ptr<Backend>(host)};integrated::Matrix m{};Allocation decoy,extra;bool closed=false;
 Fixture(unsigned type,bool routed,bool per_slot){m.type=static_cast<iq3::Type>(type);m.rows=17;m.columns=type==42?640:2560;m.experts=routed?3:1;m.count=routed?10:1;m.span=m.rows;
  m.w=alloc(gsq::row_bytes(type,m.columns)*m.rows*m.experts);m.x=alloc(m.columns*2*(per_slot?m.count:1));m.y=alloc(m.rows*m.count*2);if(routed){m.routes=alloc(m.count*sizeof(iq3::Route));m.status=alloc(m.count*4);}decoy=alloc(m.rows*m.count*2);extra=alloc(4);
  auto*r=ptr<uint8_t>(m.w);auto layout=gsq::layout(type);for(size_t i=0;i<d.arena.row(m.w).bytes;++i)r[i]=uint8_t((i*29+17)^(i/7));for(size_t i=0;i<d.arena.row(m.w).bytes;i+=layout.bytes){uint16_t scale=0x3800;std::memcpy(r+i,&scale,2);if(type==12||type==13){scale=0x3000;std::memcpy(r+i+2,&scale,2);}}
  for(size_t i=0;i<d.arena.row(m.x).bytes/2;++i)ptr<uint16_t>(m.x)[i]=iq3::bf16_bits(float(int(i%19)-9)/16);
  if(routed){for(unsigned i=0;i<m.count;++i)ptr<iq3::Route>(m.routes)[i]={i%3,0,17};ptr<iq3::Route>(m.routes)[0]={1,1,15};ptr<iq3::Route>(m.routes)[1]={2,0,0};ptr<iq3::Route>(m.routes)[2]={3,0,17};}
 }
 Allocation alloc(size_t n){auto id=d.arena.allocate("card0:gsq-"+std::to_string(next++),n,Memory::device,Category::scratch,Lifetime::transaction);std::memset(d.arena.row(id).pointer,0xa5,n);return id;}unsigned next=0;
 template<class T>T*ptr(Allocation id){return static_cast<T*>(d.arena.row(id).pointer);}
 std::vector<uint8_t>bytes(Allocation id){auto&r=d.arena.row(id);auto*p=static_cast<uint8_t*>(r.pointer);return {p,p+r.bytes};}
 std::vector<uint16_t>expected(bool per_slot){std::vector<uint16_t>out(m.rows*m.count);size_t rb=gsq::row_bytes(unsigned(m.type),m.columns);for(unsigned slot=0;slot<m.count;++slot){auto r=m.routes?ptr<iq3::Route>(m.routes)[slot]:iq3::Route{0,0,uint32_t(m.rows)};bool valid=iq3::valid_route(r,m.experts,m.rows,m.rows);for(size_t row=0;row<m.rows;++row){float value=iq3::bits_float(0x7fc00000);if(valid&&row<r.row_count){auto w=ptr<uint8_t>(m.w)+(size_t(r.expert_id)*m.rows+r.row_begin+row)*rb;auto x=ptr<uint16_t>(m.x)+(per_slot?slot*m.columns:0);value=gsq::row_gemv(unsigned(m.type),{w,rb},{x,m.columns});}out[slot*m.rows+row]=iq3::bf16_bits(value);}}return out;}
 void verify(bool per_slot){auto ex=expected(per_slot);need(!std::memcmp(ex.data(),ptr<uint16_t>(m.y),ex.size()*2),"CPU ABI scalar output mismatch");if(m.routes)for(unsigned i=0;i<m.count;++i)need(ptr<uint32_t>(m.status)[i]==unsigned(!iq3::valid_route(ptr<iq3::Route>(m.routes)[i],m.experts,m.rows,m.rows)),"route status mismatch");}
 void done(Event e){need(d.wait(e,std::chrono::milliseconds(100))&&d.complete(e)&&d.in_flight()==0,"CPU marker completion");d.retire_completed_events();}
 std::string close(){auto receipt=d.shutdown(std::chrono::milliseconds(100));need(receipt.safe_to_exit&&receipt.exit_code==0&&receipt.in_flight==0&&receipt.live_bytes==0,"owner clean close");closed=true;return receipt.json();}
 ~Fixture(){if(!closed){auto r=d.shutdown(std::chrono::milliseconds(100));if(!r.safe_to_exit)std::abort();}}
};
int main(){try{unsigned cases=0,checks=0,refusals=0;std::vector<std::string>rows,owners;
 for(unsigned type:{12,13,18,23,42})for(unsigned mode=0;mode<3;++mode){Fixture f(type,mode>0,mode==2);auto input=mode==2?gsqn::InputMode::per_slot:gsqn::InputMode::shared;
  auto before=f.bytes(f.m.y),decoy=f.bytes(f.decoy);std::vector<PreparedCompute>commands;f.d.begin_capture(commands);auto caller=f.m;gsqn::submit(f.d,caller,input,gsqn::Storage::packed_direct);f.d.end_capture();caller.w=0;caller.y=f.decoy;caller.rows=1;
  need(commands.size()==1&&f.bytes(f.m.y)==before&&f.d.in_flight()==0,"capture nonexecution");++checks;
  f.done(f.d.issue(commands[0]));f.verify(mode==2);need(f.bytes(f.decoy)==decoy,"caller mutation redirected capture");++checks;
  auto first=f.bytes(f.m.y);for(size_t i=0;i<f.d.arena.row(f.m.x).bytes/2;++i)f.ptr<uint16_t>(f.m.x)[i]=iq3::bf16_bits(float((i%7)+1)/8);
  f.done(f.d.issue(commands[0]));f.verify(mode==2);need(first!=f.bytes(f.m.y),"live input vacuity");++checks;
  auto second=f.bytes(f.m.y);auto*weights=f.ptr<uint8_t>(f.m.w);uint16_t doubled=0x4000;auto fmt=gsq::layout(type);for(size_t i=0;i<f.d.arena.row(f.m.w).bytes;i+=fmt.bytes)std::memcpy(weights+i,&doubled,2);
  f.done(f.d.issue(commands[0]));f.verify(mode==2);need(second!=f.bytes(f.m.y),"live weight vacuity");++checks;
  auto refuse=[&](auto fn){bool caught=false;auto y=f.bytes(f.m.y);try{fn();}catch(const std::exception&){caught=true;}need(caught&&y==f.bytes(f.m.y),"binding refusal/write");++refusals;};
  auto bad=f.m;bad.y=bad.x;refuse([&]{gsqn::submit(f.d,bad,input,gsqn::Storage::packed_direct);});bad=f.m;bad.w=f.extra;refuse([&]{gsqn::submit(f.d,bad,input,gsqn::Storage::packed_direct);});bad=f.m;bad.columns=0;refuse([&]{gsqn::submit(f.d,bad,input,gsqn::Storage::packed_direct);});bad=f.m;bad.type=static_cast<iq3::Type>(999);refuse([&]{gsqn::submit(f.d,bad,input,gsqn::Storage::packed_direct);});
  refuse([&]{gsqn::submit(f.d,f.m,static_cast<gsqn::InputMode>(99),gsqn::Storage::packed_direct);});
  if(mode){bad=f.m;bad.status=bad.y;refuse([&]{gsqn::submit(f.d,bad,input,gsqn::Storage::packed_direct);});}
  f.d.arena.release(f.extra);refuse([&]{f.d.issue(commands[0]);});
  rows.push_back("{\"type\":"+std::to_string(type)+",\"mode\":"+std::to_string(mode)+",\"columns\":"+std::to_string(f.m.columns)+",\"rows\":17,\"count\":"+std::to_string(f.m.count)+",\"output_sha256\":\""+hash(f.bytes(f.m.y))+"\"}");owners.push_back(f.close());++cases;
 }
 std::cout<<"{\"passed\":true,\"cases\":"<<cases<<",\"checks\":"<<checks<<",\"refusals\":"<<refusals<<",\"device_executed\":false,\"scope\":\"actual runtime owner and captured CPU operations; simulated Host backend events\",\"rows\":[";for(size_t i=0;i<rows.size();++i)std::cout<<(i?",":"")<<rows[i];std::cout<<"],\"owners\":[";for(size_t i=0;i<owners.size();++i)std::cout<<(i?",":"")<<owners[i];std::cout<<"]}\n";return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
