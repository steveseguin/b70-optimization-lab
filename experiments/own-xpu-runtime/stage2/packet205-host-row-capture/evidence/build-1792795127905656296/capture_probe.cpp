#include "host_backend.hpp"
#include <openssl/sha.h>
#include <array>
#include <iostream>
#include <map>
#include <sstream>
using namespace ownrt;
using namespace integrated;
namespace {
void need(bool v,const char*s){if(!v)throw std::runtime_error(s);}
template<class F> bool refused(F f){try{f();return false;}catch(const std::exception&){return true;}}
std::string digest(const std::vector<unsigned char>& b){unsigned char d[32];SHA256(b.data(),b.size(),d);std::string s;for(auto x:d){s+="0123456789abcdef"[x>>4];s+="0123456789abcdef"[x&15];}return s;}
struct Row {Allocation token,position,input,streams,ids;};
struct Fixture {
 Host* host;
 Device d;
 bool closed=false,halted=false;int completed_rows=0;
 std::array<Row,2> rows;
 Allocation history,conv_history,conv_output,weight,inject,metadata,scratch,error,active,rope,control,dummy;
 Allocation canonical_streams,canonical_token,canonical_position,canonical_history;
 std::array<std::vector<PreparedCompute>,2> commands;
 std::vector<Event> events;
 std::map<std::string,Allocation> mutable_map;
 std::vector<std::string> publication_order;
 Fixture():host(new Host),d(std::unique_ptr<Backend>(host)) {
  history=alloc("token-history",16);conv_history=alloc("conv-history",24);conv_output=alloc("conv-output",8);
  weight=alloc("synthetic-weight",64);inject=alloc("synthetic-inject",8);metadata=alloc("metadata",280);
  scratch=alloc("scratch",65536);error=alloc("error",4);active=alloc("active",4);rope=alloc("rope-unused",32768*128);control=alloc("control",12);dummy=alloc("dummy",4);
  canonical_streams=alloc("canonical-streams",32);canonical_token=alloc("canonical-token",4);canonical_position=alloc("canonical-position",4);canonical_history=alloc("canonical-history",16);
  for(int i=0;i<2;++i)rows[i]={alloc("token"+std::to_string(i),4),alloc("position"+std::to_string(i),4),alloc("input"+std::to_string(i),8),alloc("streams"+std::to_string(i),32),alloc("ids"+std::to_string(i),128)};
  for(int i=0;i<2;++i){auto pre="row"+std::to_string(i)+".";auto&r=rows[i];mutable_map[pre+"token"]=r.token;mutable_map[pre+"position"]=r.position;mutable_map[pre+"input"]=r.input;mutable_map[pre+"streams"]=r.streams;mutable_map[pre+"ids"]=r.ids;}
  mutable_map["history"]=history;mutable_map["conv_history"]=conv_history;
  reset();
 }
 ~Fixture(){if(!closed){auto r=d.shutdown(std::chrono::milliseconds(100));if(!r.safe_to_exit)std::abort();}}
 Allocation alloc(std::string n,size_t bytes){auto id=d.arena.allocate("card0:"+n,bytes,Memory::device,Category::scratch,Lifetime::transaction);std::memset(d.arena.row(id).pointer,0,bytes);return id;}
 template<class T>T* ptr(Allocation a){return static_cast<T*>(d.arena.row(a).pointer);}
 std::vector<unsigned char> bytes(Allocation a){auto&r=d.arena.row(a);auto*p=static_cast<unsigned char*>(r.pointer);return {p,p+r.bytes};}
 void reset(){
  need(d.in_flight()==0,"reset while work pending");d.retire_completed_events();events.clear();halted=false;completed_rows=0;
  *ptr<uint32_t>(error)=0;*ptr<uint32_t>(active)=1;
  ptr<int64_t>(history)[0]=1;ptr<int64_t>(history)[1]=2;
  for(int i=0;i<12;++i)ptr<uint16_t>(conv_history)[i]=iq3::bf16_bits(float(i+1)/64);
  for(int i=0;i<16;++i)ptr<float>(weight)[i]=float((i%4)+1)/16;
  for(int i=0;i<4;++i)ptr<uint16_t>(inject)[i]=iq3::bf16_bits(float(i-2)/4);
  auto*m=ptr<int64_t>(metadata);m[0]=11;m[1]=17;m[2]=23;for(int i=0;i<16;++i){m[3+i]=97+2*i;m[19+i]=1000*i;}
  for(int r=0;r<2;++r){*ptr<int32_t>(rows[r].token)=3+r;*ptr<uint32_t>(rows[r].position)=3+r;
   for(int i=0;i<4;++i)ptr<uint16_t>(rows[r].input)[i]=iq3::bf16_bits(float((r+1)*(i+1))/8);
   for(int i=0;i<16;++i)ptr<uint16_t>(rows[r].streams)[i]=iq3::bf16_bits(float(i+r*5)/32);
  }
  for(auto id:{canonical_streams,canonical_token,canonical_position,canonical_history})std::memset(d.arena.row(id).pointer,0xa5,d.arena.row(id).bytes);
 }
 Spec spec(Special special=Special::normal){Spec s{};s.g.h=4;s.g.context=16;s.g.budget=4;s.g.eos=15;s.special=special;return s;}
 Launch submit(Spec s,std::vector<Allocation> b,const Row& r){b.insert(b.end(),{scratch,error,r.position,active,rope});auto result=packet18::submit_parallel(d,s,b,control,dummy,dummy,{});
  // Locals are deliberately mutated before destruction, after capture.
  s.g.context=0;s.ni=19;std::fill(b.begin(),b.end(),dummy);return result;}
 void sequence(int row){auto pre="row"+std::to_string(row)+".";Row r{mutable_map.at(pre+"token"),mutable_map.at(pre+"position"),mutable_map.at(pre+"input"),mutable_map.at(pre+"streams"),mutable_map.at(pre+"ids")};
  // Real captured copy makes reuse of shared payload bytes observable. This
  // is distinct from an adapter scratch argument that HOST kernels may ignore.
  CopyEngine copy(d);copy.copy(scratch,0,r.input,0,8,{});
  submit(spec(Special::begin),{},r);
  auto hash=spec(Special::ple_hash);hash.ni=3;hash.no=1;
  hash.sizes[0]=1;hash.types[0]=flash::Scalar::i32;hash.sizes[1]=2;hash.types[1]=flash::Scalar::i64;hash.sizes[2]=35;hash.types[2]=flash::Scalar::i64;hash.sizes[3]=16;hash.types[3]=flash::Scalar::i64;
  submit(hash,{r.token,mutable_map.at("history"),metadata,r.ids},r);
  auto conv=spec();conv.op=Op::conv;conv.ni=2;conv.no=2;conv.nw=1;conv.site.shape[0]=4;conv.site.parameter=1;
  conv.sizes[0]=4;conv.sizes[1]=12;conv.sizes[2]=4;conv.sizes[3]=12;conv.grids[0]=iq3::Type::F32;conv.weight_elements[0]=16;
  submit(conv,{scratch,mutable_map.at("conv_history"),conv_output,mutable_map.at("conv_history"),weight},r);
  auto combine=spec();combine.op=Op::hc_combine;combine.ni=3;combine.no=1;combine.site.shape[0]=4;combine.site.shape[1]=4;
  combine.sizes[0]=16;combine.sizes[1]=4;combine.sizes[2]=4;combine.sizes[3]=16;
  submit(combine,{r.streams,conv_output,inject,r.streams},r);
  submit(spec(Special::commit),{},r);
 }
 void capture(){for(int r=0;r<2;++r){d.begin_capture(commands[r]);try{sequence(r);d.end_capture();}catch(...){d.end_capture();throw;}need(commands[r].size()==6,"six host commands per row");}}
 void issue(int row){need(!halted && row==completed_rows,"chunk intake/order halted");try{for(auto&cmd:commands.at(row))events.push_back(d.issue(cmd));++completed_rows;}catch(...){halted=true;throw;}}
 void finish(){for(auto e:events)need(d.wait(e,std::chrono::milliseconds(100)) && d.complete(e),"host event incomplete");need(d.in_flight()==0,"host still pending");}
 void publish(bool inject_bad_second_extent=false){need(!halted && completed_rows==2 && !*ptr<uint32_t>(error),"failed/partial chunk publication");try{finish();publication_order.push_back("all-host-events-complete");
  d.retire_completed_events();events.clear();CopyEngine copy(d);
  for(auto [dst,src]:std::array<std::pair<Allocation,Allocation>,4>{{{canonical_streams,rows[1].streams},{canonical_token,rows[1].token},{canonical_position,rows[1].position},{canonical_history,history}}}){
   auto bytes=d.arena.row(dst).bytes;if(inject_bad_second_extent && dst==canonical_token)++bytes;
   events.push_back(copy.copy(dst,0,src,0,bytes,{}));
  }
  finish();publication_order.push_back("canonical-copies-complete");
  }catch(...){halted=true;throw;}
 }
 Receipt close(){auto r=d.shutdown(std::chrono::milliseconds(100));need(r.safe_to_exit,"CPU owner retained");closed=true;return r;}
 std::vector<unsigned char> result(){std::vector<unsigned char> out;for(auto id:{rows[0].streams,rows[1].streams,history,conv_history,rows[0].ids,rows[1].ids,rows[0].position,rows[1].position}){auto b=bytes(id);out.insert(out.end(),b.begin(),b.end());}return out;}
 std::vector<unsigned char> canonical(){std::vector<unsigned char> out;for(auto id:{canonical_streams,canonical_token,canonical_position,canonical_history}){auto b=bytes(id);out.insert(out.end(),b.begin(),b.end());}return out;}
};
struct InjectedFailure final:HostOperation {void run(std::span<void*const>)const override{throw std::runtime_error("intentional host operation failure");}};
}
int main(){try{
 std::map<std::string,bool> checks;std::map<std::string,std::string> hashes,receipts;std::string fault_status;
 {
  Fixture reference;reference.sequence(0);reference.sequence(1);need(reference.d.in_flight()==0,"eager host incomplete");auto expected=reference.result();hashes["eager"]=digest(expected);need(reference.close().exit_code==0,"eager close");
  Fixture f;auto initial=f.result();auto initial_history=f.bytes(f.conv_history);auto canonical=f.canonical();f.capture();
  checks["capture_does_not_execute"]=f.result()==initial && f.d.in_flight()==0;
  auto args0=f.commands[0][1].argument_bytes,args1=f.commands[1][1].argument_bytes;
  checks["fixed_row_position_pointers_distinct"]=args0!=args1 && f.commands[0][1].pointers[2]==f.d.arena.row(f.rows[0].position).pointer && f.commands[1][1].pointers[2]==f.d.arena.row(f.rows[1].position).pointer;
  checks["shared_history_bindings_retained"]=f.commands[0][2].ids[1]==f.history && f.commands[1][2].ids[1]==f.history;
  checks["shared_scratch_captured_consumer"]=f.commands[0][3].ids[0]==f.scratch && f.commands[1][3].ids[0]==f.scratch;
  std::vector<Allocation> decoys;for(auto&[name,id]:f.mutable_map){auto replacement=f.alloc("decoy-"+name,f.d.arena.row(id).bytes);std::memset(f.d.arena.row(replacement).pointer,0x5a,f.d.arena.row(replacement).bytes);id=replacement;decoys.push_back(replacement);}
  f.issue(0);checks["canonical_untouched_after_row0"]=f.canonical()==canonical;
  checks["partial_rows_publication_refused"]=refused([&]{f.publish();});
  checks["row0_position_capture"]=*f.ptr<uint32_t>(f.rows[0].position)==4 && *f.ptr<uint32_t>(f.rows[1].position)==4;
  f.issue(1);f.finish();auto actual=f.result();auto valid_row1=f.bytes(f.rows[1].streams);hashes["captured"]=digest(actual);hashes["valid_row1_streams"]=digest(valid_row1);
  checks["captured_matches_eager_bytes"]=actual==expected;
  bool decoys_unchanged=true;for(auto id:decoys)for(auto value:f.bytes(id))decoys_unchanged&=value==0x5a;
  checks["caller_metadata_mutation_does_not_rebind"]=actual==expected && decoys_unchanged && f.commands[0][1].argument_bytes==args0 && f.commands[1][1].argument_bytes==args1;
  checks["state_and_rows_nonvacuous"]=actual!=initial && f.bytes(f.conv_history)!=initial_history && f.bytes(f.rows[0].streams)!=f.bytes(f.rows[1].streams);
  checks["canonical_untouched_before_publication"]=f.canonical()==canonical;
  f.publish();checks["canonical_copy_exact"]=f.bytes(f.canonical_streams)==f.bytes(f.rows[1].streams) && *f.ptr<uint32_t>(f.canonical_position)==5 && *f.ptr<int32_t>(f.canonical_token)==4 && f.bytes(f.canonical_history)==f.bytes(f.history);
  checks["canonical_copy_after_completion"]=f.publication_order==std::vector<std::string>{"all-host-events-complete","canonical-copies-complete"};
  f.reset();f.ptr<uint16_t>(f.rows[1].input)[0]=iq3::bf16_bits(3.f);f.issue(0);f.issue(1);f.finish();
  hashes["changed_live_input"]=digest(f.result());hashes["changed_live_input_row1_streams"]=digest(f.bytes(f.rows[1].streams));checks["in_place_input_remains_live"]=f.bytes(f.rows[1].streams)!=valid_row1;
  f.reset();f.issue(0);std::memset(f.d.arena.row(f.conv_history).pointer,0,24);f.issue(1);f.finish();
  hashes["wrong_shared_history"]=digest(f.result());hashes["wrong_history_row1_streams"]=digest(f.bytes(f.rows[1].streams));checks["wrong_shared_history_differs"]=f.bytes(f.rows[1].streams)!=valid_row1;
  f.reset();f.issue(0);std::memcpy(f.d.arena.row(f.rows[1].input).pointer,f.d.arena.row(f.rows[0].input).pointer,8);f.issue(1);f.finish();
  hashes["wrong_row_payload"]=digest(f.result());hashes["wrong_payload_row1_streams"]=digest(f.bytes(f.rows[1].streams));checks["wrong_row_payload_differs"]=f.bytes(f.rows[1].streams)!=valid_row1;
  auto normal=f.close();checks["normal_teardown_success"]=normal.exit_code==0;receipts["normal"]=normal.json();
 }
 {
  Fixture f;f.capture();auto generation=f.d.generation();auto temporary=f.alloc("unrelated",32);
  checks["allocate_preserves_generation"]=f.d.generation()==generation;f.d.arena.release(temporary);
  checks["unrelated_release_invalidates_captures"]=f.d.generation()!=generation && refused([&]{f.issue(0);});need(f.close().exit_code==0,"stale capture cleanup");
 }
 {
  Fixture f;f.capture();f.d.invalidate_prepared();checks["explicit_invalidation_refuses"]=refused([&]{f.issue(0);});need(f.close().exit_code==0,"invalidation cleanup");
 }
 {
  Fixture f;f.capture();auto original=f.canonical();f.host->auto_marker=false;f.issue(0);f.issue(1);
  checks["pending_release_refused"]=refused([&]{f.d.arena.release(f.rows[0].streams);});
  checks["pending_invalidate_refused"]=refused([&]{f.d.invalidate_prepared();});
  checks["pending_publication_refused"]=refused([&]{f.publish();}) && f.canonical()==original;
  f.host->finish_all();f.host->auto_marker=true;f.finish();need(f.close().exit_code==0,"pending fixture cleanup");
 }
 {
  Fixture f;f.capture();auto original=f.canonical();f.issue(0);f.finish();
  f.d.before_compute=[] {throw std::runtime_error("intentional chunk guard refusal");};
  std::string guard_error;try{f.issue(1);}catch(const std::exception&e){guard_error=e.what();}
  checks["guard_refusal_before_row1"]=guard_error=="intentional chunk guard refusal";f.d.before_compute={};
  checks["partial_guard_refuses_publication"]=f.halted && refused([&]{f.publish();}) && f.canonical()==original;
  checks["guard_refusal_sticky_no_retry"]=refused([&]{f.issue(1);});
  auto guard=f.close();checks["guard_refusal_owner_clean"]=guard.exit_code==0;receipts["guard_refusal"]=guard.json();
 }
 {
  Fixture f;f.capture();auto old_token=f.bytes(f.canonical_token);f.issue(0);f.issue(1);f.finish();
  std::string copy_error;try{f.publish(true);}catch(const std::exception&e){copy_error=e.what();}
  checks["publication_copy_refusal_poisons"]=copy_error=="copy extent/lifetime" && f.halted && refused([&]{f.publish();});
  checks["publication_failure_is_partial_not_rollback"]=f.bytes(f.canonical_streams)==f.bytes(f.rows[1].streams) && f.bytes(f.canonical_token)==old_token && f.publication_order==std::vector<std::string>{"all-host-events-complete"};
  auto r=f.close();checks["publication_refusal_owner_can_drain"]=r.exit_code==0;receipts["publication_refusal"]=r.json();
 }
 {
  Fixture f;std::vector<PreparedCompute> commands;f.d.begin_capture(commands);InjectedFailure op;std::array<Allocation,1> ids{f.dummy};f.d.compute(op,ids,{});f.d.end_capture();
  std::string error;try{f.d.issue(commands[0]);}catch(const std::exception&e){error=e.what();}
  checks["backend_failure_original_error"]=error=="intentional host operation failure";
  checks["backend_failure_halts_owner"]=refused([&]{f.d.issue(commands[0]);});
  auto r=f.close();fault_status=r.status;checks["backend_failure_never_normal_success"]=r.safe_to_exit && r.exit_code!=0 && r.status=="failed-drained";receipts["backend_failure"]=r.json();
 }
 bool passed=true;for(auto&[name,value]:checks)passed&=value;
  std::cout<<"{\"passed\":"<<(passed?"true":"false")<<",\"device_executed\":false,\"model_executed\":false,\"backend\":\"unchanged p198 Host / existing LifetimeMock / MockDevice\",\"completion_scope\":\"synchronous CPU operation execution plus simulated backend markers\",\"checks\":{";bool first=true;
 for(auto&[name,value]:checks){std::cout<<(first?"":",")<<'"'<<name<<"\":"<<(value?"true":"false");first=false;}
 std::cout<<"},\"byte_sha256\":{";first=true;for(auto&[name,value]:hashes){std::cout<<(first?"":",")<<'"'<<name<<"\":\""<<value<<'"';first=false;}
 std::cout<<"},\"backend_failure_status\":\""<<fault_status<<"\",\"owner_receipts\":{";first=true;
 for(auto&[name,value]:receipts){std::cout<<(first?"":",")<<'"'<<name<<"\":"<<value;first=false;}
 std::cout<<"}}\n";return passed?0:1;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 2;}}
