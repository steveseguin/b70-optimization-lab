#include "kernels.hpp"
#include <filesystem>
#include <fstream>
#include <iostream>
#include <cstring>
#include <csignal>
#include <map>
#ifndef HOST_ONLY
#include "native.hpp"
#endif
namespace fs=std::filesystem;
volatile std::sig_atomic_t stopping=0;
void stop(int){stopping=1;}
void require(bool ok,const char* msg){if(!ok)throw std::runtime_error(msg);}
struct Fixture {
 ng::Shape s;std::array<std::vector<uint8_t>,16> data,expected;std::array<int32_t,16> outputs{};
 explicit Fixture(const fs::path& path){std::ifstream f(path,std::ios::binary);require(bool(f),"fixture open");f.read(reinterpret_cast<char*>(&s),sizeof(s));ng::validate(s);
  for(int j=0;j<16;++j){uint32_t n,out;f.read(reinterpret_cast<char*>(&n),4);f.read(reinterpret_cast<char*>(&out),4);require(n>0&&n<128*1024*1024,"fixture size");data[j].resize(n);outputs[j]=out;f.read(reinterpret_cast<char*>(data[j].data()),n);if(out){expected[j].resize(n);f.read(reinterpret_cast<char*>(expected[j].data()),n);}}
  require(bool(f)&&f.peek()==EOF,"fixture truncated or trailing bytes");auto sizes=ng::required_bytes(s);for(int j=0;j<16;++j)require(data[j].size()>=sizes[j],"short fixture binding");}
 ng::Args args(){ng::Args a;for(int j=0;j<16;++j)a.p[j]=data[j].data();return a;}
 size_t compare()const{size_t n=0;for(int j=0;j<16;++j)if(outputs[j]){if(data[j]!=expected[j]){size_t mismatch=0,first=0;for(size_t k=0;k<data[j].size();++k)if(data[j][k]!=expected[j][k]){if(!mismatch)first=k;++mismatch;}throw std::runtime_error("slot "+std::to_string(j)+" mismatch bytes="+std::to_string(mismatch)+" first="+std::to_string(first));}n+=data[j].size();}return n;}
};
int main(int argc,char**argv){
 std::signal(SIGINT,stop);std::signal(SIGTERM,stop);
#ifdef HOST_ONLY
 if(argc!=3)return 2;
 size_t checks=0,bytes=0;std::string error;
 try{std::ifstream list(fs::path(argv[1])/"cases.txt");std::string name;require(bool(list),"case list open");while(list>>name){Fixture f(fs::path(argv[1])/name);auto a=f.args();if(f.s.op==ng::attention_score){for(int op=ng::attention_score;op<=ng::attention_value;++op){auto s=f.s;s.op=op;ng::cpu(s,a);}}else ng::cpu(f.s,a);
  ++checks;try{bytes+=f.compare();}catch(const std::exception& e){std::cerr<<name<<": "<<e.what()<<'\n';error+="failed "+name+"; ";}
 }
  require(checks>0,"empty fixture coverage");
 }catch(const std::exception&e){error=e.what();}
 std::ofstream out(argv[2]);out<<"{\"checks\":"<<checks<<",\"compared_bytes\":"<<bytes<<",\"passed\":"<<(error.empty()?"true":"false")<<",\"error\":\""<<error<<"\",\"device_executed\":false}\n";
 return !error.empty();
#else
 if(argc!=6||std::string(argv[1])!="--authorized-device-window"||std::string(argv[2])!="3")return 2;
 std::string mode=argv[5];if(mode!="exactness"&&mode!="timing")return 2;
 std::unique_ptr<ownrt::Device>d;ownrt::Receipt teardown;std::string error;size_t checks=0,bytes=0;
 std::ofstream timings(fs::path(argv[4])/"timings.jsonl");if(!timings)return 2;
 try{
  d=std::make_unique<ownrt::Device>(ownrt::make_sycl_device(3,true));ownrt::CopyEngine copies(*d);
  auto wait=[&](ownrt::Event e){require(d->wait(e,std::chrono::seconds(30)),"device event deadline");};
  struct Pending {ng::Shape shape;std::array<ownrt::Allocation,16> ids,host;std::array<size_t,16> sizes;};
  std::map<std::string,Pending> pending;
  std::ifstream list(fs::path(argv[3])/"cases.txt");std::string name;require(bool(list),"case list open");
  while(list>>name){require(!stopping,"cooperative stop");Fixture f(fs::path(argv[3])/name);std::array<ownrt::Allocation,16>ids,host;
   for(int j=0;j<16;++j){size_t n=f.data[j].size();ids[j]=d->arena.allocate(name+"/device"+std::to_string(j),n,ownrt::Memory::device,ownrt::Category::scratch,ownrt::Lifetime::transaction);host[j]=d->arena.allocate(name+"/host"+std::to_string(j),n,ownrt::Memory::pinned,ownrt::Category::pinned_slab,ownrt::Lifetime::transfer);std::memcpy(d->arena.row(host[j]).pointer,f.data[j].data(),n);wait(copies.copy(ids[j],0,host[j],0,n,{}));}
   for(int repeat=0;repeat<(mode=="timing"?6:2);++repeat){
    // Restore all state outside the timed chain; no cached outputs or state reuse.
    if(repeat)for(int j=0;j<16;++j)wait(copies.copy(ids[j],0,host[j],0,f.data[j].size(),{}));
    require(!stopping,"cooperative stop");std::vector<ownrt::Event> events;
    int end=f.s.op==ng::attention_score?ng::attention_value:f.s.op;
    auto wall=std::chrono::steady_clock::now();
    for(int op=f.s.op;op<=end;++op){auto s=f.s;s.op=op;std::vector<ownrt::Event>deps;if(!events.empty())deps.push_back(events.back());events.push_back(ng::submit(*d,s,ids,deps));}
    wait(events.back());double device_ms=0;for(auto e:events){auto v=d->timing(e);device_ms+=(v.end_ns-v.start_ns)/1e6;}
    double wall_ms=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-wall).count();
    timings<<"{\"case\":"<<ownrt::quote(name)<<",\"op\":"<<f.s.op<<",\"M\":"<<f.s.tokens<<",\"repeat\":"<<repeat<<",\"kernel_submissions\":"<<events.size()<<",\"non_gemv_device_ms\":"<<device_ms<<",\"wall_ms\":"<<wall_ms<<"}\n";
    // Read back into separate temporary slabs; original pinned inputs remain intact.
    for(int j=0;j<16;++j)if(f.outputs[j]){auto read=d->arena.allocate("readback",f.data[j].size(),ownrt::Memory::pinned,ownrt::Category::pinned_slab,ownrt::Lifetime::transfer);wait(copies.copy(read,0,ids[j],0,f.data[j].size(),{}));std::memcpy(f.data[j].data(),d->arena.row(read).pointer,f.data[j].size());d->arena.release(read);}
    bytes+=f.compare();++checks;d->retire_completed_events();
   }
   if(mode=="timing") {Pending job{f.s,ids,host,{}};for(int j=0;j<16;++j)job.sizes[j]=f.data[j].size();pending.emplace(name,std::move(job));}
   else{for(auto id:ids)d->arena.release(id);for(auto id:host)d->arena.release(id);}
  }
  require(checks>0,"empty fixture coverage");
  if(mode=="timing") for(int M:{1,87})for(const std::string kind:{"gdn","qsa"}) {
   // Projection inputs are independent fixture tensors. This is an actual queued
   // non-GEMV census, not an integrated layer or an extrapolated sum of timings.
   std::vector<std::string> names={"norm","hc-act","mix"};
   if(kind=="gdn")names.insert(names.end(),{"conv-10240","gdn","gdn-gated"});
   else names.insert(names.end(),{"qsa-prepare","qsa-pool","qsa-select","qsa-attention"});
   names.insert(names.end(),{"combine-norm","hc-act","mix","route-gather","ffn-routed-act","ffn-act","moe-combine","combine-norm"});
   for(int repeat=0;repeat<6;++repeat){
    require(!stopping,"cooperative stop before chain");
    for(const auto& label:names){auto& job=pending.at(label+"-"+std::to_string(M)+".fixture");for(int j=0;j<16;++j)wait(copies.copy(job.ids[j],0,job.host[j],0,job.sizes[j],{}));}
    d->retire_completed_events();std::vector<ownrt::Event>events;auto wall=std::chrono::steady_clock::now();
    for(const auto& label:names){auto& job=pending.at(label+"-"+std::to_string(M)+".fixture");int end=job.shape.op==ng::attention_score?ng::attention_value:job.shape.op;
     for(int op=job.shape.op;op<=end;++op){auto shape=job.shape;shape.op=op;std::vector<ownrt::Event>deps;if(!events.empty())deps.push_back(events.back());events.push_back(ng::submit(*d,shape,job.ids,deps));}}
    wait(events.back());double device_ms=0;for(auto e:events){auto v=d->timing(e);device_ms+=(v.end_ns-v.start_ns)/1e6;}
    double wall_ms=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-wall).count();
    timings<<"{\"kind\":\"layer_census\",\"layer_type\":"<<ownrt::quote(kind)<<",\"M\":"<<M<<",\"repeat\":"<<repeat<<",\"kernel_submissions\":"<<events.size()<<",\"non_gemv_device_ms\":"<<device_ms<<",\"wall_ms\":"<<wall_ms<<"}\n";
    d->retire_completed_events();
   }
  }
  for(auto& [name,job]:pending){for(auto id:job.ids)d->arena.release(id);for(auto id:job.host)d->arena.release(id);}
 }catch(const std::exception&e){error=e.what();}
 if(d){std::ofstream census(fs::path(argv[4])/"census.json");census<<d->arena.census()<<'\n';teardown=d->shutdown(std::chrono::seconds(10));}
 std::ofstream out(fs::path(argv[4])/"device.json");out<<"{\"checks\":"<<checks<<",\"compared_bytes\":"<<bytes<<",\"error\":"<<ownrt::quote(error)<<",\"teardown\":"<<teardown.json()<<"}\n";out.close();
 if(d&&!teardown.safe_to_exit)ownrt::hold_for_supervisor();return !error.empty()||!teardown.safe_to_exit;
#endif
}
