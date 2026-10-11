// Reuse the packet's actual-adapter owner, buffer, and Core fixture machinery.
// The renamed legacy entry is not called; all helper names have internal linkage.
#define adapter_fixture_gate packet24_route_fixture_legacy_entry
#include "adapter_fixture.cpp"
#undef adapter_fixture_gate
#include "route_fixture.hpp"
#include "selection.hpp"
unsigned route_fixture_gate(unsigned card,const std::filesystem::path& output){
 std::filesystem::create_directories(output);Runner runner(card);unsigned checks=0;int saved=packet24::kernel_version;
 try{runner.initialize();std::vector<float> scratch(64ull*1024*1024);std::ofstream bytes(output/"route-output.bin",std::ios::binary);
 for(int n:{1,3,17,255,512})for(int mode=0;mode<3;++mode){
  Case c;c.g.experts=n;c.g.top=std::min(n,10);int top=c.g.top;
  int logits=c.add(n),ids=c.add(top,Scalar::i32,0,0),prob=c.add(top,Scalar::f32,0,0),gate=c.add(top*3,Scalar::i32,0,0),down=c.add(top*3,Scalar::i32,0,0);
  if(mode==1){View v{c.buffers[logits].data.data(),size_t(n),Scalar::bf16};for(int j=0;j<n;++j)v.put(j,0.f);}
  if(mode==2){uint16_t nan=0x7fc0;std::memcpy(c.buffers[logits].data.data()+(n/2)*2,&nan,2);}
  auto hostsite=c.site(Op::route,{logits},{ids,prob},{},{n,top});
  auto actual=hostsite;actual.spec.no=4;actual.ids.push_back(gate);actual.ids.push_back(down);actual.spec.sizes[3]=top*3;actual.spec.sizes[4]=top*3;actual.spec.types[3]=Scalar::i32;actual.spec.types[4]=Scalar::i32;
  auto host=c.buffers;std::vector<void*> hp;for(auto id:hostsite.ids)hp.push_back(host[id].data.data());hp.insert(hp.end(),{scratch.data(),host[c.error].data.data(),host[c.position].data.data(),host[c.active].data.data(),host[c.rope].data.data()});integrated::evaluate(hostsite.spec,hp.data());
  int32_t expected_error=0;std::memcpy(&expected_error,host[c.error].data.data(),4);
  if(!expected_error){View hi{host[ids].data.data(),size_t(top),Scalar::i32},hg{host[gate].data.data(),size_t(top*3),Scalar::i32},hd{host[down].data.data(),size_t(top*3),Scalar::i32};for(int j=0;j<top;++j){hg.put(j*3,hi.get(j));hg.put(j*3+1,0);hg.put(j*3+2,c.g.mid);hd.put(j*3,hi.get(j));hd.put(j*3+1,0);hd.put(j*3+2,c.g.h);}}
  std::vector<std::vector<uint8_t>> v1_raw;
  for(int version:{1,2}){packet24::kernel_version=version;std::vector<Allocation> allocations;for(const auto& b:c.buffers)allocations.push_back(runner.upload(b.data));
   runner.finish(packet18::submit_rank(runner.d,actual.spec,runner.binding(actual,c,allocations)));
   for(int id:{ids,prob,gate,down,c.error}){auto raw=runner.get(allocations[id],host[id].data.size());if(version==1)v1_raw.push_back(raw);else{size_t idx=id==ids?0:id==prob?1:id==gate?2:id==down?3:4;if(raw!=v1_raw[idx])throw std::runtime_error("packet24 route raw v1/v2 mismatch n="+std::to_string(n)+" mode="+std::to_string(mode));}bytes.write(reinterpret_cast<const char*>(raw.data()),raw.size());}
   if(!expected_error){Finish finish;finish.count=top;std::array b{allocations[prob]};auto e=runner.d.compute(finish,b,{});runner.finish({e,e,1});}
   for(int id:{ids,prob,gate,down,c.error}){auto out=runner.get(allocations[id],host[id].data.size());bool pass=out==host[id].data;std::string label="packet24 route n="+std::to_string(n)+" mode="+std::to_string(mode)+" version="+std::to_string(version)+" buffer="+std::to_string(id);packet23::row(output,label,out.data(),out.size(),pass);if(!pass)throw std::runtime_error(label);bytes.write(reinterpret_cast<const char*>(out.data()),out.size());}
   ++checks;runner.d.retire_completed_events();
  }
 }
 auto shutdown=runner.d.shutdown(std::chrono::seconds(60));if(!shutdown.safe_to_exit||shutdown.exit_code)throw std::runtime_error("packet24 route teardown");packet24::kernel_version=saved;
 std::ofstream receipt(output/"route-fixture.json");receipt<<"{\"passed\":true,\"fixtures\":15,\"version_checks\":"<<checks<<",\"raw_v1_v2_checks\":15,\"includes_ties\":true,\"includes_nan\":true,\"device_executed\":";
 #ifdef OWN_RT_HOST_ONLY
 receipt<<"false";
 #else
 receipt<<"true";
 #endif
 receipt<<",\"max_submission_ns\":"<<runner.max<<",\"teardown\":"<<shutdown.json()<<"}\n";return checks;
 }catch(const std::exception& e){packet24::kernel_version=saved;packet23::failure(runner.d,output,e.what());throw;}
}
