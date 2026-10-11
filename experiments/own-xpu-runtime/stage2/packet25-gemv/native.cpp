#include "device.hpp"
#include "timing_loop.hpp"
#include "exactness.hpp"
#include <chrono>
#include <csignal>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <thread>
#include <memory>
#include <map>
namespace fs=std::filesystem;
using namespace p25;
static volatile std::sig_atomic_t stopped=0;
static void stop(int){stopped=1;return;}
void require(bool condition,const std::string& why){if(!condition)throw std::runtime_error(why);return;}
std::string quote(const std::string&s){std::string o="\"";for(char c:s){if(c=='"'||c=='\\')o+='\\';if(c=='\n'){o+="\\n";continue;}o+=c;}return o+'"';}
struct Owner {
 sycl::queue q;std::vector<void*> allocations;sycl::event tail;bool submitted=false;size_t live=0;
 explicit Owner(unsigned card):q([&]{std::vector<sycl::device> gpu;for(auto p:sycl::platform::get_platforms())if(p.get_backend()==sycl::backend::ext_oneapi_level_zero)for(auto d:p.get_devices(sycl::info::device_type::gpu))gpu.push_back(d);require(card<gpu.size(),"physical card unavailable");return gpu[card];}(),sycl::property_list{sycl::property::queue::in_order{},sycl::property::queue::enable_profiling{}}){}
 template<class T>T* allocate(size_t n){require(n&&n<=size_t(2)*1024*1024*1024/sizeof(T),"allocation bound");size_t bytes=n*sizeof(T);require(live+bytes<size_t(4)*1024*1024*1024,"owner 4 GiB bound");auto p=sycl::malloc_device<T>(n,q);require(p!=nullptr,"device allocation failed");allocations.push_back(p);live+=bytes;return p;}
 template<class T>T* upload(const std::vector<T>& v){auto p=allocate<T>(v.size());tail=q.memcpy(p,v.data(),v.size()*sizeof(T));submitted=true;tail.wait_and_throw();return p;}
 void track(const Events&e){tail=e.event[e.count-1];submitted=true;return;}
 void finish(){q.wait_and_throw();return;}
 void release(){finish();for(auto p:allocations)sycl::free(p,q);allocations.clear();live=0;return;}
};
struct Case {
 Shape shape;Params host{};Params* params;std::vector<Result> oracle;std::vector<Result> actual;std::vector<uint16_t> input;
 Case(Owner&o,Shape s,unsigned special=0,unsigned mode=0):shape(s){
 auto a=seed_weights(s.type,s.k,0,special),b=seed_weights(s.type,s.k,937,special);auto x=inputs(s.k,s.count,mode);input=x;oracle=expected(s,a,b,x);actual.resize(oracle.size());
 auto f=layout(s.type);size_t prb=s.k/f.elements*f.bytes,rb=expert(s.type)?prb:expanded::row_bytes(s.type,s.k);
 auto wa=expert(s.type)?a:expanded::expand(s.type,a.data(),a.size(),s.k),wb=expert(s.type)?b:expanded::expand(s.type,b.data(),b.size(),s.k);
 size_t n=size_t(s.rows)*s.count;std::vector<uint8_t> tiled(n*rb);for(size_t r=0;r<n;++r)std::memcpy(tiled.data()+r*rb,wa.data()+(r%8)*rb,rb);host.w=o.upload(tiled);
 if(s.paired){for(size_t r=0;r<n;++r)std::memcpy(tiled.data()+r*rb,wb.data()+(r%8)*rb,rb);host.peer=o.upload(tiled);}else host.peer=host.w;
 host.x=o.upload(x);host.y=o.allocate<Result>(n);host.routes=o.upload(std::vector<unsigned>(routes,routes+10));
 host.erb=expanded::row_bytes(s.type,s.k);host.rb=rb;host.rows=s.rows;host.k=s.k;host.count=s.count;host.split=s.split;host.paired=s.paired;host.exceptional=exceptional(s.type,a.data(),a.size(),x.data(),x.size())||(s.paired&&exceptional(s.type,b.data(),b.size(),x.data(),x.size()));
 if(expert(s.type)){host.stage=o.allocate<uint8_t>(n*host.erb);host.peer_stage=s.paired?o.allocate<uint8_t>(n*host.erb):host.stage;
 auto ah=half_scales(s.type,a),bh=half_scales(s.type,b);size_t blocks=s.k/f.elements;std::vector<float> h(n*blocks);for(size_t r=0;r<n;++r)std::copy_n(ah.data()+(r%8)*blocks,blocks,h.data()+r*blocks);host.half=o.upload(h);if(s.paired){for(size_t r=0;r<n;++r)std::copy_n(bh.data()+(r%8)*blocks,blocks,h.data()+r*blocks);host.peer_half=o.upload(h);}else host.peer_half=host.half;
 }else{host.half=host.peer_half=o.upload(std::vector<float>{0});host.stage=host.peer_stage=nullptr;}
 // Parameters are uploaded exactly once per fixture, never in submit().
 params=o.upload(std::vector<Params>{host});
 }
 Events run(Owner&o,C c){require(!stopped,"cooperative stop requested");auto events=submit(o.q,params,host,shape.type,c);o.track(events);return events;}
 void read(Owner&o){o.finish();o.q.memcpy(actual.data(),host.y,actual.size()*sizeof(Result)).wait_and_throw();return;}
};
size_t mismatch(const std::vector<Result>&a,const std::vector<Result>&b){require(a.size()==b.size(),"output extent");for(size_t i=0;i<a.size();++i)if(!equal(a[i],b[i]))return i;return a.size();}
uint64_t budget(const Shape&s){return std::string(s.klass)=="logits"?10000000ull:2000000ull;}
uint64_t check_events(const Events& events,const Shape&s){uint64_t largest=0;for(unsigned e=0;e<events.count;++e){
 auto begin=events.event[e].get_profiling_info<sycl::info::event_profiling::command_start>();
 auto end=events.event[e].get_profiling_info<sycl::info::event_profiling::command_end>();
 duration(begin,end,budget(s));
 require(end-begin<=budget(s),"submission exceeded budget: "+std::string(s.label)+" elapsed_ns="+std::to_string(end-begin));largest=std::max(largest,end-begin);
 }return largest;}
std::vector<C> exact(Owner&o,Case& c,std::ofstream&log,const std::string&fixture,Gate& total){
 std::vector<C> accepted;std::vector<Result> control;bool control_ok=false;
 for(auto v:candidates(c.shape.type)){
 auto submitted=c.run(o,v);c.read(o);check_events(submitted,c.shape);
 if(v==C::current)control=c.actual;
 Gate gate;size_t first=c.actual.size(),raw_first=first;
 for(size_t i=0;i<c.actual.size();++i){auto g=compare(c.oracle[i],c.actual[i],v==C::current?nullptr:&control[i]);accumulate(gate,g);if(!g.passed())first=std::min(first,i);if(!equal(c.oracle[i],c.actual[i])||!equal(control[i],c.actual[i]))raw_first=std::min(raw_first,i);}
 if(v==C::current)control_ok=gate.passed();
 bool ok=control_ok&&gate.passed();if(ok)accepted.push_back(v);accumulate(total,gate);
 log<<"{\"fixture\":"<<quote(fixture)<<",\"shape\":"<<quote(c.shape.label)<<",\"type\":"<<unsigned(c.shape.type)<<",\"candidate\":"<<quote(name(v))<<",\"passed\":"<<(ok?"true":"false")<<",\"fallback_current\":"<<(c.host.exceptional?"true":"false")<<",\"excluded\":"<<(ok?"false":"true")<<",\"current_host_gate_passed\":"<<(control_ok?"true":"false")<<",\"first_mismatch\":"<<first<<",\"first_encoding_difference\":"<<raw_first<<",";gate_fields(log,gate);
 log<<",\"mismatches\":[";unsigned saved=0;
 for(size_t i=0;i<c.actual.size()&&saved<8;++i){if(equal(c.oracle[i],c.actual[i])&&equal(control[i],c.actual[i]))continue;
 auto slot=i/c.shape.rows,row=i%c.shape.rows;
 log<<(saved++?",":"")<<"{\"element\":"<<i<<",\"slot\":"<<slot<<",\"seed_row\":"<<source_row(c.shape,slot,row)%8<<",\"host_output_bits\":";result_bits(log,c.oracle[i]);log<<",\"device_output_bits\":";result_bits(log,c.actual[i]);log<<",\"current_device_output_bits\":";result_bits(log,control[i]);
 log<<",\"input_bf16_bits\":[";for(unsigned k=0;k<c.shape.k;++k)log<<(k?",":"")<<hex_bits(c.input[slot*c.shape.k+k],4);log<<"]}";
 }
 log<<"]}\n";log.flush();
 }
 return accepted;
}
void timing(Owner&o,Case&c,C v,std::ofstream&out){
 auto samples=capture_samples(200,[&]{return c.run(o,v);},[&]{o.finish();});
 for(unsigned r=0;r<200;++r){out<<"{\"shape\":"<<quote(c.shape.label)<<",\"class\":"<<quote(c.shape.klass)<<",\"candidate\":"<<quote(name(v))<<",\"frequency\":"<<c.shape.frequency<<",\"repetition\":"<<r<<",\"events\":[";
 for(unsigned e=0;e<samples[r].count;++e){auto event=samples[r].event[e];auto begin=event.get_profiling_info<sycl::info::event_profiling::command_start>();auto end=event.get_profiling_info<sycl::info::event_profiling::command_end>();out<<(e?",":"")<<"{\"command_start_ns\":"<<begin<<",\"command_end_ns\":"<<end<<"}";
 if(!begin||end<=begin||end-begin>budget(c.shape)){out<<"],\"passed\":false,\"budget_ns\":"<<budget(c.shape)<<"}\n";out.flush();throw std::runtime_error("GPU timestamp/submission budget failure; recorded before teardown");}}
 out<<"],\"passed\":true}\n";
 }out.flush();return;
}
void sequences(Owner&o,Case&c,C v,std::ofstream&out){
 // 48-layer trace positions: frequency of this shape, not 48 fake logits.
 // 200 complete sequences, ONE wait at the end of each sequence.
 for(unsigned rep=0;rep<200;++rep){unsigned issued=0;std::vector<Events> events;events.reserve(48);auto start=std::chrono::steady_clock::now();sequence48([&](unsigned layer){if(layer<c.shape.frequency){events.push_back(c.run(o,v));++issued;}},[&]{o.finish();});
 double wall=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();
 uint64_t maximum=0;for(const auto&e:events)maximum=std::max(maximum,check_events(e,c.shape));
 out<<"{\"shape\":"<<quote(c.shape.label)<<",\"candidate\":"<<quote(name(v))<<",\"repetition\":"<<rep<<",\"layer_positions\":48,\"launch_groups\":"<<issued<<",\"waits\":1,\"max_submission_ns\":"<<maximum<<",\"wall_ms\":"<<wall<<"}\n";
 }out.flush();return;
}
void whole_sequences(Owner&o,const std::map<std::pair<unsigned,C>,bool>& allowed,const fs::path& output){
 std::vector<std::unique_ptr<Case>> cases;for(auto s:shapes)cases.push_back(std::make_unique<Case>(o,s));
 std::ofstream log(output/"full-sequence-wall.jsonl"),plan(output/"full-sequence-plan.jsonl");
 for(unsigned tier=0;tier<7;++tier){std::vector<C> selected;
  for(auto s:shapes){auto cs=candidates(s.type);C c=tier<cs.size()?cs[tier]:C::current;if(!allowed.at({unsigned(s.type),c}))c=C::current;selected.push_back(c);
   plan<<"{\"tier\":"<<tier<<",\"shape\":"<<quote(s.label)<<",\"candidate\":"<<quote(name(c))<<"}\n";}
  for(unsigned rep=0;rep<200;++rep){std::vector<std::pair<Events,unsigned>> submitted;submitted.reserve(300);
   auto issue=[&](unsigned i){submitted.emplace_back(cases[i]->run(o,selected[i]),i);};
   auto start=std::chrono::steady_clock::now();
   sequence48([&](unsigned layer){bool qsa=layer%4==3,upgraded=layer==2;
    if(qsa){issue(7);issue(8);issue(9);}else{issue(upgraded?4:3);issue(upgraded?6:5);}
    issue(qsa?11:10);issue(upgraded?1:0);issue(2);
   if(layer==47)issue(12);},[&]{o.finish();});double wall=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();
   uint64_t maximum=0;for(const auto& [events,index]:submitted)maximum=std::max(maximum,check_events(events,shapes[index]));
   log<<"{\"tier\":"<<tier<<",\"repetition\":"<<rep<<",\"layers\":48,\"waits\":1,\"launch_groups\":"<<submitted.size()<<",\"wall_ms\":"<<wall<<",\"max_submission_ns\":"<<maximum<<"}\n";
  }log.flush();plan.flush();
 }o.release();return;
}
int main(int argc,char**argv){fs::path output;Gate total;bool full_allowed=true;std::unique_ptr<Owner> owner;try{
 unsigned card=0;std::string mode;for(int i=1;i<argc;++i){std::string a=argv[i];require(i+1<argc,"missing argument value");std::string v=argv[++i];if(a=="--mode")mode=v;else if(a=="--card")card=std::stoul(v);else if(a=="--output")output=v;else throw std::runtime_error("unknown argument");}
 require(!output.empty()&&(mode=="K0"||mode=="G1"),"mode/card/output required");fs::create_directories(output);std::signal(SIGINT,stop);std::signal(SIGTERM,stop);verify_dispatch();owner=std::make_unique<Owner>(card);auto&o=*owner;
 std::ofstream(output/"device.json")<<"{\"name\":"<<quote(o.q.get_device().get_info<sycl::info::device::name>())<<",\"driver\":"<<quote(o.q.get_device().get_info<sycl::info::device::driver_version>())<<",\"in_order\":true,\"profiling\":true}\n";
 if(mode=="K0"){auto ids=sycl::get_kernel_ids();require(!ids.empty(),"no kernels in binary");auto bundle=sycl::get_kernel_bundle<sycl::bundle_state::input>(o.q.get_context(),{o.q.get_device()},ids);auto built=sycl::build(bundle);require(built.get_kernel_ids().size()==ids.size(),"K0 missing kernel");std::ofstream(output/"kernels.json")<<"{\"count\":"<<ids.size()<<"}\n";}
 else {
 std::ofstream gates(output/"exactness.jsonl"),times(output/"timing.jsonl"),walls(output/"sequence-wall.jsonl");
 std::map<std::pair<unsigned,C>,bool> allowed;for(auto s:shapes)for(auto c:candidates(s.type))allowed[{unsigned(s.type),c}]=true;
 // Exact fixtures precede ALL timing. Formats, partial tiles, odd rows,
 // upgraded Q8, nonfinite scales, BF16 zero/denormal/NaN, both trees and ties.
 for(Type t:{Type::IQ2_S,Type::IQ3_S,Type::IQ3_XXS,Type::IQ4_NL,Type::Q6_K,Type::Q8_0})
 for(unsigned k:{32u,96u,256u,640u,768u,2560u,6144u,10240u}){if(k%layout(t).elements)continue;for(unsigned special=0;special<2;++special)for(unsigned mode_input=0;mode_input<4;++mode_input)for(unsigned split:{1u,4u}){
 Shape s{"boundary","fixture",t,5,k,expert(t)?10u:1u,split,1,expert(t)&&t!=Type::IQ4_NL};Case test(o,s,special,mode_input);auto keep=exact(o,test,gates,"k"+std::to_string(k)+"/special"+std::to_string(special)+"/input"+std::to_string(mode_input)+"/split"+std::to_string(split),total);for(auto c:candidates(t))if(std::find(keep.begin(),keep.end(),c)==keep.end())allowed[{unsigned(t),c}]=false;o.release();}}
 for(auto s:shapes){Case test(o,s);auto keep=exact(o,test,gates,"full-real-shape",total);for(auto c:candidates(s.type))if(std::find(keep.begin(),keep.end(),c)==keep.end())allowed[{unsigned(s.type),c}]=false;o.release();}
 // Every timed candidate passed every applicable boundary and real-shape gate.
 for(auto s:shapes){Case test(o,s);for(auto c:candidates(s.type))if(allowed[{unsigned(s.type),c}]){timing(o,test,c,times);sequences(o,test,c,walls);}o.release();}
 for(auto s:shapes)full_allowed=full_allowed&&allowed.at({unsigned(s.type),C::current});
 if(full_allowed)whole_sequences(o,allowed,output);
 std::ofstream summary(output/"gate-summary.json");summary<<"{\"policy\":"<<quote(gate_policy)<<",\"all_gates_passed\":"<<(total.passed()?"true":"false")<<",\"full_sequence_skipped\":"<<(full_allowed?"false":"true")<<",\"full_sequence_skip_reason\":"<<quote(full_allowed?"":"current failed: full sequence would include an excluded format")<<",\"counts\":{";gate_fields(summary,total);summary<<"},\"eligibility\":[";bool comma=false;for(auto [key,ok]:allowed){summary<<(comma?",":"")<<"{\"type\":"<<key.first<<",\"candidate\":"<<quote(name(key.second))<<",\"eligible\":"<<(ok?"true":"false")<<"}";comma=true;}summary<<"]}\n";
 }
 o.release();std::ofstream(output/"receipt.json")<<"{\"completed\":true,\"passed\":"<<(total.finite_failures?"false":"true")<<",\"finite_element_gate_failures\":"<<total.finite_failures<<",\"all_gates_passed\":"<<(total.passed()?"true":"false")<<",\"gate_policy\":"<<quote(gate_policy)<<",\"gate_summary\":\"gate-summary.json\",\"device_executed\":true,\"safe_to_exit\":true,\"live_bytes\":0,\"in_flight\":0,\"mode\":"<<quote(mode)<<",\"real_model_qualified\":false}\n";owner.reset();return total.finite_failures?2:0;
 }catch(const std::exception&e){std::cerr<<e.what()<<"\n";if(!output.empty()){fs::create_directories(output);std::ofstream(output/"failure.json")<<"{\"passed\":false,\"before_teardown\":true,\"error\":"<<quote(e.what())<<"}\n";}
 bool safe=!owner;try{if(owner){owner->release();safe=true;}}catch(const std::exception&drain){if(!output.empty())std::ofstream(output/"drain-failure.txt")<<drain.what()<<"\n";}
 if(!output.empty())std::ofstream(output/"receipt.json")<<"{\"passed\":false,\"device_executed\":true,\"safe_to_exit\":"<<(safe?"true":"false")<<"}\n";
 if(safe)owner.reset();else{owner.release();for(;;)std::this_thread::sleep_for(std::chrono::seconds(1));}return 1;}}
