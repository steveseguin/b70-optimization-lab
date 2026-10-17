// Small draft-only fixture: no target model forward and no real weights.
#define main unused_packet66_entry
#include "main.cpp"
#undef main
int main(int argc,char**argv){try{
 require(argc==3,"fixture output and on/off");fs::path out=argv[1];fs::create_directories(out);
 Options a;a.mini=true;a.pipeline_mini=true;a.rank=1;a.draft_rank=1;a.target_split=23;a.context=64;a.memory="resident";a.nongemv="parallel";a.timing="token";a.output=out;a.seconds=120;
 Weights w(a);Engine e(w,a,pipeline::split(plan(w,a),1,true,1,23));e.initialize();e.prepare_plan();
 std::ofstream bytes(out/"state.bin",std::ios::binary);std::ofstream proposals(out/"proposals.txt");
 auto write=[&](const std::vector<uint8_t>& v){bytes.write(reinterpret_cast<const char*>(v.data()),v.size());};
 auto target=[&](){std::vector<uint8_t> v;for(auto [name,b]:e.buffers[0]){auto raw=e.readback(0,b.id,b.n*flash::scalar_bytes(b.type));v.insert(v.end(),raw.begin(),raw.end());}return v;};
 {
 mtp36::DraftRuntime draft(e);draft.probe_enabled=std::string(argv[2])=="on";
 for(int request=0;request<2;++request){
  if(request){fs::create_directories(out/"request2");draft.reset_request(out/"request2");}
  for(int pos=0;pos<34;++pos){
   std::vector<uint16_t> hidden(4*e.p.g.h);for(size_t i=0;i<hidden.size();++i)hidden[i]=iq3::bf16_bits(float(int(i%13)-6+pos)/32.f);
   e.put(0,"streams",hidden.data(),hidden.size()*2);auto before=target();int d1;
   if(pos%2){require(draft.begin((pos*7+request)%e.p.g.vocab,pos+1,true),"async begin");std::optional<mtp36::DraftRuntime::Completion> result;
    e.progress_callback=[&](){auto submissions=e.submitted;if(auto done=draft.poll_result())result=done;require(e.submitted==submissions,"completion callback submitted probe work");};
    e.drain();require(bool(result),"publication callback did not finish");e.progress_callback={};d1=result->token;
   }else d1=draft.run((pos*7+request)%e.p.g.vocab,pos+1,true);
   if(pos%3==0||pos==33)draft.flush_probe();
   require(d1>=0,"fixture draft failed");require(before==target(),"probe mutated target buffers");
   proposals<<d1<<'\n';auto state=draft.fixture_state();auto fingerprint=hash(before)+hash(state);bytes.write(fingerprint.data(),fingerprint.size());
   if(pos==33&&request==1){write(before);write(state);}bytes.write(reinterpret_cast<const char*>(&d1),4);
  }
 }
 }
 bytes.close();proposals.close();e.shutdown();
 std::cout<<"{\"passed\":true,\"device_executed\":false,\"draft_steps\":68,\"requests\":2,\"sync_and_async\":true,\"target_model_forwards\":0}\n";
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
