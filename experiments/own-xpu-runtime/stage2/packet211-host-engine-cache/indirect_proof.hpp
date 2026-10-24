#pragma once
#ifndef OWN_RT_HOST_ONLY
#error P211 numerical adapter proof is HOST_ONLY only
#endif
#include "host_indirect.hpp"
#include <openssl/sha.h>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <map>
#include <vector>
#include <cstring>
#include <memory>
#include <chrono>

namespace p211::proof {
inline void check(bool value,const char* reason){if(!value)throw std::runtime_error(reason);}
inline std::string digest(const std::vector<uint8_t>& bytes){
 unsigned char value[32];SHA256(bytes.data(),bytes.size(),value);std::string out;
 for(auto x:value){out+="0123456789abcdef"[x>>4];out+="0123456789abcdef"[x&15];}return out;
}
inline std::string hex(const std::vector<uint8_t>& bytes){std::string out;for(auto x:bytes){out+="0123456789abcdef"[x>>4];out+="0123456789abcdef"[x&15];}return out;}
template<class F>std::string refusal(F f){try{f();return {};}catch(const std::exception&e){return e.what();}}

struct Fixture {
 static constexpr unsigned rows=4,experts=4,count=10;
 Host* host;ownrt::Device device;bool shared,closed=false;unsigned columns,projections;
 std::vector<ownrt::Allocation> original,pinned,tables,ys,reference_ys,status,reference_status,retained;
 ownrt::Allocation input=0,routes=0,cache=0,decoy=0;
 std::vector<integrated::Matrix> indirect,direct;std::vector<Span> spans;
 std::vector<ownrt::PreparedCompute> commands;uint64_t generation=0;unsigned serial=0;
 explicit Fixture(bool paired):host(new Host),device(std::unique_ptr<ownrt::Backend>(host)),shared(paired),columns(paired?4:8),projections(paired?2:1){
  input=allocate("input",size_t(shared?1:count)*columns*2);
  routes=allocate("routes",count*sizeof(iq3::Route));
  cache=allocate("cache",projections*expert_bytes(),ownrt::Memory::device,ownrt::Category::weights,ownrt::Lifetime::process);
  decoy=allocate("decoy",256);std::memset(pointer(decoy),0x5a,256);
  auto*x=static_cast<uint16_t*>(pointer(input));for(unsigned slot=0;slot<(shared?1:count);++slot)for(unsigned k=0;k<columns;++k)x[slot*columns+k]=iq3::bf16_bits(float(1+k+slot)*0.25f);
  ownrt::CopyEngine copy(device);
  for(unsigned projection=0;projection<projections;++projection){
   original.push_back(allocate("contiguous",experts*expert_bytes(),ownrt::Memory::device,ownrt::Category::weights,ownrt::Lifetime::process));
   pinned.push_back(allocate("pinned",experts*expert_bytes(),ownrt::Memory::pinned,ownrt::Category::weights,ownrt::Lifetime::process));
   tables.push_back(allocate("table",experts*sizeof(p58::Pointer),ownrt::Memory::device,ownrt::Category::weights,ownrt::Lifetime::process));
   ys.push_back(allocate("indirect-output",count*rows*2));reference_ys.push_back(allocate("reference-output",count*rows*2));
   // Oversize status storage makes crossed y/status aliases pass extent checks,
   // so the explicit alias guard, rather than an incidental short buffer, decides.
   status.push_back(allocate("indirect-status",count*rows*2));reference_status.push_back(allocate("reference-status",count*rows*2));
   auto*w=static_cast<float*>(pointer(original.back()));for(unsigned e=0;e<experts;++e)for(unsigned i=0;i<rows*columns;++i)w[e*rows*columns+i]=float(1+e*7+i+projection*19)*0.125f;
   auto event=copy.copy(pinned.back(),0,original.back(),0,experts*expert_bytes(),{});completed(event);
   event=copy.copy(cache,projection*expert_bytes(),original.back(),2*expert_bytes(),expert_bytes(),{});completed(event);
   auto*table=static_cast<p58::Pointer*>(pointer(tables.back()));for(unsigned e=0;e<experts;++e)table[e]={e==2?uint64_t(pointer(cache))+projection*expert_bytes():uint64_t(pointer(pinned.back()))+e*expert_bytes(),1};
   integrated::Matrix m{};m.type=iq3::Type::F32;m.w=tables.back();m.x=input;m.y=ys.back();m.rows=rows;m.columns=columns;m.experts=experts;m.count=count;m.span=rows;m.routes=routes;m.status=status.back();
   indirect.push_back(m);m.w=original.back();m.y=reference_ys.back();m.status=reference_status.back();direct.push_back(m);
   spans.push_back({uint64_t(pointer(pinned.back())),experts*expert_bytes()});
  }
  route_case(false);clear_outputs();generation=device.generation();
  device.before_compute=[this]{admit();};
 }
 ~Fixture(){if(!closed){auto r=device.shutdown(std::chrono::seconds(1));if(!r.safe_to_exit)std::abort();}}
 size_t expert_bytes()const{return rows*columns*sizeof(float);}
 ownrt::Allocation allocate(const std::string&name,size_t bytes,ownrt::Memory memory=ownrt::Memory::device,ownrt::Category category=ownrt::Category::scratch,ownrt::Lifetime life=ownrt::Lifetime::transaction){
  auto id=device.arena.allocate("card0:p211-proof:"+std::to_string(++serial)+":"+name,bytes,memory,category,life);retained.push_back(id);std::memset(pointer(id),0,bytes);return id;
 }
 void*pointer(ownrt::Allocation id){return device.arena.row(id).pointer;}
 std::vector<uint8_t> bytes(ownrt::Allocation id,size_t n=0){const auto&r=device.arena.row(id);if(!n)n=r.bytes;check(n<=r.bytes,"proof read extent");auto*p=static_cast<const uint8_t*>(r.pointer);return {p,p+n};}
 void completed(ownrt::Event event){check(device.wait(event,std::chrono::seconds(1))&&device.complete(event)&&device.in_flight()==0,"proof CPU operation incomplete");device.retire_completed_events();}
 void admit(){check(device.generation()==generation,"proof retained generation changed");for(auto id:retained)check(device.arena.row(id).live,"proof retained storage released");
  for(size_t i=0;i<pinned.size();++i)check(spans[i].begin==uint64_t(pointer(pinned[i]))&&spans[i].bytes==device.arena.row(pinned[i]).bytes,"proof pinned span identity");}
 void route_case(bool invalid){auto*r=static_cast<iq3::Route*>(pointer(routes));for(unsigned slot=0;slot<count;++slot)r[slot]={slot%experts,0,rows};r[0]={0,0,rows};r[1]=invalid?iq3::Route{experts,0,rows}:iq3::Route{2,1,rows-1};r[2]=invalid?iq3::Route{1,rows+1,1}:iq3::Route{3,2,rows-2};}
 void clear_outputs(){for(const auto&v:{ys,reference_ys,status,reference_status})for(auto id:v)std::memset(pointer(id),0xa5,device.arena.row(id).bytes);}
 std::vector<uint8_t> output(){std::vector<uint8_t> out;for(auto id:ys){auto b=bytes(id);out.insert(out.end(),b.begin(),b.end());}return out;}
 void capture(){commands.clear();device.begin_capture(commands);try{indirect_experts(device,indirect,shared,spans,{uint64_t(pointer(cache)),device.arena.row(cache).bytes});device.end_capture();}catch(...){device.end_capture();throw;}check(commands.size()==1,"one captured indirect operator");}
 void issue(){completed(device.issue(commands.at(0)));}
 std::string compare_case(const std::string&name,bool invalid){
  route_case(invalid);clear_outputs();completed(integrated::experts(device,direct,shared).last);issue();
  std::ostringstream out;out<<"{\"name\":"<<ownrt::quote(name)<<",\"passed\":true,\"shared\":"<<(shared?"true":"false")<<",\"rows\":"<<rows<<",\"columns\":"<<columns<<",\"experts\":"<<experts<<",\"count\":"<<count<<",\"variant\":2,\"captured_operations\":1,\"outputs\":[";
  for(unsigned i=0;i<projections;++i){auto a=bytes(reference_ys[i]),b=bytes(ys[i]),sa=bytes(reference_status[i],count*4),sb=bytes(status[i],count*4);check(a==b&&sa==sb,"original contiguous/indirect bytes differ");
   const auto*flags=static_cast<const uint32_t*>(pointer(status[i]));check(flags[0]==0&&flags[1]==unsigned(invalid)&&flags[2]==unsigned(invalid),"route status authority");
   for(unsigned slot=3;slot<count;++slot)check(flags[slot]==0,"remaining top10 route status");
   if(i)out<<',';out<<"{\"bytes\":"<<a.size()<<",\"contiguous_sha256\":"<<ownrt::quote(digest(a))<<",\"indirect_sha256\":"<<ownrt::quote(digest(b))<<",\"output_hex\":"<<ownrt::quote(hex(b))<<",\"status_hex\":"<<ownrt::quote(hex(sb))<<",\"status_sha256\":"<<ownrt::quote(digest(sb))<<"}";
  }out<<"]}";return out.str();
 }
 ownrt::Receipt close(){device.before_compute={};auto r=device.shutdown(std::chrono::seconds(1));check(r.safe_to_exit&&r.in_flight==0&&r.live_bytes==0,"proof safe CPU teardown");closed=true;return r;}
};
} // namespace p211::proof

namespace p211 {
inline int indirect_proof(const std::filesystem::path& output){
 using namespace proof;std::map<std::string,bool> checks;std::map<std::string,std::string> owners,hashes,errors;std::vector<std::string> cases;std::string fatal;
 check(!std::filesystem::exists(output)&&!std::filesystem::is_symlink(output),"preserve indirect proof output");std::filesystem::create_directories(output);
 try{
  for(bool shared:{true,false}){
   Fixture f(shared);auto untouched=f.output();f.capture();checks[shared?"gate_capture_no_execution":"down_capture_no_execution"]=f.output()==untouched&&f.device.in_flight()==0;
   // Destroy/rebind the actual caller values after capture; captured operator
   // arguments and owned metadata must continue to select the original IDs.
   auto arguments=f.commands[0].argument_bytes;auto saved=f.indirect;f.indirect.assign(1,integrated::Matrix{});
   cases.push_back(f.compare_case(shared?"gate_up_valid":"down_valid",false));
   cases.push_back(f.compare_case(shared?"gate_up_invalid":"down_invalid",true));
   checks[shared?"gate_caller_metadata_immutable":"down_caller_metadata_immutable"]=f.commands[0].argument_bytes==arguments&&f.bytes(f.decoy)==std::vector<uint8_t>(256,0x5a);f.indirect=saved;
   f.route_case(false);f.clear_outputs();f.issue();auto reference=f.output();
   auto cache_before=f.bytes(f.cache);std::memset(f.pointer(f.cache),0,f.expert_bytes());f.issue();auto mutated=f.output();
   checks[shared?"gate_cache_payload_consumed":"down_cache_payload_consumed"]=mutated!=reference;hashes[shared?"gate_cache_mutated":"down_cache_mutated"]=digest(mutated);hashes[shared?"gate_reference":"down_reference"]=digest(reference);
   std::memcpy(f.pointer(f.cache),cache_before.data(),cache_before.size());f.issue();check(f.output()==reference,"restored cache bytes not exact");
   auto pin_before=f.bytes(f.pinned[0]);std::memset(f.pointer(f.pinned[0]),0,f.expert_bytes());f.issue();checks[shared?"gate_pinned_payload_consumed":"down_pinned_payload_consumed"]=f.output()!=reference;
   std::memcpy(f.pointer(f.pinned[0]),pin_before.data(),pin_before.size());f.issue();check(f.output()==reference,"restored pinned bytes not exact");owners[shared?"gate_up":"down"]=f.close().json();
  }
  for(unsigned kind=0;kind<4;++kind){Fixture f(true);f.capture();auto before=f.output();auto*table=static_cast<p58::Pointer*>(f.pointer(f.tables[0]));unsigned expert=kind==3?2:0;
   if(kind==0||kind==3){uint64_t end=uint64_t(f.pointer(f.cache))+f.device.arena.row(f.cache).bytes;for(const auto&s:f.spans)end=std::max(end,s.begin+s.bytes);table[expert].address=end+16;}
   if(kind==1)++table[expert].address;if(kind==2)table[expert].generation=0;
   std::string name=kind==0?"outside_first":kind==1?"misaligned_first":kind==2?"zero_generation_first":"outside_later";
   errors[name]=refusal([&]{f.issue();});check(errors[name]=="p211 indirect payload outside retained owned span","expected pointer refusal");
   checks[name+"_output_scope"]=kind==3?f.output()!=before:f.output()==before;
   checks[name+"_sticky_owner"]=!refusal([&]{f.issue();}).empty();auto r=f.close();checks[name+"_failed_drained"]=r.exit_code==1&&r.status=="failed-drained";owners[name]=r.json();
  }
  {
   Fixture f(true);auto valid=f.indirect;auto before=f.output();
   auto test=[&](const std::string&name,auto mutate){f.indirect=valid;mutate();auto error=refusal([&]{f.capture();});checks[name]=!error.empty()&&f.output()==before&&f.device.in_flight()==0;errors[name]=error;};
   test("cross_y_status_alias_refused",[&]{f.indirect[0].y=f.indirect[1].status;});
   test("cross_status_y_alias_refused",[&]{f.indirect[0].status=f.indirect[1].y;});
   test("writable_input_alias_refused",[&]{f.indirect[0].y=f.input;});
   test("tuple_shape_refused",[&]{++f.indirect[1].columns;});
   auto short_table=f.allocate("short-table",sizeof(p58::Pointer));test("short_table_extent_refused",[&]{f.indirect[0].w=short_table;});
   owners["binding_refusals"]=f.close().json();
  }
  for(bool pinned:{true,false}){Fixture f(true);f.capture();auto before=f.output();f.device.arena.release(pinned?f.pinned[0]:f.cache);auto error=refusal([&]{f.issue();});auto name=pinned?"released_pinned":"released_cache";checks[std::string(name)+"_capture_refused"]=!error.empty()&&f.output()==before;errors[name]=error;owners[name]=f.close().json();}
 }catch(const std::exception&e){fatal=e.what();}
 bool passed=fatal.empty()&&!checks.empty();for(auto&[name,value]:checks)passed&=value;
 std::ofstream out(output/"indirect-proof.json");check(bool(out),"indirect proof receipt open");
 out<<"{\"schema\":\"packet211.indirect-proof.v1\",\"passed\":"<<(passed?"true":"false")<<",\"device_executed\":false,\"model_executed\":false,\"completion_scope\":\"actual CPU arithmetic and bytes, inherited simulated Host events\",\"error\":"<<ownrt::quote(fatal)<<",\"cases\":[";
 for(size_t i=0;i<cases.size();++i)out<<(i?",":"")<<cases[i];out<<"],\"checks\":{";bool first=true;for(auto&[name,value]:checks){out<<(first?"":",")<<ownrt::quote(name)<<":"<<(value?"true":"false");first=false;}
 out<<"},\"byte_sha256\":{";first=true;for(auto&[name,value]:hashes){out<<(first?"":",")<<ownrt::quote(name)<<":"<<ownrt::quote(value);first=false;}
 out<<"},\"errors\":{";first=true;for(auto&[name,value]:errors){out<<(first?"":",")<<ownrt::quote(name)<<":"<<ownrt::quote(value);first=false;}
 out<<"},\"owner_receipts\":{";first=true;for(auto&[name,value]:owners){out<<(first?"":",")<<ownrt::quote(name)<<":"<<value;first=false;}out<<"}}\n";out.flush();check(bool(out),"indirect proof receipt write");return passed?0:1;
}
} // namespace p211
