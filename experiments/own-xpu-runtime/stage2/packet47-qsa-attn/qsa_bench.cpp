#include "qsa_kernel.hpp"
#include "qsa_reference.hpp"
#include "qgate.hpp"
#include <sycl/ext/oneapi/backend/level_zero.hpp>
#include <level_zero/ze_api.h>
#include <openssl/sha.h>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <csignal>
#include <memory>
#include <set>
#include <map>
namespace fs=std::filesystem;
static volatile std::sig_atomic_t interrupted=0;
static void stop(int){interrupted=1;}
static void require(bool b,const std::string&s){if(!b)throw std::runtime_error(s);}
static std::string quote(const std::string&s){std::string o="\"";for(char c:s){if(c=='\"'||c=='\\')o+='\\';if(c=='\n'){o+="\\n";continue;}o+=c;}return o+'\"';}
static std::string hash(const void*p,size_t n){unsigned char out[32];SHA256(static_cast<const unsigned char*>(p),n,out);std::ostringstream s;for(auto c:out)s<<std::hex<<std::setw(2)<<std::setfill('0')<<unsigned(c);return s.str();}
struct Buffers {
 sycl::queue&q;std::vector<void*>all;
 explicit Buffers(sycl::queue&v):q(v){}~Buffers(){q.wait();for(void*p:all)sycl::free(p,q);}
 template<class T>T* alloc(size_t count){T*p=sycl::malloc_device<T>(count,q);if(!p)throw std::bad_alloc();all.push_back(p);return p;}
 ng::Args args(const p47ref::Fixture&f){ng::Args a;for(int j=0;j<19;++j){a.p[j]=alloc<uint32_t>(f.data[j].size());q.memcpy(a.p[j],f.data[j].data(),f.data[j].size()*4);}q.wait_and_throw();return a;}
};
static void upload(sycl::queue&q,ng::Args a,const p47ref::Fixture&f){for(int j=0;j<19;++j)q.memcpy(a.p[j],f.data[j].data(),f.data[j].size()*4);q.wait_and_throw();}
static std::vector<uint8_t> read(sycl::queue&q,const void*p,size_t n){std::vector<uint8_t>b(n);q.memcpy(b.data(),p,n).wait_and_throw();return b;}
static void comparison(std::ofstream&out,sycl::queue&q,const void*actual,const void*expected,size_t n,int context,int rows,int seed,const std::string&variant,const std::string&buffer,const std::string&control="normal"){
 auto b=read(q,actual,n);bool same=std::memcmp(b.data(),expected,n)==0;
 size_t first_mismatch=0;while(first_mismatch<n&&b[first_mismatch]==static_cast<const uint8_t*>(expected)[first_mismatch])++first_mismatch;
 out<<"{\"context\":"<<context<<",\"rows\":"<<rows<<",\"seed\":"<<seed<<",\"variant\":"<<quote(variant)<<",\"buffer\":"<<quote(buffer)<<",\"control\":"<<quote(control)<<",\"bytes\":"<<n<<",\"equal\":"<<(same?"true":"false")<<",\"sha256\":"<<quote(hash(b.data(),n))<<",\"expected_sha256\":"<<quote(hash(expected,n))<<",\"first_mismatch_byte\":"<<(same?-1:static_cast<long long>(first_mismatch))<<",\"actual_byte\":"<<(same?-1:int(b[first_mismatch]))<<",\"expected_byte\":"<<(same?-1:int(static_cast<const uint8_t*>(expected)[first_mismatch]))<<"}\n";out.flush();require(bool(out),"comparison write");require(same,"exact mismatch "+variant+" "+buffer+" context="+std::to_string(context)+" rows="+std::to_string(rows)+" control="+control);
}
static void readonly_comparison(std::ofstream&out,sycl::queue&q,ng::Args a,const p47ref::Fixture&f,int seed,const std::string&variant){
 std::vector<uint8_t>actual,expected;for(int slot:{0,1,2,3,4,17,18}){auto bytes=read(q,a.p[slot],f.data[slot].size()*4);actual.insert(actual.end(),bytes.begin(),bytes.end());auto*p=reinterpret_cast<const uint8_t*>(f.data[slot].data());expected.insert(expected.end(),p,p+bytes.size());}bool same=actual==expected;out<<"{\"context\":"<<f.shape.capacity<<",\"rows\":"<<f.shape.tokens<<",\"seed\":"<<seed<<",\"variant\":"<<quote(variant)<<",\"buffer\":\"readonly.input\",\"control\":\"normal\",\"bytes\":"<<actual.size()<<",\"equal\":"<<(same?"true":"false")<<",\"sha256\":"<<quote(hash(actual.data(),actual.size()))<<",\"expected_sha256\":"<<quote(hash(expected.data(),expected.size()))<<"}\n";out.flush();require(same,"readonly input changed");
}
static std::vector<sycl::event> attention(sycl::queue&q,ng::Shape s,ng::Args a,int*counts,float*partial,const int*positions,int variant){if(variant==0)return p47::current(q,s,a,positions);return p47::candidate(q,s,a,counts,partial,variant==2);}
static const char*name(int v){return v==0?"current":v==1?"ordered":"split32";}
struct Side {
 std::array<std::vector<uint32_t>,19> data;ng::Shape shape;ng::Args a{};float*scratch;
 Side(Buffers&b,ng::Shape s):shape(s){shape.op=ng::select;auto sizes=ng::required_bytes(shape);sizes[16]=4;for(int i=0;i<19;++i){data[i].resize((sizes[i]+3)/4);a.p[i]=b.alloc<uint32_t>(data[i].size());}scratch=b.alloc<float>(round2::scratch_floats(shape));}
 ng::Args host(){ng::Args h;for(int i=0;i<19;++i)h.p[i]=data[i].data();return h;}
 void input(sycl::queue&q,int seed){auto h=host();std::fill_n(h.i(2),shape.tokens*2051,-777);for(int slot:{0,1})for(size_t j=0;j<data[slot].size()*2;++j)h.put(slot,j,float(int((j*17+seed*13+slot*11)%257)-128)/128.f);h.i(15)[0]=0;h.i(17)[0]=shape.capacity-shape.tokens;h.i(18)[0]=1;for(int i=0;i<19;++i)q.memcpy(a.p[i],data[i].data(),data[i].size()*4);q.wait_and_throw();}
};
struct Timing {std::string cls;sycl::event event;};
static void timing(std::ofstream&out,int context,int rows,int iteration,int variant,const std::vector<Timing>&events){std::map<std::string,uint64_t>classes;uint64_t total=0;std::ostringstream es;es<<'[';for(size_t i=0;i<events.size();++i){auto&e=events[i];uint64_t start=e.event.get_profiling_info<sycl::info::event_profiling::command_start>(),end=e.event.get_profiling_info<sycl::info::event_profiling::command_end>();require(start&&end>start&&end-start<4000000000ull,"bounded nonempty event");classes[e.cls]+=end-start;total+=end-start;es<<(i?",":"")<<"{\"id\":"<<i+1<<",\"class\":"<<quote(e.cls)<<",\"start_ns\":"<<start<<",\"end_ns\":"<<end<<"}";}es<<']';out<<"{\"context\":"<<context<<",\"rows\":"<<rows<<",\"iteration\":"<<iteration<<",\"seed\":"<<18176+iteration%2<<",\"variant\":"<<quote(name(variant))<<",\"warmup\":"<<(iteration<10?"true":"false")<<",\"exact\":true,\"submissions\":"<<events.size()<<",\"gpu_ns\":"<<total<<",\"classes_ns\":{";bool first=true;for(auto&[cls,t]:classes){out<<(first?"":",")<<quote(cls)<<':'<<t;first=false;}out<<"},\"events\":"<<es.str()<<"}\n";out.flush();require(bool(out),"timing write");}
int main(int argc,char**argv){std::string mode,error,pci;fs::path output;int card=-1;bool authorized=false,executed=false,safe=false;size_t checks=0,pairs=0;std::unique_ptr<sycl::queue>queue;
 try{for(int i=1;i<argc;++i){std::string k=argv[i];auto value=[&]{require(i+1<argc,"missing argument");return std::string(argv[++i]);};if(k=="--mode")mode=value();else if(k=="--output")output=value();else if(k=="--card")card=std::stoi(value());else if(k=="--authorized-device-window")authorized=true;else throw std::runtime_error("unknown argument "+k);}
 require(authorized&&card==0&&!output.empty()&&(mode=="exact"||mode=="timing"),"explicit card0 exact/timing window required");
 require(getenv("ONEAPI_DEVICE_SELECTOR")&&std::string(getenv("ONEAPI_DEVICE_SELECTOR"))=="level_zero:0","ONEAPI_DEVICE_SELECTOR=level_zero:0 required");
 fs::create_directories(output);std::signal(SIGTERM,stop);std::signal(SIGINT,stop);
 executed=true;queue=std::make_unique<sycl::queue>(sycl::gpu_selector_v,sycl::property_list{sycl::property::queue::in_order{},sycl::property::queue::enable_profiling{}});auto&q=*queue;
 require(q.get_device().get_info<sycl::info::device::name>().find("B70")!=std::string::npos,"B70 required");
 ze_pci_ext_properties_t props{};props.stype=ZE_STRUCTURE_TYPE_PCI_EXT_PROPERTIES;require(zeDevicePciGetPropertiesExt(sycl::get_native<sycl::backend::ext_oneapi_level_zero>(q.get_device()),&props)==ZE_RESULT_SUCCESS,"PCI identity query");std::ostringstream address;address<<std::hex<<std::setfill('0')<<std::setw(4)<<props.address.domain<<':'<<std::setw(2)<<props.address.bus<<':'<<std::setw(2)<<props.address.device<<'.'<<props.address.function;pci=address.str();require(fs::canonical("/sys/class/drm/card0/device").filename().string()==pci,"selected device is not physical DRM card0");
 std::ofstream comparisons(output/"comparisons.jsonl"),timings(output/"iterations.jsonl"),diagnostics(output/"differences.jsonl");require(comparisons&&timings&&diagnostics,"output streams");
 auto weights=p47gate::weights();Buffers permanent(q);auto*w=permanent.alloc<uint8_t>(weights.size());q.memcpy(w,weights.data(),weights.size()).wait_and_throw();
 std::vector<int>contexts{1024,2048,4096,8192,32768};if(mode=="exact")contexts.insert(contexts.end(),{1027,2051,4099});
 for(int context:contexts)for(int rows:{1,2}){
  Buffers b(q);p47ref::Fixture initial(context,rows,18176);ng::Args a=b.args(initial);auto*counts=b.alloc<int>(rows);auto*partial=b.alloc<float>(p47::scratch_floats(initial.shape));auto*positions=b.alloc<int>(rows);std::vector<int>pos(rows);for(int r=0;r<rows;++r)pos[r]=context-rows+r;q.memcpy(positions,pos.data(),rows*4).wait_and_throw();Side select(b,initial.shape);
  auto*gx=b.alloc<uint16_t>(rows*p47gate::cols);auto*gy=b.alloc<uint16_t>(rows*p47gate::rows);std::vector<uint16_t>x(rows*p47gate::cols),y(rows*p47gate::rows);
  std::array<std::vector<uint8_t>,2> timing_old,timing_split,timing_select,timing_gate;
  if(mode=="timing")for(int seed_index=0;seed_index<2;++seed_index){int seed=18176+seed_index;p47ref::Fixture f(context,rows,seed);std::fill(f.data[5].begin(),f.data[5].end(),0xcdcdcdcdu);auto old=f,split=f;select.input(q,seed);ng::cpu(select.shape,select.host());std::memcpy(f.args().p[4],select.host().p[2],rows*2051*4);old=f;split=f;p47ref::cpu_old(old.shape,old.args());p47ref::cpu_split(split.shape,split.args());auto capture=[&](auto&to,const void*p,size_t n){auto*b=static_cast<const uint8_t*>(p);to.assign(b,b+n);};capture(timing_old[seed_index],old.data[5].data(),rows*6144*2);capture(timing_split[seed_index],split.data[5].data(),rows*6144*2);select.input(q,seed);ng::cpu(select.shape,select.host());capture(timing_select[seed_index],select.host().p[2],rows*2051*4);for(size_t k=0;k<x.size();++k)x[k]=ng::Args::bits(float(int((k*19+seed*11)%257)-128)/128.f);p47gate::cpu(weights.data(),x.data(),y.data(),rows);capture(timing_gate[seed_index],y.data(),y.size()*2);}
  int iterations=mode=="exact"?2:210;
  for(int it=0;it<iterations;++it){require(!interrupted,"interrupted between bounded iterations");int seed=18176+it%2;
   // Alternate two changing, CPU-qualified synthetic fixtures. These are
   // operator timings, never cached-prompt or whole-model performance claims.
   p47ref::Fixture fixture(context,rows,seed);std::fill(fixture.data[5].begin(),fixture.data[5].end(),0xcdcdcdcdu);auto host=fixture.args();
   for(size_t k=0;k<x.size();++k)x[k]=ng::Args::bits(float(int((k*19+seed*11)%257)-128)/128.f);q.memcpy(gx,x.data(),x.size()*2).wait_and_throw();select.input(q,seed);
   if(mode=="exact"){
    auto se=p47::selection(q,select.shape,select.a,select.scratch);se.back().wait_and_throw();auto sh=select.host();ng::cpu(select.shape,sh);comparison(comparisons,q,select.a.p[2],sh.p[2],size_t(rows)*2051*4,context,rows,seed,"current","selection.ids");++checks;std::memcpy(fixture.args().p[4],sh.p[2],rows*2051*4);
    auto old=fixture,split=fixture;p47ref::cpu_old(old.shape,old.args());p47ref::cpu_split(split.shape,split.args());
    for(int variant=0;variant<3;++variant){upload(q,a,fixture);auto e=attention(q,fixture.shape,a,counts,partial,positions,variant);e.back().wait_and_throw();auto&expected=variant==2?split:old;comparison(comparisons,q,a.p[5],expected.data[5].data(),size_t(rows)*6144*2,context,rows,seed,name(variant),"attention.output");++checks;readonly_comparison(comparisons,q,a,fixture,seed,name(variant));++checks;auto err=read(q,a.p[15],4);require(*reinterpret_cast<const int*>(err.data())==0,"attention error");}
    auto ha=old.args(),hb=split.args();size_t changed=0;uint32_t maxulp=0;float maxabs=0;auto ordered=[](uint16_t v){return (v&0x8000)?uint32_t(0x8000-(v&0x7fff)):uint32_t(0x8000+v);};for(int k=0;k<rows*6144;++k){auto u=static_cast<uint16_t*>(ha.p[5])[k],v=static_cast<uint16_t*>(hb.p[5])[k];changed+=u!=v;auto ou=ordered(u),ov=ordered(v);maxulp=std::max(maxulp,ou>ov?ou-ov:ov-ou);maxabs=std::max(maxabs,std::abs(ha.b(5,k)-hb.b(5,k)));}diagnostics<<"{\"context\":"<<context<<",\"rows\":"<<rows<<",\"seed\":"<<seed<<",\"boundary\":\"BF16 gated attention output; logits not measured\",\"changed\":"<<changed<<",\"max_bf16_ulp\":"<<maxulp<<",\"max_abs\":"<<std::setprecision(9)<<maxabs<<"}\n";
    p47gate::cpu(weights.data(),x.data(),y.data(),rows);q.memset(gy,0xCD,y.size()*2).wait_and_throw();p47gate::submit(q,w,gx,gy,rows).wait_and_throw();comparison(comparisons,q,gy,y.data(),y.size()*2,context,rows,seed,"current","qgate.output");++checks;
   }else {
    std::memcpy(fixture.args().p[4],timing_select[it%2].data(),rows*2051*4);
    std::vector<uint8_t>old_output;for(int step=0;step<3;++step){int variant=(it/2)%2?2-step:step;upload(q,a,fixture);select.input(q,seed);q.memset(gy,0xCD,y.size()*2).wait_and_throw();std::vector<Timing>events;for(auto e:attention(q,fixture.shape,a,counts,partial,positions,variant))events.push_back({"qsa.attention",e});for(auto e:p47::selection(q,select.shape,select.a,select.scratch))events.push_back({"qsa.select",e});events.push_back({"qsa.qgate",p47gate::submit(q,w,gx,gy,rows)});q.wait_and_throw();auto actual=read(q,a.p[5],size_t(rows)*6144*2);require(actual==(variant==2?timing_split[it%2]:timing_old[it%2]),"timing CPU attention exactness");require(read(q,select.a.p[2],size_t(rows)*2051*4)==timing_select[it%2],"timing CPU selection exactness");require(read(q,gy,size_t(rows)*p47gate::rows*2)==timing_gate[it%2],"timing CPU qgate exactness");timing(timings,context,rows,it,variant,events);auto err=read(q,a.p[15],4);require(*reinterpret_cast<const int*>(err.data())==0,"timing attention error");auto serr=read(q,select.a.p[15],4);require(*reinterpret_cast<const int*>(serr.data())==0,"timing selection error");if(variant!=2){auto bytes=read(q,a.p[5],size_t(rows)*6144*2);if(old_output.empty())old_output=std::move(bytes);else{require(bytes==old_output,"timing ordered/current parity");++pairs;}}}
   }
  }
 }
 if(mode=="exact")for(int rows:{1,2})for(std::string control:{"inactive","sticky-error","invalid-position","invalid-id","empty"}){
  int context=4096,seed=18176;Buffers b(q);p47ref::Fixture fixture(context,rows,seed);std::fill(fixture.data[5].begin(),fixture.data[5].end(),0xcdcdcdcdu);auto host=fixture.args();int expected_error=0;
  if(control=="inactive")host.i(18)[0]=0;else if(control=="sticky-error"){host.i(15)[0]=1;expected_error=1;}else if(control=="invalid-position"){host.i(17)[0]=context;expected_error=1;}else if(control=="invalid-id"){host.i(4)[0]=context;expected_error=1;}else std::fill_n(host.i(4),rows*2051,-1);
  ng::Args a=b.args(fixture);auto*counts=b.alloc<int>(rows);auto*partial=b.alloc<float>(p47::scratch_floats(fixture.shape));auto*positions=b.alloc<int>(rows);std::vector<int>pos(rows);for(int r=0;r<rows;++r)pos[r]=host.i(17)[0]+r;q.memcpy(positions,pos.data(),rows*4).wait_and_throw();
  for(int variant=0;variant<3;++variant){upload(q,a,fixture);attention(q,fixture.shape,a,counts,partial,positions,variant).back().wait_and_throw();comparison(comparisons,q,a.p[5],fixture.data[5].data(),size_t(rows)*6144*2,context,rows,seed,name(variant),"attention.output",control);comparison(comparisons,q,a.p[15],&expected_error,4,context,rows,seed,name(variant),"error",control);checks+=2;}
 }
 q.wait_and_throw();safe=true;
 }catch(const std::exception&ex){error=ex.what();if(queue){try{queue->wait_and_throw();safe=true;}catch(...){safe=false;}}else safe=true;}
 std::ostringstream receipt;receipt<<"{\"schema\":\"ownrt.packet47.qsa.v1\",\"passed\":"<<(error.empty()?"true":"false")<<",\"mode\":"<<quote(mode)<<",\"cpu_mock\":false,\"device_executed\":"<<(executed?"true":"false")<<",\"safe_to_exit\":"<<(safe?"true":"false")<<",\"card\":"<<card<<",\"pci_bdf\":"<<quote(pci)<<",\"checks\":"<<checks<<",\"timing_pair_checks\":"<<pairs<<",\"error\":"<<quote(error)<<"}";
 if(!output.empty()){std::ofstream f(output/"receipt.json");f<<receipt.str()<<'\n';}std::cout<<receipt.str()<<'\n';return error.empty()?0:1;
}
