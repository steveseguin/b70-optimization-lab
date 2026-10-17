#include "p51-bench.hpp"
#include "dense_virtual.hpp"
namespace p53bbench {
using F=p51bench::Fixture;
using Capture=std::map<std::string,std::vector<uint8_t>>;
struct DenseMember {const flash::Launch* launch;Matrix m;p39::Bound shape;std::array<Allocation,19> ids;bool low;};
struct Group {std::string name;size_t site{};Matrix m{};std::array<Allocation,10> ids{};std::vector<size_t> sites;std::vector<DenseMember> members;};
DenseMember dense_member(F&f,const flash::Launch&l){auto m=f.e.matrices.at(&l).at(0);auto c=packet26::Dispatch::class_name(l.label);bool low=c=="hc.a.low"||c=="hc.f.low";auto out=low?f.id(l.label.substr(0,l.label.size()-3)+"act"):m.y;
 p39::Bound b{};b.rows=m.rows;b.count=1;b.experts=1;b.capacity=f.e.p.g.context;b.rb=arithmetic::row_bytes(m.type,m.columns,f.e.variant(l));
 return {&l,m,b,{m.w,m.w,m.x,m.y,m.y,m.x,m.y,m.y,m.workspace,m.x,out,m.y,m.x,m.x,m.x,m.x,f.id("error"),f.id("active"),f.id("position")},low};
}
std::vector<Group> groups(F&f){std::vector<Group> out;for(size_t i=0;i<f.groups.size();++i){auto&l=f.e.p.launches[f.groups[i].first];auto cls=packet26::Dispatch::class_name(l.label);if(cls!="expsgate"&&cls!="expsdown")continue;auto&ms=f.e.matrices.at(&l);auto m=ms.at(0),peer=ms.size()==2?ms.at(1):m;require(m.count==10&&m.experts==512,"ten routes and512 experts");require((cls=="expsgate"&&m.columns==2560&&m.rows==640)||(cls=="expsdown"&&m.columns==640&&m.rows==2560),"production expert shapes");out.push_back({cls,i,m,{f.packed.at(l.weights[0]),f.packed.at(l.weights[ms.size()==2?1:0]),m.x,m.y,peer.y,m.routes,m.status,peer.status,f.id("error"),f.id("active")}});}require(out.size()==2,"two expert classes");
 Group hc;hc.name="hc.low_gate";Group small;small.name="small.ffn.q6";
 for(size_t i=0;i<f.groups.size();++i){auto&l=f.e.p.launches[f.groups[i].first];auto c=packet26::Dispatch::class_name(l.label);
  if(c=="hc.a.low"||c=="hc.a.gate"||c=="hc.f.low"||c=="hc.f.gate"){hc.sites.push_back(i);hc.members.push_back(dense_member(f,l));}
  if(c=="router"){require(f.e.small_groups.contains(&l),"production small tuple");small.sites.push_back(i);for(auto*member:f.e.small_groups.at(&l).members)small.members.push_back(dense_member(f,*member));}
 }
 require(hc.members.size()==4&&small.members.size()==4,"dense production member census");
 for(auto&m:hc.members)require(m.m.type==iq3::Type::Q8_0&&m.m.rows==(m.low?320u:10240u)&&m.m.columns==(m.low?10240u:320u)&&f.e.variant(*m.launch)==(m.low?7u:6u),"HC production geometry");
 auto shapes=packet27::small::shapes("small.ffn.q6");for(unsigned j=0;j<4;++j){auto&m=small.members[j];require(m.m.type==shapes[j].type&&m.m.rows==shapes[j].rows&&m.m.columns==shapes[j].columns&&f.e.variant(*m.launch)==shapes[j].variant,"small tuple geometry");}
 out.push_back(hc);out.push_back(small);return out;}
std::vector<unsigned> variants(const Group&g){return g.name=="hc.low_gate"?std::vector<unsigned>{0,1,2}:g.name=="small.ffn.q6"?std::vector<unsigned>{0,1}:std::vector<unsigned>{1,2,3};}
const char* variant_name(const Group&g,unsigned v){if(g.name=="expsgate"&&v==2)return "virtual8-split-stream";if(g.name=="expsgate"&&v==3)return "virtual16-split-stream";return p53b::variants.at(v).name;}
void inputs(F&f,unsigned seed){f.input(seed,4095);std::array<iq3::Route,10>routes{};std::array<uint32_t,10>ids{};for(unsigned j=0;j<10;++j){ids[j]=(seed*17+j*47)%512;routes[j]={ids[j],0,640};}f.e.upload(0,f.id(f.prefix+"ids"),0,ids.data(),40);for(const auto&[site,ms]:f.e.matrices)for(auto&m:ms)if(m.routes){for(auto&r:routes)r.row_count=m.rows;f.e.upload(0,m.routes,0,routes.data(),sizeof(routes));}f.routes();}
void restore(F&f,const Group&g,const F::Snapshot&s){std::set<Allocation>need{f.id("position")};if(g.members.empty()){for(unsigned i=2;i<10;++i)need.insert(g.ids[i]);}else for(auto&m:g.members)for(unsigned i=2;i<19;++i)need.insert(m.ids[i]);for(size_t i=0;i<f.mutable_ids.size();++i)if(need.contains(f.mutable_ids[i]))f.e.upload(0,f.mutable_ids[i],0,s[i].data(),s[i].size());f.e.fp32_sources[0]=0;}
void control(F&f,const Group&g){if(g.members.empty())f.execute(f.groups[g.site],false);else for(auto site:g.sites)f.execute(f.groups[site],g.name=="hc.low_gate");}
template<class Op>void issue(F&f,const Group&g,unsigned v){Op op;op.rows=g.m.rows;op.count=g.m.count;op.experts=g.m.experts;op.variant=v;auto ev=f.e.dev(0).compute(op,g.ids,{});f.e.finish(0,ev);}
template<unsigned V>void dense_candidate(F&f,const Group&g){
 if(g.name=="small.ffn.q6"){p53b::SmallKernel<V>op;std::vector<Allocation>ids;for(unsigned j=0;j<4;++j){op.shapes[j]=g.members[j].shape;for(unsigned k:{0u,2u,3u})ids.push_back(g.members[j].ids[k]);}auto ev=f.e.dev(0).compute(op,ids,{});f.e.finish(0,ev);}
 else for(auto&m:g.members){auto issue=[&]<unsigned K,unsigned Split,p39::Kind E>(){p53b::DenseKernel<iq3::Type::Q8_0,K,Split,V,E>op;op.shape=m.shape;auto ev=f.e.dev(0).compute(op,m.ids,{});f.e.finish(0,ev);};if(m.low)issue.template operator()<10240,4,p39::Kind::silu_div4>();else issue.template operator()<320,1,p39::Kind::expert_checks>();}
}
void candidate(F&f,const Group&g,unsigned v){if(g.name=="expsgate")issue<p53b::GateKernel>(f,g,v);else if(g.name=="expsdown")issue<p53b::DownKernel>(f,g,v);else if(v==0)dense_candidate<2>(f,g);else if(v==1)dense_candidate<4>(f,g);else if(v==2&&g.name=="hc.low_gate")dense_candidate<8>(f,g);else throw std::invalid_argument("dense variant");}
Capture capture(F&f,const Group&g){Capture c;
 if(!g.members.empty()){for(auto&m:g.members){c[std::to_string(m.ids[3])]=f.e.readback(0,m.ids[3],m.m.rows*2);if(m.low)c[std::to_string(m.ids[10])]=f.e.readback(0,m.ids[10],m.m.rows*2);}c[std::to_string(f.id("error"))]=f.e.readback(0,f.id("error"),4);return c;}auto add=[&](unsigned i,size_t n){c[std::to_string(g.ids[i])]=f.e.readback(0,g.ids[i],n);};add(3,g.m.rows*g.m.count*2);if(g.name=="expsgate")add(4,g.m.rows*g.m.count*2);add(6,g.m.count*4);if(g.name=="expsgate")add(7,g.m.count*4);add(8,4);return c;}
std::vector<uint8_t> slice(F&f,Allocation src,size_t offset,size_t n){auto&e=f.e;e.drain();std::vector<uint8_t>b(n);for(size_t i=0;i<n;i+=4*1024*1024){size_t take=std::min(n-i,size_t(4*1024*1024));ownrt::CopyEngine copy(e.dev(0));e.wait(0,copy.copy(e.slab[0],0,src,offset+i,take,{}));std::memcpy(b.data()+i,e.dev(0).arena.row(e.slab[0]).pointer,take);e.dev(0).retire_completed_events();}return b;}
template<iq3::Type T,unsigned K>Capture cpu_production(F&f,const Group&g){
 // Independent of the p53b lane virtualization/scheduler. Gather only the ten
 // selected experts, retaining the production row strides and scalar oracle.
 constexpr bool paired=T==iq3::Type::IQ2_S;size_t rb=p48::layout(T,K).row_bytes;auto route_bytes=f.e.readback(0,g.ids[5],g.m.count*sizeof(iq3::Route));std::vector<iq3::Route>routes(g.m.count);std::memcpy(routes.data(),route_bytes.data(),route_bytes.size());auto xb=f.e.readback(0,g.ids[2],K*(paired?1:g.m.count)*2);std::vector<uint16_t>x(xb.size()/2);std::memcpy(x.data(),xb.data(),xb.size());std::array<std::vector<uint16_t>,2>out;for(auto&v:out)v.resize(g.m.rows*g.m.count);std::vector<uint32_t>status(g.m.count);uint32_t error=0;
 for(unsigned slot=0;slot<g.m.count;++slot){auto r=routes[slot];require(iq3::valid_route(r,g.m.experts,g.m.rows,g.m.rows)&&r.row_begin==0&&r.row_count==g.m.rows,"registered complete valid route");auto w=slice(f,g.ids[0],size_t(r.expert_id)*g.m.rows*rb,g.m.rows*rb);auto peer=paired?slice(f,g.ids[1],size_t(r.expert_id)*g.m.rows*rb,g.m.rows*rb):std::vector<uint8_t>{};
  for(unsigned row=0;row<g.m.rows;++row){float lanes[2][32]{};for(unsigned lane=0;lane<32;++lane){if constexpr(paired){auto v=p48::gate_lane<T,K>(w.data()+row*rb,peer.data()+row*rb,x.data(),0,K,lane);lanes[0][lane]=v[0];lanes[1][lane]=v[1];}else lanes[0][lane]=p48::lane<T,K>(w.data()+row*rb,x.data()+slot*K,0,K,lane);}out[0][slot*g.m.rows+row]=iq3::bf16_bits(iq3::tree32(lanes[0]));if constexpr(paired)out[1][slot*g.m.rows+row]=iq3::bf16_bits(iq3::tree32(lanes[1]));}
 }
 Capture result;auto add=[&](unsigned i,const void*p,size_t n){auto*b=static_cast<const uint8_t*>(p);result[std::to_string(g.ids[i])]=std::vector<uint8_t>(b,b+n);};add(3,out[0].data(),out[0].size()*2);if constexpr(paired)add(4,out[1].data(),out[1].size()*2);add(6,status.data(),status.size()*4);if constexpr(paired)add(7,status.data(),status.size()*4);add(8,&error,4);return result;
}
Capture dense_expected(F&f,const Group&g){
 Capture result;uint32_t error=0,active=1,position=4095;
 for(auto&m:g.members){auto w=slice(f,m.ids[0],0,size_t(m.m.rows)*m.shape.rb);auto key=std::to_string(m.ids[2]);auto xb=result.contains(key)?result.at(key):f.e.readback(0,m.ids[2],m.m.columns*2);
  std::vector<uint16_t>x(xb.size()/2),y(m.m.rows),act(m.m.rows);std::memcpy(x.data(),xb.data(),xb.size());
  unsigned split=f.e.variant(*m.launch)==6?1:4;
  for(unsigned row=0;row<m.m.rows;++row){float partial[4]{};for(unsigned part=0;part<split;++part){auto bounds=iq3::kopt2::bounds(m.m.columns,part,split);float lanes[32];for(unsigned l=0;l<32;++l){auto*wr=w.data()+size_t(row)*m.shape.rb;lanes[l]=m.m.type==iq3::Type::F32?iq3::kopt2::lane_range<iq3::Type::F32>(wr,x.data(),iq3::Type::BF16,bounds.first,bounds.second,l):iq3::expanded::lane(m.m.type,wr,x.data(),iq3::Type::BF16,m.m.columns,bounds.first,bounds.second,l);}partial[part]=iq3::tree32(lanes);}y[row]=iq3::bf16_bits(split==1?partial[0]:(partial[0]+partial[1])+(partial[2]+partial[3]));
   if(m.low){auto b=m.shape;b.out=act.data();b.active=&active;b.error=&error;b.position=&position;p51::dense_tail_host<p39::Kind::silu_div4>(b,row,y[row]);}}
  auto add=[&](Allocation id,const auto&v){auto*p=reinterpret_cast<const uint8_t*>(v.data());result[std::to_string(id)]=std::vector<uint8_t>(p,p+v.size()*sizeof(v[0]));};add(m.ids[3],y);if(m.low)add(m.ids[10],act);
 }
 auto*p=reinterpret_cast<const uint8_t*>(&error);result[std::to_string(f.id("error"))]=std::vector<uint8_t>(p,p+4);return result;
}
Capture expected(F&f,const Group&g){if(!g.members.empty())return dense_expected(f,g);return g.name=="expsgate"?cpu_production<iq3::Type::IQ2_S,2560>(f,g):cpu_production<iq3::Type::IQ4_NL,640>(f,g);}
std::string identity(const Capture&c){std::vector<uint8_t>b;for(auto&[n,v]:c){b.insert(b.end(),n.begin(),n.end());b.insert(b.end(),v.begin(),v.end());}return hash(b);}
void check(const Capture&a,const Capture&b){p51bench::compare_maps(a,b,"p53b production identity");}
std::vector<p51bench::EventRow> events(F&f){auto&e=f.e;if(e.tail)e.wait(0,e.tail);std::vector<p51bench::EventRow>v;
#ifndef OWN_RT_HOST_ONLY
 for(auto&p:e.pending)for(auto id=p.launch.first;id<=p.launch.last;++id){auto t=e.dev(0).timing(id);require(t.end_ns>t.start_ns&&t.end_ns-t.start_ns<4000000000ull,"bounded event");v.push_back({"class",t.start_ns,t.end_ns,id});}
#endif
 e.pending.clear();e.tail=0;e.dev(0).retire_completed_events();return v;}
void comparison(std::ofstream&o,const Group&g,const char*v,unsigned m,unsigned row,unsigned iteration,const Capture&actual,const Capture&cpu,const Capture&production){check(actual,cpu);check(actual,production);o<<"{\"class\":"<<ownrt::quote(g.name)<<",\"variant\":"<<ownrt::quote(v)<<",\"m\":"<<m<<",\"token_row\":"<<row<<",\"iteration\":"<<iteration<<",\"equal\":true,\"production_equal\":true,\"sha256\":"<<ownrt::quote(identity(actual))<<",\"cpu_sha256\":"<<ownrt::quote(identity(cpu))<<",\"production_sha256\":"<<ownrt::quote(identity(production))<<",\"buffers\":"<<actual.size()<<",\"bytes\":"<<std::accumulate(actual.begin(),actual.end(),size_t(0),[](size_t n,const auto&v){return n+v.second.size();})<<"}\n";}
void timing(std::ofstream&o,const Group&g,unsigned variant,unsigned pair_variant,unsigned m,unsigned row,unsigned iteration,const std::vector<p51bench::EventRow>&ev){uint64_t ns=0;for(auto&e:ev)ns+=e.end-e.start;o<<"{\"class\":"<<ownrt::quote(g.name)<<",\"variant\":"<<ownrt::quote(variant==p53b::variants.size()?"control":variant_name(g,variant))<<",\"pair_variant\":"<<ownrt::quote(variant_name(g,pair_variant))<<",\"m\":"<<m<<",\"token_row\":"<<row<<",\"iteration\":"<<iteration<<",\"warmup\":"<<(iteration<10?"true":"false")<<",\"gpu_ns\":"<<ns<<",\"events\":[";for(size_t j=0;j<ev.size();++j)o<<(j?",":"")<<"{\"start_ns\":"<<ev[j].start<<",\"end_ns\":"<<ev[j].end<<"}";o<<"]}\n";}
}
int main(int argc,char**argv){using namespace p53bbench;std::string mode,error;fs::path output;int card=-1;bool authorized=false,device_executed=false,safe=true;unsigned checks=0;std::unique_ptr<Engine>engine;std::vector<std::string>teardown;
 try{for(int i=1;i<argc;++i){std::string k=argv[i];auto v=[&]{require(i+1<argc,"argument value");return std::string(argv[++i]);};if(k=="--mode")mode=v();else if(k=="--output")output=v();else if(k=="--card")card=std::stoi(v());else if(k=="--authorized-device-window")authorized=true;else throw std::runtime_error("unknown argument "+k);}require(!output.empty()&&(mode=="cpu-full"||mode=="exact"||mode=="timing"),"mode/output required");fs::create_directories(output);
#ifdef OWN_RT_HOST_ONLY
 require(mode=="cpu-full"&&!authorized&&card==-1,"host build CPU only");
#else
 require((mode=="exact"||mode=="timing")&&authorized&&card==0,"coordinator card0 authorization required");
#endif
 std::signal(SIGTERM,stop);std::signal(SIGINT,stop);packet26::dispatch.load((p51bench::packet/"dispatch-baseline.json").string());Options a;a.mini=true;Weights w(a);a.mini=false;a.cards=2;a.context=4096;a.memory="resident";a.legacy=true;a.timing="class";a.seconds=2820;a.output=output;auto plan=p51bench::layer_plan(w,a,4);
 engine=std::make_unique<Engine>(w,a,plan);auto&e=*engine;
#ifdef OWN_RT_HOST_ONLY
 e.devices.push_back(std::make_unique<ownrt::Device>(std::make_unique<Host>()));
#else
 {std::vector<sycl::device>cards;for(auto&p:sycl::platform::get_platforms())if(p.get_backend()==sycl::backend::ext_oneapi_level_zero)for(auto&d:p.get_devices(sycl::info::device_type::gpu))cards.push_back(d);require(!cards.empty()&&cards[0].get_info<sycl::ext::intel::info::device::pci_address>()=="0000:23:00.0","PCI card0 mismatch");}device_executed=true;e.devices.push_back(std::make_unique<ownrt::Device>(ownrt::make_sycl_device(0,true)));
#endif
 F f(e,4);f.setup();auto gs=groups(f);std::ofstream comparisons(output/"comparisons.jsonl"),iterations(output/"iterations.jsonl");std::array<F::Snapshot,4>snapshots;for(unsigned fixture=0;fixture<2;++fixture)for(unsigned row=0;row<2;++row){inputs(f,0x5300+fixture*97+row*7919);snapshots[fixture*2+row]=f.snapshot();}
 for(unsigned m:mode=="cpu-full"?std::vector<unsigned>{1}:std::vector<unsigned>{1,2})for(unsigned iteration=0;iteration<(mode=="timing"?210u:mode=="cpu-full"?1u:2u);++iteration)for(unsigned row=0;row<m;++row){e.guard();auto&initial=snapshots[(iteration%2)*2+row];for(auto&g:gs){restore(f,g,initial);if(mode!="timing"){auto cpu=expected(f,g);control(f,g);events(f);auto baseline=capture(f,g);comparison(comparisons,g,"control",m,row,iteration,baseline,cpu,baseline);++checks;for(auto v:variants(g)){restore(f,g,initial);candidate(f,g,v);events(f);auto actual=capture(f,g);comparison(comparisons,g,variant_name(g,v),m,row,iteration,actual,cpu,baseline);++checks;}}
 else for(auto v:variants(g)){for(unsigned arm=0;arm<2;++arm){bool ca=bool(arm)^bool(iteration%2);restore(f,g,initial);e.set_class(g.name);if(ca)candidate(f,g,v);else control(f,g);auto ev=events(f);timing(iterations,g,ca?v:p53b::variants.size(),v,m,row,iteration,ev);}iterations.flush();}}
 }
 teardown=e.shutdown();engine.reset();
 }catch(const std::exception&ex){error=ex.what();if(engine){try{teardown=engine->shutdown();}catch(...){safe=false;}engine.reset();}}
 std::ostringstream result;result<<"{\"schema\":\"ownrt.packet53b.bench.v1\",\"passed\":"<<(error.empty()?"true":"false")<<",\"mode\":"<<ownrt::quote(mode)<<",\"cpu_mock\":"<<(mode=="cpu-full"?"true":"false")<<",\"device_executed\":"<<(device_executed?"true":"false")<<",\"safe_to_exit\":"<<(safe?"true":"false")<<",\"checks\":"<<checks<<",\"error\":"<<ownrt::quote(error)<<"}";if(!output.empty())save(output/"receipt.json",result.str()+"\n");std::cout<<result.str()<<"\n";return error.empty()?0:1;
}
