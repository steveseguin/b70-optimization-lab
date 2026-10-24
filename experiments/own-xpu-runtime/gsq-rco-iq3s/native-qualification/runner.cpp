#include "../native-formats/packed.hpp"
#include <openssl/evp.h>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <cstring>
#include <csignal>
#include <sys/resource.h>
#include <sys/stat.h>
namespace qualification {
namespace fs=std::filesystem;
using namespace ownrt;
volatile std::sig_atomic_t stopped=0;
void stop(int){stopped=1;}
void guard(){if(stopped)throw std::runtime_error("cooperative stop requested; no further submissions");}
void need(bool b,const char*s){if(!b)throw std::runtime_error(s);}
std::string sha(const std::vector<uint8_t>&v){unsigned char b[32];unsigned n;need(EVP_Digest(v.data(),v.size(),b,&n,EVP_sha256(),nullptr)==1,"digest");std::string s;for(auto x:b){s+="0123456789abcdef"[x>>4];s+="0123456789abcdef"[x&15];}return s;}
template<class T>std::vector<uint8_t>raw(const std::vector<T>&v){auto*p=reinterpret_cast<const uint8_t*>(v.data());return {p,p+v.size()*sizeof(T)};}
struct Fixture {
 Device&d;Allocation slab;size_t &transfers,&allocation_bytes,&submissions;unsigned serial=0;
 Fixture(Device&device,size_t&t,size_t&a,size_t&n):d(device),transfers(t),allocation_bytes(a),submissions(n){slab=d.arena.allocate("card0:gsq-qualification-slab",1024*1024,Memory::pinned,Category::pinned_slab,Lifetime::transfer);}
 Allocation alloc(size_t n){guard();allocation_bytes+=n;need(allocation_bytes<1024*1024,"synthetic allocation budget");return d.arena.allocate("card0:gsq-qualification-"+std::to_string(serial++),n,Memory::device,Category::scratch,Lifetime::transaction);}
 void complete(Event e){need(d.wait(e,std::chrono::seconds(30))&&d.complete(e)&&d.in_flight()==0,"native event incomplete");d.retire_completed_events();guard();}
 void upload(Allocation id,const std::vector<uint8_t>&data){guard();need(data.size()==d.arena.row(id).bytes&&data.size()<=1024*1024,"upload extent");need(d.in_flight()==0,"pinned restage while pending");std::memcpy(d.arena.row(slab).pointer,data.data(),data.size());transfers+=data.size();need(transfers<1024*1024,"transfer budget");CopyEngine cp(d);complete(cp.copy(id,0,slab,0,data.size(),{}));}
 std::vector<uint8_t>read(Allocation id){guard();size_t n=d.arena.row(id).bytes;need(n<=1024*1024&&d.in_flight()==0,"readback extent/pending");transfers+=n;need(transfers<1024*1024,"transfer budget");CopyEngine cp(d);complete(cp.copy(slab,0,id,0,n,{}));auto*p=static_cast<const uint8_t*>(d.arena.row(slab).pointer);return {p,p+n};}
 std::string run(unsigned type,unsigned mode){
  integrated::Matrix m{};m.type=static_cast<iq3::Type>(type);m.rows=5;m.columns=type==42?640:2560;m.experts=mode?2:1;m.count=mode?4:1;m.span=m.rows;auto input=mode==2?gsqn::InputMode::per_slot:gsqn::InputMode::shared;
  auto fmt=gsq::layout(type);size_t rb=gsq::row_bytes(type,m.columns);std::vector<uint8_t>w(m.rows*m.experts*rb);
  for(size_t i=0;i<w.size();++i)w[i]=uint8_t((i*29+17)^(i/7));for(size_t i=0;i<w.size();i+=fmt.bytes){uint16_t h=0x3800;std::memcpy(w.data()+i,&h,2);if(type==12||type==13){h=0x3000;std::memcpy(w.data()+i+2,&h,2);}}
  std::vector<uint16_t>x(m.columns*(mode==2?m.count:1));for(size_t i=0;i<x.size();++i)x[i]=iq3::bf16_bits(float(int(i%19)-9)/16);
  std::vector<iq3::Route>routes{{1,1,3},{0,0,5},{1,0,0},{2,0,5}};
  m.w=alloc(w.size());m.x=alloc(x.size()*2);m.y=alloc(m.rows*m.count*2);auto decoy=alloc(m.rows*m.count*2);
  upload(m.w,w);upload(m.x,raw(x));std::vector<uint8_t>sentinel(m.rows*m.count*2,0xa5);upload(m.y,sentinel);upload(decoy,sentinel);
  if(mode){m.routes=alloc(routes.size()*sizeof(iq3::Route));m.status=alloc(m.count*4);upload(m.routes,raw(routes));upload(m.status,std::vector<uint8_t>(m.count*4,0xa5));}
  auto expected=[&]{std::vector<uint16_t>out(m.rows*m.count);for(unsigned slot=0;slot<m.count;++slot){auto r=mode?routes[slot]:iq3::Route{0,0,uint32_t(m.rows)};bool valid=iq3::valid_route(r,m.experts,m.rows,m.rows);for(size_t row=0;row<m.rows;++row){float v=iq3::bits_float(0x7fc00000);if(valid&&row<r.row_count)v=gsq::row_gemv(type,{w.data()+(size_t(r.expert_id)*m.rows+r.row_begin+row)*rb,rb},{x.data()+(mode==2?slot*m.columns:0),m.columns});out[slot*m.rows+row]=iq3::bf16_bits(v);}}return raw(out);};
  auto verify=[&]{auto output=read(m.y);need(output==expected(),"native/scalar BF16 mismatch");if(mode){std::vector<uint32_t>status{0,0,0,1};need(read(m.status)==raw(status),"native route status mismatch");}return output;};
  std::vector<PreparedCompute>commands;d.begin_capture(commands);try{auto caller=m;gsqn::submit(d,caller,input,gsqn::Storage::packed_direct);caller.y=decoy;caller.rows=1;caller.w=0;d.end_capture();}catch(...){d.end_capture();throw;}
  need(commands.size()==1&&read(m.y)==sentinel,"capture unexpectedly executed");guard();++submissions;complete(d.issue(commands[0]));auto first=verify();need(read(decoy)==sentinel,"caller metadata redirected capture");
  for(size_t i=0;i<x.size();++i)x[i]=iq3::bf16_bits(float((i%7)+1)/8);upload(m.x,raw(x));guard();++submissions;complete(d.issue(commands[0]));auto second=verify();need(second!=first,"live input did not affect output");
  for(size_t i=0;i<w.size();i+=fmt.bytes){uint16_t h=0x4000;std::memcpy(w.data()+i,&h,2);}upload(m.w,w);guard();++submissions;complete(d.issue(commands[0]));auto third=verify();need(third!=second,"live weights did not affect output");
  return "{\"type\":"+std::to_string(type)+",\"mode\":"+std::to_string(mode)+",\"rows\":5,\"columns\":"+std::to_string(m.columns)+",\"count\":"+std::to_string(m.count)+",\"passed\":true,\"status_and_tail_exact\":true,\"capture_and_live_data\":true,\"first_output_sha256\":"+quote(sha(first))+",\"changed_input_sha256\":"+quote(sha(second))+",\"changed_weight_sha256\":"+quote(sha(third))+"}";
 }
};
int run(unsigned card,const fs::path&output){
 need(output.is_absolute()&&!fs::exists(output)&&!fs::is_symlink(output),"fresh absolute output required");need(fs::create_directory(output),"new output directory");
 std::unique_ptr<Device>d;Backend*backend=nullptr;bool factory_entered=false,safe=false,passed=false;std::string error,cleanup_error,teardown;std::vector<std::string>cases;size_t transferred=0,allocated=0,submissions=0;
 auto report=[&]()noexcept{try{std::ofstream out(output/"result.json");out<<"{\"schema\":\"gsq.native-format-qualification.v1\",\"passed\":"<<(passed?"true":"false")<<",\"safe_to_exit\":"<<(safe?"true":"false")<<",\"device_executed\":"<<(factory_entered?"true":"false")<<",\"kernel_submissions_attempted\":"<<submissions<<",\"model_executed\":false,\"card_selector\":"<<card<<",\"error\":"<<quote(error)<<",\"cleanup_error\":"<<quote(cleanup_error)<<",\"transfer_bytes\":"<<transferred<<",\"device_allocation_bytes\":"<<allocated<<",\"cases\":[";for(size_t i=0;i<cases.size();++i)out<<(i?",":"")<<cases[i];out<<"],\"teardown\":"<<(teardown.empty()?"null":teardown)<<"}\n";out.flush();return bool(out);}catch(...){return false;}};
 try{
  guard();factory_entered=true;auto owner=ownrt::make_sycl_device(card,false);backend=owner.get();d=std::make_unique<Device>(std::move(owner));Fixture fixture(*d,transferred,allocated,submissions);
  for(unsigned type:{12,13,18,23,42})for(unsigned mode=0;mode<3;++mode){guard();cases.push_back(fixture.run(type,mode));transferred=fixture.transfers;allocated=fixture.allocation_bytes;need(report(),"progress receipt failed");}
  guard();backend->synchronize();auto receipt=d->shutdown(std::chrono::seconds(30));teardown=receipt.json();safe=receipt.safe_to_exit;need(safe&&receipt.exit_code==0&&receipt.in_flight==0&&receipt.live_bytes==0,"native owner teardown failed");passed=true;
 }catch(const std::exception&ex){error=ex.what();}catch(...){error="non-standard qualification failure";}
 if(!passed){
  if(!d){safe=!factory_entered;if(!safe){report();ownrt::hold_for_supervisor();}}
  else if(teardown.empty()){
   // Device's event ledger can be empty after a submission exception. A
   // positive synchronization of this exact retained backend is mandatory
   // before generic shutdown/free; report failures cannot bypass retention.
   try{backend->synchronize();}catch(const std::exception&ex){cleanup_error=ex.what();report();ownrt::hold_for_supervisor();}catch(...){cleanup_error="backend synchronization failed";report();ownrt::hold_for_supervisor();}
   try{auto receipt=d->shutdown(std::chrono::seconds(30));teardown=receipt.json();safe=receipt.safe_to_exit;}catch(const std::exception&ex){cleanup_error=ex.what();safe=false;}catch(...){cleanup_error="owner shutdown failed";safe=false;}
  }
 }
 const bool recorded=report();if(!safe)ownrt::hold_for_supervisor();return passed&&recorded?0:1;
}
} // namespace qualification
int main(int argc,char**argv){
 // Default and malformed invocations perform no device construction or query.
 if(argc!=6||std::string(argv[1])!="--run"||std::string(argv[2])!="--card"||std::string(argv[4])!="--output")return 64;
 try{std::string value=argv[3];if(value.empty()||value.find_first_not_of("0123456789")!=std::string::npos)return 64;unsigned long card=std::stoul(value);if(card>3)return 64;struct rlimit limit{};qualification::need(getrlimit(RLIMIT_AS,&limit)==0&&limit.rlim_cur==RLIM_INFINITY,"native runner requires unlimited address space, not compiler4GiB cap");umask(0077);std::signal(SIGTERM,qualification::stop);std::signal(SIGINT,qualification::stop);return qualification::run(unsigned(card),argv[5]);}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}
}
