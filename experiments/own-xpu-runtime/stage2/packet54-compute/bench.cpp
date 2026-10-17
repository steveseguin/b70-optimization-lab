#include "p51-bench.hpp"
#include "recurrence.hpp"
#include "route.hpp"
#include "hc_ffn.hpp"
namespace p54bench {
using F=p51bench::Fixture;
using Capture=std::map<std::string,std::vector<uint8_t>>;
struct Group {std::string name;std::vector<size_t> sites;std::vector<std::string> variants;};
std::vector<Group> groups(F&f){
 std::vector<Group> gs{{"route",{}, {"route-rank4","route-exp32-rank4"}}, {"gdn.recurrence",{}, {"rows4-shared","rows8-shared"}}, {"hc.inject_mix_norm",{}, {"mix-vector4"}}, {"ffn.combine",{}, {}}};
 for(size_t i=0;i<f.groups.size();++i){auto cls=packet26::Dispatch::class_name(f.e.p.launches[f.groups[i].first].label);if(cls=="route")gs[0].sites.push_back(i);else if(cls=="gdn.recurrence")gs[1].sites.push_back(i);else if(cls.starts_with("hc."))gs[2].sites.push_back(i);else if(cls=="ffn.combine")gs[3].sites.push_back(i);else throw std::runtime_error("unexpected class "+cls);}
 require(gs[0].sites.size()==1&&gs[1].sites.size()==1&&gs[2].sites.size()==6&&gs[3].sites.size()==1,"production class census");return gs;
}
flash::Plan plan_only(Weights&w,Options&a){auto p=p51bench::layer_plan(w,a,4);std::erase_if(p.launches,[](const auto&l){auto c=packet26::Dispatch::class_name(l.label);return !(c=="route"||c=="gdn.recurrence"||c=="ffn.combine"||c=="hc.a.norm"||c=="hc.f.norm"||c=="hc.a.mix"||c=="hc.f.mix"||c=="hc.a.inject"||c=="hc.f.inject");});std::set<std::string>used{"active","error","position"};for(auto&l:p.launches){used.insert(l.inputs.begin(),l.inputs.end());used.insert(l.outputs.begin(),l.outputs.end());}std::erase_if(p.buffers,[&](auto&b){return !used.contains(b.name);});return p;}
void restore(F&f,const Group&g,const F::Snapshot&s,bool carry_state=false){std::set<Allocation> need{f.id("active"),f.id("error"),f.id("position"),f.e.scratch[0],f.e.workspace[0]};std::set<Allocation> state;
 for(auto site:g.sites){auto&l=f.e.p.launches[f.groups[site].first];for(auto&n:l.inputs)need.insert(f.id(n));for(auto&n:l.outputs)need.insert(f.id(n));if(l.op=="gdn"){state.insert(f.id(l.inputs[3]));state.insert(f.id(l.outputs[1]));}}
 for(size_t j=0;j<f.mutable_ids.size();++j)if(need.contains(f.mutable_ids[j])&&!(carry_state&&state.contains(f.mutable_ids[j])))f.e.upload(0,f.mutable_ids[j],0,s[j].data(),s[j].size());f.e.fp32_sources[0]=0;
}
void site_candidate(F&f,size_t site,unsigned v){auto&e=f.e;auto&l=e.p.launches[f.groups[site].first];auto c=packet26::Dispatch::class_name(l.label);
 if(c.ends_with("inject")){f.execute(f.groups[site],false);return;}
 auto&b=e.prepared.at(&l);
 if(c=="route"){e.finish(0,v==0?p54route::submit<4,256>(e.dev(0),b.spec,b.bindings):p54route::submit<4,32>(e.dev(0),b.spec,b.bindings),false);return;}
 if(c=="gdn.recurrence"){auto binding=p54::recurrence_bindings(b.spec,b.bindings);auto issue=[&]<unsigned R>(){p54::RecurrenceKernel<R>op;op.shape=binding.shape;auto ev=e.dev(0).compute(op,binding.ids,{});e.finish(0,ev);};if(v==0)issue.template operator()<4>();else issue.template operator()<8>();return;}
 if(c.ends_with("norm")){f.execute(f.groups[site],false);return;}
 if(c.ends_with("mix")){e.finish(0,p54hc::submit_mix(e.dev(0),b.spec,b.bindings),false);return;}
 if(c=="ffn.combine"){e.finish(0,p54hc::submit_combine(e.dev(0),b.spec,b.bindings),false);return;}throw std::runtime_error("candidate site");
}
void capture_site(F&f,size_t site,Capture&c){auto&l=f.e.p.launches[f.groups[site].first];for(auto&n:l.outputs){auto b=f.e.buffers[0].at(n);c[l.label+":"+n]=f.e.readback(0,b.id,b.n*flash::scalar_bytes(b.type));}auto cls=packet26::Dispatch::class_name(l.label);if(cls=="route"||cls.ends_with("norm"))c[l.label+":scratch"]=f.e.readback(0,f.e.scratch[0],cls=="route"?4352:1280);}
std::vector<p51bench::EventRow> events(F&f){auto&e=f.e;if(e.tail)e.wait(0,e.tail);std::vector<p51bench::EventRow>v;
#ifndef OWN_RT_HOST_ONLY
 for(auto&p:e.pending)for(auto id=p.launch.first;id<=p.launch.last;++id){auto t=e.dev(0).timing(id);require(t.end_ns>t.start_ns&&t.end_ns-t.start_ns<4000000000ull,"bounded event");v.push_back({"class",t.start_ns,t.end_ns,id});}
#endif
 e.pending.clear();e.tail=0;e.dev(0).retire_completed_events();return v;}
Capture execute(F&f,const Group&g,int variant,bool capture,std::vector<p51bench::EventRow>&ev){Capture c;for(auto site:g.sites){if(variant<0)f.execute(f.groups[site],g.name=="route");else site_candidate(f,site,variant);auto one=events(f);ev.insert(ev.end(),one.begin(),one.end());if(capture)capture_site(f,site,c);}if(capture)for(auto n:{"active","error","position"})c[n]=f.e.readback(0,f.id(n),4);return c;}
Capture expected(F&f,const Group&g){
 auto&e=f.e;std::map<Allocation,std::vector<uint8_t>> mem;
 auto ensure=[&](Allocation a){if(!mem.contains(a))mem[a]=e.readback(0,a,e.dev(0).arena.row(a).bytes);};
 for(auto site:g.sites){auto&l=e.p.launches[f.groups[site].first];if(l.op=="gemv"){auto&m=e.matrices.at(&l).at(0);for(auto id:{m.w,m.x,m.y})ensure(id);}else for(auto id:e.prepared.at(&l).bindings)ensure(id);for(auto&n:l.outputs)ensure(f.id(n));}
 for(auto n:{"active","error","position"})ensure(f.id(n));Capture c;
 for(auto site:g.sites){auto&l=e.p.launches[f.groups[site].first];auto cls=packet26::Dispatch::class_name(l.label);
  if(l.op=="gemv"){auto&m=e.matrices.at(&l).at(0);require(m.type==iq3::Type::F32&&m.columns==10240&&m.rows==4,"inject control shape");auto*w=mem.at(m.w).data();auto*x=reinterpret_cast<const uint16_t*>(mem.at(m.x).data());auto*y=reinterpret_cast<uint16_t*>(mem.at(m.y).data());size_t rb=arithmetic::row_bytes(m.type,m.columns,e.variant(l));unsigned split=e.variant(l)==4?4:1;for(unsigned row=0;row<4;++row){float partial[4]{};for(unsigned part=0;part<split;++part){auto range=iq3::kopt2::bounds(10240,part,split);float lanes[32];for(unsigned lane=0;lane<32;++lane)lanes[lane]=iq3::kopt2::lane_range<iq3::Type::F32>(w+row*rb,x,iq3::Type::BF16,range.first,range.second,lane);partial[part]=iq3::tree32(lanes);}y[row]=iq3::bf16_bits(split==1?partial[0]:(partial[0]+partial[1])+(partial[2]+partial[3]));}}
  else {auto&b=e.prepared.at(&l);std::vector<void*> pointers;for(auto a:b.bindings)pointers.push_back(mem.at(a).data());if(cls=="route")p54route::control_host(route42::bind(b.spec,pointers));else if(cls=="gdn.recurrence")p54::recurrence_control(b.spec,pointers);else if(cls.ends_with("norm"))p54hc::control_norm(b.spec,pointers);else if(cls.ends_with("mix"))p54hc::control_mix(b.spec,pointers);else if(cls=="ffn.combine")p54hc::control_combine(b.spec,pointers);else throw std::runtime_error("CPU control site");}
  for(auto&n:l.outputs)c[l.label+":"+n]=mem.at(f.id(n));if(cls=="route"||cls.ends_with("norm")){auto&bytes=mem.at(e.scratch[0]);c[l.label+":scratch"]={bytes.begin(),bytes.begin()+(cls=="route"?4352:1280)};}
 }
 for(auto n:{"active","error","position"})c[n]=mem.at(f.id(n));return c;
}
std::string identity(const Capture&c){std::vector<uint8_t>b;for(auto&[n,v]:c){b.insert(b.end(),n.begin(),n.end());b.insert(b.end(),v.begin(),v.end());}return hash(b);}
void comparison(std::ofstream&o,const Group&g,const std::string&v,unsigned m,unsigned row,unsigned iteration,const Capture&actual,const Capture&cpu,const Capture&production){p51bench::compare_maps(actual,cpu,"CPU control");p51bench::compare_maps(actual,production,"production control");o<<"{\"class\":"<<ownrt::quote(g.name)<<",\"variant\":"<<ownrt::quote(v)<<",\"m\":"<<m<<",\"token_row\":"<<row<<",\"iteration\":"<<iteration<<",\"equal\":true,\"production_equal\":true,\"sha256\":"<<ownrt::quote(identity(actual))<<",\"cpu_sha256\":"<<ownrt::quote(identity(cpu))<<",\"production_sha256\":"<<ownrt::quote(identity(production))<<",\"buffers\":"<<actual.size()<<",\"bytes\":"<<std::accumulate(actual.begin(),actual.end(),size_t(0),[](size_t n,const auto&v){return n+v.second.size();})<<"}\n";}
void timing(std::ofstream&o,const Group&g,const std::string&variant,const std::string&pair,unsigned m,unsigned row,unsigned iteration,const std::vector<p51bench::EventRow>&ev){uint64_t ns=0;for(auto&e:ev)ns+=e.end-e.start;o<<"{\"class\":"<<ownrt::quote(g.name)<<",\"variant\":"<<ownrt::quote(variant)<<",\"pair_variant\":"<<ownrt::quote(pair)<<",\"m\":"<<m<<",\"token_row\":"<<row<<",\"iteration\":"<<iteration<<",\"warmup\":"<<(iteration<10?"true":"false")<<",\"gpu_ns\":"<<ns<<",\"events\":[";for(size_t j=0;j<ev.size();++j)o<<(j?",":"")<<"{\"start_ns\":"<<ev[j].start<<",\"end_ns\":"<<ev[j].end<<"}";o<<"]}\n";}
}
int main(int argc,char**argv){using namespace p54bench;std::string mode,error;fs::path output;int card=-1;bool authorized=false,device_executed=false,safe=true;unsigned checks=0;std::unique_ptr<Engine>engine;std::vector<std::string>teardown;
 try{for(int i=1;i<argc;++i){std::string k=argv[i];auto v=[&]{require(i+1<argc,"argument value");return std::string(argv[++i]);};if(k=="--mode")mode=v();else if(k=="--output")output=v();else if(k=="--card")card=std::stoi(v());else if(k=="--authorized-device-window")authorized=true;else throw std::runtime_error("unknown argument "+k);}require(!output.empty()&&(mode=="cpu-full"||mode=="exact"||mode=="timing"),"mode/output required");fs::create_directories(output);
#ifdef OWN_RT_HOST_ONLY
 require(mode=="cpu-full"&&!authorized&&card==-1,"host build CPU only");
#else
 require((mode=="exact"||mode=="timing")&&authorized&&card==0,"coordinator card0 authorization required");
#endif
 std::signal(SIGTERM,stop);std::signal(SIGINT,stop);packet26::dispatch.load((p51bench::packet/"dispatch-baseline.json").string());Options a;a.mini=true;Weights w(a);a.mini=false;a.cards=2;a.context=4096;a.memory="resident";a.legacy=true;a.timing="class";a.seconds=2820;a.output=output;auto plan=plan_only(w,a);engine=std::make_unique<Engine>(w,a,plan);auto&e=*engine;
#ifdef OWN_RT_HOST_ONLY
 e.devices.push_back(std::make_unique<ownrt::Device>(std::make_unique<Host>()));
#else
 {std::vector<sycl::device>cards;for(auto&p:sycl::platform::get_platforms())if(p.get_backend()==sycl::backend::ext_oneapi_level_zero)for(auto&d:p.get_devices(sycl::info::device_type::gpu))cards.push_back(d);require(!cards.empty()&&cards[0].get_info<sycl::ext::intel::info::device::pci_address>()=="0000:23:00.0","PCI card0 mismatch");}device_executed=true;e.devices.push_back(std::make_unique<ownrt::Device>(ownrt::make_sycl_device(0,true)));
#endif
 F f(e,4);f.setup();auto gs=groups(f);std::ofstream comparisons(output/"comparisons.jsonl"),iterations(output/"iterations.jsonl"),exceptions(output/"exceptions.jsonl");std::array<F::Snapshot,4>snapshots;for(unsigned fixture=0;fixture<2;++fixture)for(unsigned row=0;row<2;++row){f.input(0x5400+fixture*97+row*7919,4094+row);snapshots[fixture*2+row]=f.snapshot();}
 for(unsigned m:mode=="cpu-full"?std::vector<unsigned>{1}:std::vector<unsigned>{1,2})for(unsigned iteration=0;iteration<(mode=="timing"?210u:mode=="cpu-full"?1u:2u);++iteration)for(auto&g:gs){e.guard();
  if(mode!="timing"){std::vector<Capture>baseline,cpus;for(unsigned row=0;row<m;++row){restore(f,g,snapshots[(iteration%2)*2+row],row>0);auto cpu=expected(f,g);std::vector<p51bench::EventRow>ev;auto actual=execute(f,g,-1,true,ev);comparison(comparisons,g,"control",m,row,iteration,actual,cpu,actual);baseline.push_back(actual);cpus.push_back(cpu);++checks;}
   for(unsigned v=0;v<g.variants.size();++v)for(unsigned row=0;row<m;++row){restore(f,g,snapshots[(iteration%2)*2+row],row>0);std::vector<p51bench::EventRow>ev;auto actual=execute(f,g,v,true,ev);comparison(comparisons,g,g.variants[v],m,row,iteration,actual,cpus[row],baseline[row]);++checks;}}
  else for(unsigned v=0;v<g.variants.size();++v){std::vector<Capture>paired;for(unsigned arm=0;arm<2;++arm){bool ca=bool(arm)^bool(iteration%2);for(unsigned row=0;row<m;++row){restore(f,g,snapshots[(iteration%2)*2+row],row>0);std::vector<p51bench::EventRow>ev;auto actual=execute(f,g,ca?int(v):-1,true,ev);timing(iterations,g,ca?g.variants[v]:"control",g.variants[v],m,row,iteration,ev);if(!arm)paired.push_back(std::move(actual));else p51bench::compare_maps(actual,paired[row],"timing pair");require(e.integer(0,"error")==0,"timing sticky error");}}iterations.flush();}
 }
 // Actual compiled production parity for vector mix's nonfinite operands.
 // Norm and FFN vector arms are closed by retained production-byte failures.
 if(mode!="timing"){
  Group mix{"hc.mix",{}, {"mix-vector4"}};
  for(auto site:gs[2].sites)if(packet26::Dispatch::class_name(e.p.launches[f.groups[site].first].label)=="hc.a.mix")mix.sites.push_back(site);
  require(mix.sites.size()==1,"exception mix site");restore(f,mix,snapshots[0]);auto&l=e.p.launches[f.groups[mix.sites[0]].first];
  for(unsigned input=0;input<2;++input){auto b=e.buffers[0].at(l.inputs[input]);auto raw=e.readback(0,b.id,b.n*2);auto*x=reinterpret_cast<uint16_t*>(raw.data());for(unsigned h=0;h<4;++h)for(unsigned j=0;j<4;++j)x[h*2560+j]=input==1?0x7fc3:j%2?0xffc5:0x7fc1;e.upload(0,b.id,0,raw.data(),raw.size());}
  auto poisoned=f.snapshot();std::vector<p51bench::EventRow>ev;auto baseline=execute(f,mix,-1,true,ev);restore(f,mix,poisoned);ev.clear();auto actual=execute(f,mix,0,true,ev);p51bench::compare_maps(actual,baseline,"exceptional actual mix production");
  exceptions<<"{\"class\":\"hc.mix\",\"variant\":\"mix-vector4\",\"equal\":true,\"sha256\":"<<ownrt::quote(identity(actual))<<",\"production_sha256\":"<<ownrt::quote(identity(baseline))<<",\"buffers\":4,\"bytes\":5132}\n";
 }

 teardown=e.shutdown();engine.reset();
 }catch(const std::exception&ex){error=ex.what();if(engine){try{teardown=engine->shutdown();}catch(const std::exception&close){safe=false;save(output/"unsafe-teardown.txt",close.what());ownrt::hold_for_supervisor();}engine.reset();}}
 std::ostringstream result;result<<"{\"schema\":\"ownrt.packet54.bench.v1\",\"passed\":"<<(error.empty()?"true":"false")<<",\"mode\":"<<ownrt::quote(mode)<<",\"cpu_mock\":"<<(mode=="cpu-full"?"true":"false")<<",\"device_executed\":"<<(device_executed?"true":"false")<<",\"safe_to_exit\":"<<(safe?"true":"false")<<",\"checks\":"<<checks<<",\"error\":"<<ownrt::quote(error)<<"}";if(!output.empty())save(output/"receipt.json",result.str()+"\n");std::cout<<result.str()<<"\n";return error.empty()?0:1;
}
