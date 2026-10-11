// Synthetic, real-shape profiling only. Reuse the exact production schedule.
#define main packet23_model_entry
#include "main.cpp"
#undef main
#include "capture_events.hpp"
#include "selection.hpp"
#include <functional>

namespace k2 {
struct Job {std::string label,klass,layer;unsigned per_token;std::function<void()> submit;};
std::string klass(std::string label){if(label.starts_with("blk."))return label.substr(label.find('.',4)+1);return label;}
unsigned frequency(const std::string& c){if(c=="hc.a.norm")return 47;if(c.starts_with("gdn."))return 36;if(c.starts_with("qsa."))return 12;if(c.starts_with("ple.")||c.starts_with("final.")||c=="logits"||c=="argmax"||c=="streams"||c.starts_with("begin")||c.starts_with("commit"))return 1;return 48;}
flash::Plan fixture_plan(){Geometry g;g.context=256;auto p=flash::Builder(g).build({false,false,false,true});std::vector<flash::Launch> merged;
 for(size_t i=0;i<p.launches.size();++i){auto l=p.launches[i];if(l.op=="routed_gemv"&&l.weights[0].find("ffn_gate_exps")!=std::string::npos){const auto& up=p.launches.at(i+2);require(up.op=="routed_gemv"&&l.shape==up.shape,"K2 expert pair shape");l.op="expert_gate_up";l.weights.push_back(up.weights[0]);l.outputs.insert(l.outputs.end(),up.outputs.begin(),up.outputs.end());merged.push_back(l);merged.push_back(p.launches[i+1]);i+=2;}else merged.push_back(l);}p.launches=std::move(merged);
 // The real 48-layer split has one begin/commit on each owner. Time both
 // control classes on this one-card fixture, with distinct labels and the same
 // exact operation. Peer transfers are not kernel classes.
 std::vector<flash::Launch> controls;for(const auto& l:p.launches){if(l.label=="begin.0"){auto peer=l;peer.label="begin.1";controls.push_back(peer);}if(l.label=="commit.final"){auto peer=l;peer.label="commit.0";controls.push_back(peer);}}
 for(const auto& l:controls){if(l.label=="begin.1")p.launches.insert(p.launches.begin()+1,l);else p.launches.insert(p.launches.end()-1,l);}return p;}
void input(Weights& w,const fs::path& dir){std::ifstream f(dir/"directory.tsv");require(bool(f),"K2 directory");w.directory=flash::read_directory(f);std::ifstream list(dir/"seeds.tsv");std::string name,file;while(list>>name>>file){require(fs::path(file).filename()==file,"K2 seed basename");std::ifstream in(dir/file,std::ios::binary);std::vector<uint8_t> b((std::istreambuf_iterator<char>(in)),{});require(!b.empty()&&b.size()<=65536,"K2 bounded seed");w.tiled.emplace(name,std::move(b));}require(list.eof(),"K2 seed manifest");}
std::vector<Job> jobs(Engine& e,bool bind){std::vector<Job> out;for(const auto& l:e.p.launches){if(e.removed.count(l.label)||l.op=="lookup"||l.op=="handoff"||l.op=="handoff_result")continue;auto c=klass(l.label);std::string layer=l.label.starts_with("blk.")?l.label.substr(0,l.label.find('.',4)):"outside";std::function<void()> run;
 if(!bind)run=[]{};
 else if(e.tasks.count(l.label)){auto task=e.tasks.at(l.label);if(task.kind=="batch")run=[&e,task]{e.fused_batch(task);};else run=[&e,task]{e.fused_non_gemv(task);};}
 else if(l.op=="gemv"||l.op=="routed_gemv"||l.op=="expert_gate_up"){auto m=e.matrix(l);unsigned variant=e.variant(l);if(l.op=="gemv")run=[&e,m,variant]{e.finish(0,integrated::dense(e.dev(0),m,variant),true);};else if(l.op=="routed_gemv")run=[&e,m]{e.finish(0,integrated::experts(e.dev(0),{m},false),true);};else throw std::runtime_error("unbatched paired expert");}
 else {auto [s,b]=e.bind_site(l);run=[&e,s,b]{e.finish(0,packet18::submit_parallel(e.dev(0),s,b,e.controls[0],e.scores[0],e.probabilities[0]),false);};}
 out.push_back({l.label,c,layer,frequency(c),std::move(run)});}return out;}
void nonzero(Engine& e){for(const auto& [name,b]:e.buffers[0]){if(b.type!=Scalar::bf16)continue;std::vector<uint16_t> values(std::min(b.n,size_t(2*1024*1024)));for(size_t off=0;off<b.n;off+=values.size()){size_t n=std::min(values.size(),b.n-off);for(size_t j=0;j<n;++j)values[j]=iq3::bf16_bits(float(int((off+j)*13%31)-15)/1024.f);e.upload(0,b.id,off*2,values.data(),n*2);}}}
void check(Engine& e,const std::string& stage){require(e.integer(0,"error")==0,"K2 sticky error after "+stage);}
void reset(Engine& e,unsigned position=63){uint32_t zero=0,one=1;e.put(0,"error",&zero,4);e.put(0,"active",&one,4);e.put(0,"position",&position,4);}
void capture(Engine& e,const std::function<void()>& submit,std::vector<ownrt::Event>& events){e.guard();packet24::submitted_events=&events;try{submit();}catch(...){packet24::submitted_events=nullptr;throw;}packet24::submitted_events=nullptr;require(!events.empty(),"K2 empty launch group");}
}
int main(int argc,char** argv){fs::path output,input;bool authorized=false,validate=false;unsigned card=0;std::string kernels="both";try{
 for(int i=1;i<argc;++i){std::string a=argv[i];auto value=[&]{require(i+1<argc,"K2 missing value");return std::string(argv[++i]);};if(a=="--output")output=value();else if(a=="--input")input=value();else if(a=="--card")card=std::stoul(value());else if(a=="--kernels")kernels=value();else if(a=="--authorized-device-window")authorized=true;else if(a=="--validate-only")validate=true;else throw std::runtime_error("K2 argument");}
 require(!output.empty()&&!input.empty(),"K2 input/output required");require(kernels=="both"||kernels=="v1"||kernels=="v2","K2 kernels");fs::create_directories(output);
 Options source;source.mini=true;Weights w(source);k2::input(w,input);Options a;a.cards=1;a.card=card;a.output=output;a.seconds=900;a.memory="resident";a.gemv="r5";a.timing="launch";a.fixture_resident=true;Engine e(w,a,k2::fixture_plan());
 auto manifest=k2::jobs(e,false);std::ofstream mf(output/"manifest.json");mf<<"{\"schema\":\"packet24.k2.manifest.v1\",\"diagnostic\":true,\"model_weights_required\":false,\"repetitions\":200,\"context\":256,\"position\":63,\"groups\":[";bool comma=false;for(auto& j:manifest){mf<<(comma?",":"")<<"{\"label\":"<<ownrt::quote(j.label)<<",\"class\":"<<ownrt::quote(j.klass)<<",\"groups_per_token\":"<<j.per_token<<"}";comma=true;}mf<<"]}\n";mf.close();
 if(validate){require(!authorized,"K2 validate-only refuses device authorization");std::cout<<"K2 manifest validated; no device created\n";return 0;}
#ifdef OWN_RT_HOST_ONLY
 throw std::runtime_error("host K2 permits --validate-only only; no real-shape CPU run");
#else
 require(authorized,"K2 requires explicit device-window authorization");
 for(char** p=environ;*p;++p)require(!std::string(*p).starts_with("NEO"),"NEO debug key refused");
 std::signal(SIGTERM,stop);std::signal(SIGINT,stop);
 try {e.initialize();k2::nonzero(e);require(e.dev(0).arena.total(Memory::device)<8ull*1024*1024*1024,"K2 8 GiB device allocation bound");auto jobs=k2::jobs(e,true);
 // First preparation builds descriptors and uploads all weights, outside timing.
 packet24::kernel_version=1;k2::reset(e);for(auto& j:jobs){j.submit();e.drain();k2::check(e,"preparation "+j.label);}k2::reset(e);require(e.dev(0).arena.total(Memory::device)<8ull*1024*1024*1024,"K2 prepared allocation bound");
 // Preserve one deterministic starting state for every class/version/sequence.
 // All restores are owner-tracked copies outside measured intervals.
 std::vector<std::pair<Allocation,Allocation>> fixture_snapshots;ownrt::CopyEngine fixture_copy(e.dev(0));ownrt::Event copied=0;
 for(const auto& [name,b]:e.buffers[0]){size_t bytes=b.n*flash::scalar_bytes(b.type);auto saved=e.allocate(0,"k2-snapshot:"+name,bytes,Category::scratch,Lifetime::transaction);fixture_snapshots.push_back({b.id,saved});copied=fixture_copy.copy(saved,0,b.id,0,bytes,{});}
 require(e.dev(0).wait(copied,std::chrono::seconds(60)),"K2 snapshot deadline");e.dev(0).retire_completed_events();require(e.dev(0).arena.total(Memory::device)<8ull*1024*1024*1024,"K2 snapshot allocation bound");
 auto restore=[&]{e.drain();ownrt::Event last=0;for(auto [dst,src]:fixture_snapshots){e.guard();last=fixture_copy.copy(dst,0,src,0,e.dev(0).arena.row(src).bytes,{});}require(e.dev(0).wait(last,std::chrono::seconds(60)),"K2 restore deadline");e.dev(0).retire_completed_events();};
 std::ofstream raw(output/"events.jsonl"),walls(output/"sequence-wall.jsonl");uint64_t maximum=0;unsigned groups=0;
 for(unsigned version:{1u,2u}){if(kernels!="both"&&kernels!="v"+std::to_string(version))continue;packet24::kernel_version=version;
  for(auto& j:jobs){restore();k2::reset(e,j.klass.starts_with("commit")?0:63);j.submit();e.drain();k2::check(e,"version warmup "+j.label);k2::reset(e,j.klass.starts_with("commit")?0:63);std::vector<std::vector<ownrt::Event>> samples(200);
   for(auto& sample:samples)k2::capture(e,j.submit,sample);require(e.dev(0).wait(samples.back().back(),std::chrono::seconds(60)),"K2 per-class completion deadline");
   for(unsigned r=0;r<samples.size();++r){raw<<"{\"kernels\":\"v"<<version<<"\",\"label\":"<<ownrt::quote(j.label)<<",\"class\":"<<ownrt::quote(j.klass)<<",\"groups_per_token\":"<<j.per_token<<",\"repetition\":"<<r<<",\"events\":[";bool comma=false;for(auto event:samples[r]){auto t=e.dev(0).timing(event);require(t.start_ns&&t.end_ns>=t.start_ns,"K2 GPU timestamp range");maximum=std::max(maximum,t.end_ns-t.start_ns);require(t.end_ns-t.start_ns<=4000000000ull,"K2 per-submission budget 4s exceeded");raw<<(comma?",":"")<<"{\"event\":"<<event<<",\"command_start_ns\":"<<t.start_ns<<",\"command_end_ns\":"<<t.end_ns<<"}";comma=true;}raw<<"]}\n";++groups;}raw.flush();e.drain();k2::check(e,"class "+j.label);
  }
  // Each representative layer is issued 200 times with exactly one final wait.
  // This is a separate host-issue diagnostic; no timings are queried in-loop.
  for(auto layer:{"blk.0","blk.1","blk.2","blk.3"}){restore();k2::reset(e);auto start=std::chrono::steady_clock::now();for(unsigned r=0;r<200;++r)for(auto& j:jobs)if(j.layer==layer||(std::string(layer)=="blk.0"&&j.klass=="streams")){e.guard();j.submit();}double issue=Engine::ms(start);require(e.dev(0).wait(e.tail,std::chrono::seconds(60)),"K2 layer sequence deadline");double completion=Engine::ms(start);e.tail=0; // Completion already waited; drain only profiles/retires.
   walls<<"{\"kernels\":\"v"<<version<<"\",\"layer\":"<<ownrt::quote(layer)<<",\"includes_initial_broadcast_norm\":"<<(std::string(layer)=="blk.0"?"true":"false")<<",\"repetitions\":200,\"waits\":1,\"issue_wall_ms\":"<<issue<<",\"completion_wall_ms\":"<<completion<<"}\n";walls.flush();e.drain();k2::check(e,std::string("sequence ")+layer);}
 }
 require(e.integer(0,"error")==0,"K2 synthetic error flag");auto r=e.dev(0).shutdown(std::chrono::seconds(60));require(r.safe_to_exit&&r.exit_code==0,"K2 safe shutdown");std::ofstream receipt(output/"receipt.json");receipt<<"{\"schema\":\"packet24.k2.v1\",\"passed\":true,\"diagnostic\":true,\"device_executed\":true,\"repetitions\":200,\"launch_groups\":"<<groups<<",\"max_submission_ns\":"<<maximum<<",\"owner_cards\":1,\"safe_to_exit\":true,\"teardown\":["<<r.json()<<"]}\n";
 }catch(const std::exception& ex){packet24::submitted_events=nullptr;if(!e.devices.empty())packet23::failure(e.dev(0),output,ex.what());throw;}
 return 0;
#endif
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';if(!output.empty()){fs::create_directories(output);std::ofstream(output/"k2-error.json")<<"{\"passed\":false,\"error\":"<<ownrt::quote(e.what())<<"}\n";}return 1;}}
