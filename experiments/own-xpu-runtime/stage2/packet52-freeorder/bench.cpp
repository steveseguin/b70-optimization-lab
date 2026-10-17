#include "p51-bench.hpp"
#include "freeorder.hpp"
namespace p52bench {
struct Member {const flash::Launch*launch;Matrix m; p52::Spec s;std::array<Allocation,11>ids;};
struct Group {std::string name;std::vector<size_t>sites;std::vector<Member>members;};
using F=p51bench::Fixture;
std::vector<uint8_t> slice(Engine&e,Allocation src,size_t offset,size_t n){e.drain();std::vector<uint8_t>b(n);for(size_t i=0;i<n;i+=4*1024*1024){size_t take=std::min(n-i,size_t(4*1024*1024));ownrt::CopyEngine copy(e.dev(0));e.wait(0,copy.copy(e.slab[0],0,src,offset+i,take,{}));std::memcpy(b.data()+i,e.dev(0).arena.row(e.slab[0]).pointer,take);e.dev(0).retire_completed_events();}return b;}
Member member(F&f,const flash::Launch&l){auto&e=f.e;auto m=e.matrices.at(&l).at(0);auto cls=packet26::Dispatch::class_name(l.label);bool pair=cls=="expsgate",packed=pair||cls=="expsdown";p52::Spec s{m.type,unsigned(m.columns),unsigned(m.rows),unsigned(m.count),unsigned(m.experts),unsigned(packed?p48::layout(m.type,m.columns).row_bytes:arithmetic::row_bytes(m.type,m.columns,e.variant(l))),unsigned(cls=="hc.a.low"||cls=="hc.f.low"?1:cls=="attention"?2:0),pair};auto peer=pair?e.matrices.at(&l).at(1):m;auto out=s.epilogue==1?f.id(l.label.substr(0,l.label.size()-3)+"act"):m.y;auto streams=s.epilogue==2?f.id("streams"):m.y;auto inject=s.epilogue==2?f.id(f.prefix+"hc.a.inject"):m.x;
 return {&l,m,s,{packed?f.packed.at(l.weights[0]):m.w,pair?f.packed.at(l.weights[1]):m.w,m.x,m.y,peer.y,out,streams,inject,m.routes?m.routes:m.x,m.status?m.status:m.y,peer.status?peer.status:peer.y}};
}
std::vector<Group> groups(F&f){std::vector<Group>out;auto&e=f.e;for(size_t i=0;i<f.groups.size();++i){auto&l=e.p.launches[f.groups[i].first];auto cls=packet26::Dispatch::class_name(l.label);std::string name=cls=="hc.a.low"||cls=="hc.a.gate"||cls=="hc.f.low"||cls=="hc.f.gate"?"hc.low_gate":cls=="router"?"small.ffn.q6":cls;
 if(name!="expsgate"&&name!="gdn.qkv"&&name!="expsdown"&&name!="attention"&&name!="hc.low_gate"&&name!="small.ffn.q6"&&name!="gdn.z")continue;
 auto it=std::find_if(out.begin(),out.end(),[&](auto&x){return x.name==name;});if(it==out.end()){out.push_back({name,{},{}});it=out.end()-1;}it->sites.push_back(i);
 if(name=="small.ffn.q6"){require(e.small_groups.contains(&l),"production small tuple");for(auto*site:e.small_groups.at(&l).members)it->members.push_back(member(f,*site));}
 else it->members.push_back(member(f,l));
 }require(out.size()==7,"all seven ordinary-layer classes");return out;}
void inputs(F&f,unsigned seed){f.input(seed,4095);std::array<iq3::Route,10>routes{};std::array<uint32_t,10>ids{};for(unsigned j=0;j<10;++j){ids[j]=(seed*17+j*47)%512;routes[j]={ids[j],0,640};}f.e.upload(0,f.id(f.prefix+"ids"),0,ids.data(),40);
 for(const auto&[site,ms]:f.e.matrices)for(auto&m:ms)if(m.routes){for(unsigned j=0;j<10;++j)routes[j].row_count=m.rows;f.e.upload(0,m.routes,0,routes.data(),sizeof(routes));}
}
void restore_group(F&f,const Group&g,const F::Snapshot&snapshot){std::set<Allocation>needed{f.id("active"),f.id("error"),f.id("position")};for(auto&m:g.members)for(unsigned j=2;j<11;++j)needed.insert(m.ids[j]);for(size_t j=0;j<f.mutable_ids.size();++j)if(needed.contains(f.mutable_ids[j]))f.e.upload(0,f.mutable_ids[j],0,snapshot[j].data(),snapshot[j].size());f.e.fp32_sources[0]=0;}
void control(F&f,const Group&g){for(auto i:g.sites){auto&l=f.e.p.launches[f.groups[i].first];auto c=packet26::Dispatch::class_name(l.label);bool p51=c=="attention"||c.starts_with("hc.");f.execute(f.groups[i],p51);}}
void candidate(F&f,const Group&g,unsigned variant){
 // HC sites have data dependencies (low -> BF16 activation -> gate), so retain
 // four separate production sites. Small FFN's four siblings share one launch.
 unsigned batch=g.name=="small.ffn.q6"?g.members.size():1;
 for(unsigned first=0;first<g.members.size();first+=batch){p52::Kernel op;op.count=batch;op.variant=variant;std::vector<Allocation>ids;for(unsigned j=0;j<batch;++j){auto&m=g.members[first+j];op.specs[j]=m.s;ids.insert(ids.end(),m.ids.begin(),m.ids.end());}ids.push_back(f.e.scratch[0]);auto event=f.e.dev(0).compute(op,ids,{});integrated::Launch launch{event,event,1};
#ifndef OWN_RT_HOST_ONLY
 if(p52::orders[variant].split>1){op.stage=1;std::array after{event};launch.last=f.e.dev(0).compute(op,ids,after);++launch.passes;}
#endif
 f.e.finish(0,launch,true);
 }
}
using Capture=std::map<std::string,std::vector<uint8_t>>;
Capture capture(F&f,const Group&g){Capture c;for(auto&m:g.members){auto add=[&](unsigned i,size_t n){c[std::to_string(m.ids[i])]=f.e.readback(0,m.ids[i],n);};add(3,m.s.rows*m.s.count*2);if(m.s.paired)add(4,m.s.rows*m.s.count*2);if(m.s.epilogue==1)add(5,m.s.rows*2);if(m.s.epilogue==2)add(6,m.s.rows*8);if(m.s.count>1){add(9,m.s.count*4);if(m.s.paired)add(10,m.s.count*4);}}return c;}
struct HostMember {p52::Spec s;std::array<std::vector<uint8_t>,11>data;std::vector<float>scratch;};
HostMember host_member(F&f,const Member&m){HostMember h;h.s=m.s;h.s.experts=m.s.count;auto&s=h.s;std::vector<iq3::Route>routes(s.count);if(s.count>1){auto b=f.e.readback(0,m.ids[8],s.count*sizeof(iq3::Route));std::memcpy(routes.data(),b.data(),b.size());}else routes[0]={0,0,s.rows};
 for(unsigned which=0;which<(s.paired?2u:1u);++which){h.data[which].resize(size_t(s.count)*s.rows*s.rb);for(unsigned slot=0;slot<s.count;++slot){size_t off=(size_t(routes[slot].expert_id)*s.rows+routes[slot].row_begin)*s.rb;auto b=slice(f.e,m.ids[which],off,size_t(s.rows)*s.rb);std::memcpy(h.data[which].data()+size_t(slot)*s.rows*s.rb,b.data(),b.size());}}
 h.data[2]=f.e.readback(0,m.ids[2],s.k*(s.type==iq3::Type::IQ4_NL?s.count:1)*2);h.data[3].resize(s.rows*s.count*2);h.data[4].resize(s.rows*s.count*2);h.data[5].resize(s.rows*2);h.data[6]=s.epilogue==2?f.e.readback(0,m.ids[6],s.rows*8):std::vector<uint8_t>(8);h.data[7]=s.epilogue==2?f.e.readback(0,m.ids[7],8):std::vector<uint8_t>(8);h.data[8].resize(s.count*sizeof(iq3::Route));for(unsigned slot=0;slot<s.count;++slot){routes[slot].expert_id=slot;routes[slot].row_begin=0;}std::memcpy(h.data[8].data(),routes.data(),h.data[8].size());h.data[9].resize(s.count*4);h.data[10].resize(s.count*4);h.scratch.resize(p52::outputs(s)*4);return h;}
void mirror_member(HostMember&h,unsigned variant,bool production=false,unsigned split=1){p52::Kernel op;op.specs[0]=h.s;op.variant=variant;std::vector<void*>ptr;for(auto&b:h.data)ptr.push_back(b.data());ptr.push_back(h.scratch.data());auto bound=op.bind(ptr)[0];p52::mirror(bound,p52::orders[variant],production,split);}
// Capture mirrors before each sequential operation; HC gate sees the candidate
// low activation. Inputs are copied out of timed intervals only in E windows.
Capture exact_candidate(F&f,const Group&g,unsigned variant,bool production=false){Capture expected;unsigned member_index=0;std::vector<uint8_t>partials;
 for(auto&m:g.members){auto h=host_member(f,m);unsigned split=(f.e.variant(*m.launch)==4||f.e.variant(*m.launch)==7)?4:1;mirror_member(h,variant,production,split);
  if(g.name!="small.ffn.q6"){if(production){Group one{g.name,{g.sites.at(member_index)}, {m}};control(f,one);}else {Group one{g.name,{}, {m}};candidate(f,one,variant);}}
  auto add=[&](unsigned i){expected[std::to_string(m.ids[i])]=h.data[i];};add(3);if(m.s.paired)add(4);if(m.s.epilogue==1)add(5);if(m.s.epilogue==2)add(6);if(m.s.count>1){add(9);if(m.s.paired)add(10);}
  if(!production&&p52::orders[variant].split==4){std::vector<uint8_t>raw(h.scratch.size()*4);std::memcpy(raw.data(),h.scratch.data(),raw.size());if(g.name=="small.ffn.q6")partials.insert(partials.end(),raw.begin(),raw.end());else p51bench::compare_bytes(slice(f.e,f.e.scratch[0],0,raw.size()),raw,"split4 partials own mirror");}
  ++member_index;
 }
 if(g.name=="small.ffn.q6"){if(production)control(f,g);else candidate(f,g,variant);if(!partials.empty())p51bench::compare_bytes(slice(f.e,f.e.scratch[0],0,partials.size()),partials,"small tuple split partials");}
 return expected;
}
std::string identity(const Capture&c){std::vector<uint8_t>bytes;for(auto&[n,b]:c){bytes.insert(bytes.end(),n.begin(),n.end());bytes.insert(bytes.end(),b.begin(),b.end());}return hash(bytes);}
void check(const Capture&a,const Capture&b){require(a.size()==b.size(),"mirror capture count");for(auto&[n,v]:a)p51bench::compare_bytes(v,b.at(n),"free-order own mirror "+n);}
struct Distance {size_t elements=0,differing=0;double max_absolute=0,max_relative=0;};
Distance distance(const Capture&a,const Capture&b){Distance d;for(auto&[n,x]:a){auto&y=b.at(n);require(x.size()==y.size(),"distance extent");for(size_t i=0;i+1<x.size();i+=2){uint16_t u,v;std::memcpy(&u,x.data()+i,2);std::memcpy(&v,y.data()+i,2);++d.elements;d.differing+=u!=v;float f=p39::widen(u),g=p39::widen(v);if(std::isfinite(f)&&std::isfinite(g)){double delta=std::abs(double(f)-g);d.max_absolute=std::max(d.max_absolute,delta);d.max_relative=std::max(d.max_relative,delta/std::max(std::abs(double(g)),1e-30));}}}return d;}
std::vector<p51bench::EventRow> events(F&f){auto&e=f.e;if(e.tail)e.wait(0,e.tail);std::vector<p51bench::EventRow>v;
#ifndef OWN_RT_HOST_ONLY
 for(auto&p:e.pending)for(auto id=p.launch.first;id<=p.launch.last;++id){auto t=e.dev(0).timing(id);require(t.end_ns>t.start_ns&&t.end_ns-t.start_ns<4000000000ull,"bounded event");v.push_back({"class",t.start_ns,t.end_ns,id});}
#endif
 e.pending.clear();e.tail=0;e.dev(0).retire_completed_events();return v;}
void timing(std::ofstream&o,const Group&g,unsigned variant,unsigned pair_variant,unsigned m,unsigned row,unsigned iteration,const std::vector<p51bench::EventRow>&ev){uint64_t ns=0;for(auto&e:ev)ns+=e.end-e.start;o<<"{\"class\":"<<ownrt::quote(g.name)<<",\"variant\":"<<ownrt::quote(variant==p52::orders.size()?"control":p52::orders[variant].name)<<",\"pair_variant\":"<<ownrt::quote(p52::orders[pair_variant].name)<<",\"m\":"<<m<<",\"token_row\":"<<row<<",\"iteration\":"<<iteration<<",\"warmup\":"<<(iteration<10?"true":"false")<<",\"gpu_ns\":"<<ns<<",\"events\":[";for(size_t j=0;j<ev.size();++j)o<<(j?",":"")<<"{\"start_ns\":"<<ev[j].start<<",\"end_ns\":"<<ev[j].end<<"}";o<<"]}\n";}
}
int main(int argc,char**argv){using namespace p52bench;std::string mode,error;fs::path output;int card=-1;bool authorized=false,device_executed=false,safe=true;unsigned checks=0;std::unique_ptr<Engine>engine;std::vector<std::string>teardown;
 try{for(int i=1;i<argc;++i){std::string k=argv[i];auto v=[&]{require(i+1<argc,"argument value");return std::string(argv[++i]);};if(k=="--mode")mode=v();else if(k=="--output")output=v();else if(k=="--card")card=std::stoi(v());else if(k=="--authorized-device-window")authorized=true;else throw std::runtime_error("unknown argument "+k);}require(!output.empty()&&(mode=="cpu"||mode=="cpu-full"||mode=="exact"||mode=="timing"),"mode/output required");fs::create_directories(output);
#ifdef OWN_RT_HOST_ONLY
 require((mode=="cpu"||mode=="cpu-full")&&!authorized&&card==-1,"host build CPU only");
#else
 require((mode=="exact"||mode=="timing")&&authorized&&card==0,"coordinator card0 authorization required");
#endif
 std::signal(SIGTERM,stop);std::signal(SIGINT,stop);packet26::dispatch.load((p51bench::packet/"dispatch-baseline.json").string());Options a;a.mini=true;Weights w(a);a.mini=false;a.cards=2;a.context=4096;a.memory="resident";a.legacy=true;a.timing="class";a.seconds=1100;a.output=output;auto plan=p51bench::layer_plan(w,a,4);
 if(mode=="cpu"){
  // CPU preparation gates are bounded format/order tests at every real K. Full
  // production shapes are mirrored against the device only inside E windows.
  std::ofstream rows(output/"comparisons.jsonl");for(auto[type,k]:std::vector<std::pair<iq3::Type,unsigned>>{{iq3::Type::IQ2_S,2560},{iq3::Type::IQ4_NL,640},{iq3::Type::Q6_K,2560},{iq3::Type::Q6_K,6144},{iq3::Type::Q8_0,10240},{iq3::Type::Q8_0,320},{iq3::Type::F32,2560}}){p52::Spec s{type,k,3,1,1,unsigned(type==iq3::Type::IQ2_S||type==iq3::Type::IQ4_NL?p48::layout(type,k).row_bytes:arithmetic::row_bytes(type,k,type==iq3::Type::F32?0:6)),0,false};s.count=(type==iq3::Type::IQ2_S||type==iq3::Type::IQ4_NL)?2:1;s.experts=s.count;s.paired=type==iq3::Type::IQ2_S;s.epilogue=type==iq3::Type::Q8_0&&k==10240?1:type==iq3::Type::Q6_K&&k==6144?2:0;std::vector<uint8_t>weight(size_t(s.rows)*s.experts*s.rb);std::vector<uint16_t>x(k*(type==iq3::Type::IQ4_NL?s.count:1));for(unsigned i=0;i<x.size();++i)x[i]=iq3::bf16_bits(float(int(fixture46::mix(i)%257)-128)/1024);for(unsigned r=0;r<s.rows*s.experts;++r){auto p=weight.data()+r*s.rb;if(type==iq3::Type::F32){for(unsigned j=0;j<k;++j){float v=float(int(fixture46::mix(j+r*711)%33)-16)/8192;std::memcpy(p+j*4,&v,4);}}else if(type==iq3::Type::Q6_K||type==iq3::Type::Q8_0){for(unsigned j=0;j<k;++j)p[j]=uint8_t(fixture46::mix(j+r*711));for(unsigned j=0;j<k/(type==iq3::Type::Q6_K?16:32);++j){float v=.001f*float(j%7+1);std::memcpy(p+k+j*4,&v,4);}}else{for(unsigned j=0;j<s.rb;++j)p[j]=uint8_t(fixture46::mix(j+r*711));auto l=p48::layout(type,k);for(unsigned j=0;j<k/(type==iq3::Type::IQ2_S?256:32);++j){uint16_t h=0x0400+j%127;std::memcpy(p+l.halves+2*j,&h,2);}}}
   for(unsigned variant=0;variant<p52::orders.size();++variant){
    struct State {std::vector<uint16_t>y,py,out,streams;std::vector<uint32_t>status,peer_status;std::vector<float>scratch;};
    auto state=[&](){State t;t.y.resize(s.rows*s.count);t.py.resize(s.rows*s.count);t.out.resize(s.rows);t.streams.resize(s.rows*4);for(unsigned j=0;j<t.streams.size();++j)t.streams[j]=iq3::bf16_bits(float(int(j)-5)/32);t.status.resize(s.count);t.peer_status.resize(s.count);t.scratch.resize(p52::outputs(s)*4);return t;};
    auto expected=state(),actual=state();std::vector<iq3::Route>routes(s.count);for(unsigned slot=0;slot<s.count;++slot)routes[slot]={s.count-slot-1,0,s.rows};std::array<uint16_t,4>inject{0x3c00,0x3d00,0x3e00,0x3f00};
    auto bound=[&](State&t){return p52::Bound{s,weight.data(),weight.data(),x.data(),inject.data(),t.y.data(),t.py.data(),t.out.data(),t.streams.data(),routes.data(),t.status.data(),t.peer_status.data(),t.scratch.data()};};
    p52::mirror(bound(expected),p52::orders[variant]);p52::kernel_host(bound(actual),variant);
    auto bytes=[&](const State&t){std::vector<uint8_t>b;auto add=[&](const auto&v){auto ptr=reinterpret_cast<const uint8_t*>(v.data());b.insert(b.end(),ptr,ptr+v.size()*sizeof(v[0]));};add(t.y);add(t.py);add(t.out);add(t.streams);add(t.status);add(t.peer_status);add(t.scratch);return b;};auto reference=bytes(expected),result=bytes(actual);require(reference==result,"independent CPU traversal including outputs/epilogues/partials");
    rows<<"{\"type\":"<<int(type)<<",\"k\":"<<k<<",\"variant\":"<<ownrt::quote(p52::orders[variant].name)<<",\"sha256\":"<<ownrt::quote(hash(result))<<",\"cpu_sha256\":"<<ownrt::quote(hash(reference))<<",\"bytes\":"<<result.size()<<",\"equal\":true}\n";++checks;
   }
  }
 }else{
  engine=std::make_unique<Engine>(w,a,plan);auto&e=*engine;
#ifdef OWN_RT_HOST_ONLY
  e.devices.push_back(std::make_unique<ownrt::Device>(std::make_unique<Host>()));
#endif
#ifndef OWN_RT_HOST_ONLY
  {std::vector<sycl::device>cards;for(auto&p:sycl::platform::get_platforms())if(p.get_backend()==sycl::backend::ext_oneapi_level_zero)for(auto&d:p.get_devices(sycl::info::device_type::gpu))cards.push_back(d);require(!cards.empty()&&cards[0].get_info<sycl::ext::intel::info::device::pci_address>()=="0000:23:00.0","PCI card0 mismatch");}device_executed=true;e.devices.push_back(std::make_unique<ownrt::Device>(ownrt::make_sycl_device(0,true)));
#endif
  F f(e,4);f.setup();auto gs=groups(f);std::ofstream comparisons(output/"comparisons.jsonl"),iterations(output/"iterations.jsonl");
  std::array<F::Snapshot,4>snapshots;for(unsigned fixture=0;fixture<2;++fixture)for(unsigned row=0;row<2;++row){inputs(f,0x5200+fixture*97+row*7919);snapshots[fixture*2+row]=f.snapshot();}
  for(unsigned m:mode=="cpu-full"?std::vector<unsigned>{1}:std::vector<unsigned>{1,2})for(unsigned iteration=0;iteration<(mode=="timing"?210u:mode=="cpu-full"?1u:2u);++iteration)for(unsigned row=0;row<m;++row){e.guard();const auto&initial=snapshots[(iteration%2)*2+row];
   for(auto&g:gs){restore_group(f,g,initial);Capture baseline;if(mode=="exact"||mode=="cpu-full"){auto expected=exact_candidate(f,g,0,true);events(f);baseline=capture(f,g);check(baseline,expected);comparisons<<"{\"class\":"<<ownrt::quote(g.name)<<",\"variant\":\"control\",\"m\":"<<m<<",\"token_row\":"<<row<<",\"iteration\":"<<iteration<<",\"equal\":true,\"sha256\":"<<ownrt::quote(identity(baseline))<<",\"cpu_sha256\":"<<ownrt::quote(identity(expected))<<",\"buffers\":"<<baseline.size()<<",\"bytes\":"<<std::accumulate(baseline.begin(),baseline.end(),size_t(0),[](size_t n,const auto&v){return n+v.second.size();})<<",\"distance_information_only\":{\"elements\":0,\"differing\":0,\"max_absolute\":0,\"max_relative\":0}}\n";++checks;}
    if(mode=="exact"||mode=="cpu-full"){for(unsigned v=0;v<p52::orders.size();++v){restore_group(f,g,initial);auto expected=exact_candidate(f,g,v);events(f);auto actual=capture(f,g);check(actual,expected);auto diff=distance(actual,baseline);comparisons<<"{\"class\":"<<ownrt::quote(g.name)<<",\"variant\":"<<ownrt::quote(p52::orders[v].name)<<",\"m\":"<<m<<",\"token_row\":"<<row<<",\"iteration\":"<<iteration<<",\"equal\":true,\"sha256\":"<<ownrt::quote(identity(actual))<<",\"cpu_sha256\":"<<ownrt::quote(identity(expected))<<",\"buffers\":"<<actual.size()<<",\"bytes\":"<<std::accumulate(actual.begin(),actual.end(),size_t(0),[](size_t n,const auto&v){return n+v.second.size();})<<",\"distance_information_only\":{\"elements\":"<<diff.elements<<",\"differing\":"<<diff.differing<<",\"max_absolute\":"<<diff.max_absolute<<",\"max_relative\":"<<diff.max_relative<<"}}\n";++checks;}}
    else for(unsigned v=0;v<p52::orders.size();++v){for(unsigned arm=0;arm<2;++arm){bool candidate_arm=bool(arm)^bool(iteration%2);restore_group(f,g,initial);e.set_class(g.name);if(candidate_arm)candidate(f,g,v);else control(f,g);auto ev=events(f);timing(iterations,g,candidate_arm?v:p52::orders.size(),v,m,row,iteration,ev);}iterations.flush();}
   }
  }
  teardown=e.shutdown();engine.reset();
 }
 }catch(const std::exception&ex){error=ex.what();if(engine){try{teardown=engine->shutdown();}catch(...){safe=false;}engine.reset();}}
 std::ostringstream result;result<<"{\"schema\":\"ownrt.packet52.bench.v1\",\"passed\":"<<(error.empty()?"true":"false")<<",\"mode\":"<<ownrt::quote(mode)<<",\"cpu_mock\":"<<(mode=="cpu"||mode=="cpu-full"?"true":"false")<<",\"device_executed\":"<<(device_executed?"true":"false")<<",\"safe_to_exit\":"<<(safe?"true":"false")<<",\"checks\":"<<checks<<",\"error\":"<<ownrt::quote(error)<<"}";if(!output.empty())save(output/"receipt.json",result.str()+"\n");std::cout<<result.str()<<"\n";return error.empty()?0:1;
}
