#include "failure.hpp"
#include "gemv_batch.hpp"
#include <iostream>
#include <set>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <openssl/sha.h>
#include <unistd.h>
#include <cstring>
using namespace ownrt;
#ifdef OWN_RT_HOST_ONLY
struct Cpu final:Backend {
 std::string identity()const override{return "CPU GEMV bundle fixture";}
 void* allocate(size_t n,Memory)override{return ::operator new(n);}
 void release(void* p,Memory)override{::operator delete(p);}
 Event copy(void* d,const void* s,size_t n,std::span<const Event>)override{std::memcpy(d,s,n);return next_handle();}
 Event marker(std::span<const Event>)override{return next_handle();}
 Event compute(const Operation& op,std::span<void* const> p,std::span<const Event>)override{dynamic_cast<const integrated::HostOperation&>(op).run(p);return next_handle();}
 EventTiming timing(Event)override{return {0,0};}
 bool complete(Event)override{return true;}bool wait(Event,Deadline)override{return true;}
 void synchronize()override{}void clear_events()override{}void close_queue()override{}void close_context()override{}
};
#endif

#ifndef OWN_RT_HOST_ONLY
#include "sycl_operation.hpp"
// Independent standalone v2 elementwise oracle, transcribed from core_v2::run.
// Separate submissions preserve the original BF16 producer/consumer boundary.
struct ReferenceElementwise:ownrt::SyclOperation {
 unsigned op,n;
 sycl::event submit(sycl::queue& q,std::span<void* const> pointers,const std::vector<sycl::event>& deps)const override {
  std::array<void*,4> p{};std::copy(pointers.begin(),pointers.end(),p.begin());auto kind=op,count=n;
  return q.submit([&](sycl::handler& h){h.depends_on(deps);h.parallel_for(sycl::range<1>(kind==4?1:count),[=](sycl::id<1> id){size_t j=id[0];
   auto get=[&](unsigned slot,size_t at){return iq3::bits_float(uint32_t(static_cast<const uint16_t*>(p[slot])[at])<<16);};
   auto put=[&](unsigned slot,size_t at,float value){static_cast<uint16_t*>(p[slot])[at]=iq3::bf16_bits(value);};
   auto sig=[](float v){return 1.f/(1.f+detmath::exp(-v));};
   if(kind==0){float v=get(0,j)/4.f;put(1,j,v*sig(v));}
   if(kind==1){float v=0;for(unsigned st=0;st<4;++st)v=v+sig(get(1,st*count+j))*get(0,st*count+j);put(2,j,v/4.f);}
   if(kind==2){float v=get(0,j);put(2,j,(v*sig(v))*get(1,j));}
   if(kind==3){for(unsigned st=0;st<4;++st)put(3,st*count+j,get(0,st*count+j)+get(1,j)*(2.f*sig(get(2,st)/4.f)));}
   if(kind==4){float tree[32]{};auto source=static_cast<const float*>(p[0]);auto out=static_cast<float*>(p[1]);for(unsigned i=0;i<count;++i)tree[i]=source[i];unsigned width=count;while(width>1){if(width%2)tree[width++]=0;for(unsigned i=0;i<width/2;++i)tree[i]=tree[i*2]+tree[i*2+1];width/=2;}for(unsigned i=0;i<count;++i)out[i]=source[i]/tree[0];}
  });});
 }
};
#endif
std::vector<uint8_t> weights(iq3::Type type,unsigned rows,unsigned k,unsigned salt){
 auto layout=iq3::layout(type);std::vector<uint8_t> data(size_t(rows)*k/layout.elements*layout.bytes);uint32_t state=1234567+salt;
 for(auto& x:data){state=1664525u*state+1013904223u;x=state>>24;}
 for(unsigned r=0;r<rows;++r){auto row=data.data()+size_t(r)*k/layout.elements*layout.bytes;
  if(layout.elements==1){for(unsigned c=0;c<k;++c){float v=float(int((c*13+r*7+salt)%47)-23)/256.f;constexpr float scale[]={1.f,1e-30f,1e30f};v=v*scale[(r+salt)%3];
   if(type==iq3::Type::F32)std::memcpy(row+c*4,&v,4);
   else{uint16_t b=type==iq3::Type::BF16?iq3::bf16_bits(v):uint16_t((c%7==0)?0x0001:(c%7==1)?0x7bff:(c%7==2)?0xfbff:(0x2000|((c*7+r)&1023)));std::memcpy(row+c*2,&b,2);}}}
  else for(unsigned c=0;c<k;c+=layout.elements){auto block=row+c/layout.elements*layout.bytes;unsigned offset=type==iq3::Type::Q3_K?108:type==iq3::Type::Q6_K?208:0;constexpr uint16_t scales[]={0x1800,0x0001,0x03ff,0x0400,0x7bff,0xfbff,0x8000};auto scale=scales[(c/layout.elements+r+salt)%7];block[offset]=scale&255;block[offset+1]=scale>>8;}
 }
 return data;
}
int main(int argc,char** argv){std::filesystem::path failure_output;for(int i=1;i+1<argc;++i)if(std::string(argv[i])=="--output")failure_output=argv[i+1];try{
 std::unique_ptr<Backend> backend;std::filesystem::path output;unsigned card=0;bool authorized=false;
 for(int i=1;i<argc;++i){std::string a=argv[i];if(a=="--authorized-device-window")authorized=true;else if(a=="--card"&&i+1<argc)card=std::stoul(argv[++i]);else if(a=="--output"&&i+1<argc)output=argv[++i];else throw std::invalid_argument("fixture arguments");}
 std::vector<uint8_t> output_bytes;uint64_t max_submission_ns=0;
 auto record=[&](const std::vector<uint16_t>& data){auto ptr=reinterpret_cast<const uint8_t*>(data.data());packet23::row(output,"GEMV output "+std::to_string(output_bytes.size()),ptr,data.size()*2);if(!output.empty()){std::ofstream f(output/"output.bin",std::ios::binary|std::ios::app);f.write(reinterpret_cast<const char*>(ptr),data.size()*2);f.flush();}output_bytes.insert(output_bytes.end(),ptr,ptr+data.size()*2);};
 #ifdef OWN_RT_HOST_ONLY
 if(authorized)throw std::invalid_argument("host binary cannot authorize device");backend=std::make_unique<Cpu>();
 #else
 if(!authorized||output.empty())throw std::invalid_argument("device fixture requires --authorized-device-window --card N --output DIR");
 for(char** p=environ;*p;++p)if(std::string(*p).starts_with("NEO"))throw std::invalid_argument("NEO debug key refused");
 backend=make_sycl_device(card,true);
 #endif
 Device d(std::move(backend));try { CopyEngine copy(d);
 auto timing=[&](integrated::Launch launch){for(auto e:{launch.first,launch.last}){auto t=d.timing(e);max_submission_ns=std::max(max_submission_ns,t.end_ns-t.start_ns);}};
 #ifndef OWN_RT_HOST_ONLY
 auto elementwise=[&](unsigned kind,unsigned n,std::vector<Allocation> ids){ReferenceElementwise op;op.op=kind;op.n=n;auto event=d.compute(op,ids,{});if(!d.wait(event,std::chrono::minutes(20)))throw std::runtime_error("unfused elementwise deadline");timing({event,event,1});};
 #endif
size_t cases=0,values=0;uint64_t hash=1469598103934665603ull;
 size_t allocation_serial=0;auto alloc=[&](size_t n,Memory m=Memory::device){return d.arena.allocate("fixture-"+std::to_string(allocation_serial++),n,m,Category::scratch,Lifetime::transaction);};
 auto upload=[&](const void* data,size_t n){auto staging=alloc(n,Memory::pinned),device=alloc(n);std::memcpy(d.arena.row(staging).pointer,data,n);copy.copy(device,0,staging,0,n,{});return device;};
 auto read=[&](Allocation id,size_t n){auto staging=alloc(n,Memory::pinned);auto e=copy.copy(staging,0,id,0,n,{});if(!d.wait(e,std::chrono::minutes(20)))throw std::runtime_error("fixture read deadline");std::vector<uint16_t> out(n/2);std::memcpy(out.data(),d.arena.row(staging).pointer,n);return out;};
 auto verify=[&](const std::vector<uint16_t>& actual,const std::vector<uint16_t>& expected,const std::string& label){packet23::row(output,label,actual.data(),actual.size()*2,actual==expected);if(actual!=expected)throw std::runtime_error(label);};
 std::array types{iq3::Type::F32,iq3::Type::F16,iq3::Type::BF16,iq3::Type::Q8_0,iq3::Type::Q6_K,iq3::Type::Q3_K,iq3::Type::IQ3_XXS,iq3::Type::IQ2_S,iq3::Type::IQ3_S,iq3::Type::IQ4_NL};
 for(unsigned k:{512u,1280u,2560u})for(unsigned m:{1u,3u,87u})for(unsigned variant:{0u,1u,2u,4u,6u,7u})for(unsigned ti=0;ti<types.size();ti+=2){
  std::vector<uint16_t> input(m*k);for(size_t i=0;i<input.size();++i)input[i]=iq3::bf16_bits(float(int((i*17)%67)-33)/32.f);
  auto x=upload(input.data(),input.size()*2);std::vector<packet21::BatchSpec> specs;std::vector<std::vector<uint16_t>> expected;
  for(unsigned b=0;b<2;++b){unsigned rows=b?5:3;auto type=types[ti+b];auto packed=weights(type,rows,k,ti+b);auto data=variant>=6?iq3::expanded::expand(type,packed.data(),packed.size(),k):packed;
   auto w=upload(data.data(),data.size());auto y=alloc(size_t(m)*rows*2);integrated::Matrix matrix{};matrix.type=type;matrix.w=w;matrix.x=x;matrix.y=y;matrix.rows=rows;matrix.columns=k;packet21::BatchSpec spec;spec.matrix=matrix;spec.variant=variant;specs.push_back(spec);
   size_t rb=integrated::arithmetic::row_bytes(type,k,variant);std::vector<uint16_t> wanted(size_t(m)*rows);
   for(unsigned mi=0;mi<m;++mi)for(unsigned r=0;r<rows;++r)wanted[mi*rows+r]=iq3::bf16_bits(integrated::arithmetic::row(type,data.data()+r*rb,input.data()+mi*k,k,variant));
   #ifndef OWN_RT_HOST_ONLY
   // Same-card unfused original kernels, with distinct per-input allocations.
   for(unsigned mi=0;mi<m;++mi){auto single=matrix;single.x=upload(input.data()+mi*k,k*2);single.y=alloc(rows*2);single.workspace=alloc(rows*16);auto event=integrated::dense(d,single,variant);if(!d.wait(event.last,std::chrono::minutes(20)))throw std::runtime_error("unfused deadline");timing(event);auto got=read(single.y,rows*2);verify(got,std::vector<uint16_t>(wanted.begin()+mi*rows,wanted.begin()+(mi+1)*rows),"unfused device != host");}
   #endif
   expected.push_back(std::move(wanted));
  }
  auto plan=packet21::prepare_batch(d,specs,m);auto table=upload(plan.descriptor_bytes.data(),plan.descriptor_bytes.size());auto event=packet21::gemv_batch(d,plan,table);if(event.passes!=1||!d.wait(event.last,std::chrono::minutes(20)))throw std::runtime_error("bundle launch");timing(event);
  for(unsigned b=0;b<2;++b){auto got=read(specs[b].matrix.y,expected[b].size()*2);verify(got,expected[b],"bundle output mismatch type="+std::to_string(unsigned(types[ti+b]))+" variant="+std::to_string(variant)+" M="+std::to_string(m));record(got);for(auto v:got){hash=(hash^(v&255))*1099511628211ull;hash=(hash^(v>>8))*1099511628211ull;}values+=got.size();++cases;}
  d.retire_completed_events();
 }

 // Nonlinear input and output rounding fixtures retain original intermediate bytes.
 for(auto input_transform:{packet21::InputTransform::none,packet21::InputTransform::silu_div4,packet21::InputTransform::hc_mix}){
  constexpr unsigned rows=5,k=512;std::vector<uint16_t> input(k*4),aux(k*4),material(k);
  for(size_t i=0;i<input.size();++i){input[i]=iq3::bf16_bits(float(int(i%31)-15)/16.f);aux[i]=iq3::bf16_bits(float(int(i%19)-9)/8.f);}
  for(unsigned c=0;c<k;++c){auto bf=[](uint16_t v){return iq3::bits_float(uint32_t(v)<<16);};float value=bf(input[c]);
   if(input_transform==packet21::InputTransform::silu_div4){value=value/4.f;value=value*(1.f/(1.f+detmath::exp(-value)));}
   if(input_transform==packet21::InputTransform::hc_mix){value=0;for(unsigned i=0;i<4;++i)value=value+(1.f/(1.f+detmath::exp(-bf(aux[i*k+c]))))*bf(input[i*k+c]);value=value/4.f;}
   material[c]=iq3::bf16_bits(value);
  }
  auto x=upload(input.data(),input.size()*2),auxid=upload(aux.data(),aux.size()*2);packet21::BatchSpec spec;spec.input=input_transform;spec.auxiliary=auxid;spec.paired=true;spec.output=packet21::OutputTransform::silu_product;spec.other=alloc(rows*2);spec.variant=1;spec.peer_variant=2;
  std::vector<std::vector<uint16_t>> wanted(3,std::vector<uint16_t>(rows));
  #ifndef OWN_RT_HOST_ONLY
  auto reference_input=alloc(k*2);if(input_transform==packet21::InputTransform::none){auto e=copy.copy(reference_input,0,x,0,k*2,{});if(!d.wait(e,std::chrono::minutes(20)))throw std::runtime_error("reference input copy");}
  else if(input_transform==packet21::InputTransform::silu_div4)elementwise(0,k,{x,reference_input});else elementwise(1,k,{x,auxid,reference_input});
  verify(read(reference_input,k*2),material,"unfused prologue host parity");std::array<Allocation,2> reference_y{};
  #endif

  for(unsigned p=0;p<2;++p){auto& matrix=p?spec.peer:spec.matrix;matrix.type=p?iq3::Type::IQ3_S:iq3::Type::Q6_K;matrix.rows=rows;matrix.columns=k;matrix.x=x;matrix.y=alloc(rows*2);auto data=weights(matrix.type,rows,k,123+p);matrix.w=upload(data.data(),data.size());auto rb=integrated::arithmetic::row_bytes(matrix.type,k,p?2:1);
   for(unsigned r=0;r<rows;++r)wanted[p][r]=iq3::bf16_bits(integrated::arithmetic::row(matrix.type,data.data()+r*rb,material.data(),k,p?2:1));
   #ifndef OWN_RT_HOST_ONLY
   auto baseline=matrix;baseline.x=reference_input;baseline.y=reference_y[p]=alloc(rows*2);baseline.workspace=alloc(rows*16);auto event=integrated::dense(d,baseline,p?2:1);if(!d.wait(event.last,std::chrono::minutes(20)))throw std::runtime_error("paired unfused deadline");timing(event);verify(read(baseline.y,rows*2),wanted[p],"paired unfused host parity");
   #endif

  }
  for(unsigned r=0;r<rows;++r){float gate=iq3::bits_float(uint32_t(wanted[0][r])<<16),up=iq3::bits_float(uint32_t(wanted[1][r])<<16);wanted[2][r]=iq3::bf16_bits((gate*(1.f/(1.f+detmath::exp(-gate))))*up);}

  #ifndef OWN_RT_HOST_ONLY
  auto activated=alloc(rows*2);elementwise(2,rows,{reference_y[0],reference_y[1],activated});verify(read(activated,rows*2),wanted[2],"unfused activation host parity");
  #endif
  if(input_transform!=packet21::InputTransform::none)spec.materialized_input=alloc(k*2);
  auto plan=packet21::prepare_batch(d,{spec});auto table=upload(plan.descriptor_bytes.data(),plan.descriptor_bytes.size());auto event=packet21::gemv_batch(d,plan,table);if(!d.wait(event.last,std::chrono::minutes(20)))throw std::runtime_error("transform deadline");timing(event);
  for(unsigned p=0;p<3;++p){auto got=read(p==0?spec.matrix.y:p==1?spec.peer.y:spec.other,rows*2);verify(got,wanted[p],"nonlinear GEMV rounding mismatch");record(got);for(auto v:got){hash=(hash^(v&255))*1099511628211ull;hash=(hash^(v>>8))*1099511628211ull;}values+=got.size();++cases;}
  if(spec.materialized_input && read(spec.materialized_input,k*2)!=material)throw std::runtime_error("prologue materialization mismatch");
  // Safety counterexample: output that a sibling reads must be rejected.
  auto unsafe=spec;unsafe.matrix.y=spec.matrix.x;bool refused=false;try{packet21::prepare_batch(d,{spec,unsafe});}catch(const std::invalid_argument&){refused=true;}if(!refused)throw std::runtime_error("sibling dependency alias accepted");
  d.retire_completed_events();
 }

 // Four-stream residual is an intentional coordinate-local read/modify/write.
 {
  constexpr unsigned rows=5,k=512;std::vector<uint16_t> x(k),stream(rows*4),inject(4);
  for(unsigned i=0;i<k;++i)x[i]=iq3::bf16_bits(float(int(i%23)-11)/16.f);
  for(unsigned i=0;i<stream.size();++i)stream[i]=iq3::bf16_bits(float(int(i%13)-6)/8.f);
  for(unsigned i=0;i<4;++i)inject[i]=iq3::bf16_bits(float(int(i)-2));
  packet21::BatchSpec spec;auto& m=spec.matrix;m.type=iq3::Type::IQ3_XXS;m.rows=rows;m.columns=k;auto data=weights(m.type,rows,k,83);m.w=upload(data.data(),data.size());m.x=upload(x.data(),x.size()*2);m.y=alloc(rows*2);spec.variant=4;spec.output=packet21::OutputTransform::hc_residual;spec.other=spec.destination=upload(stream.data(),stream.size()*2);spec.auxiliary=upload(inject.data(),inject.size()*2);
  auto rb=integrated::arithmetic::row_bytes(m.type,k,4);auto wanted=stream;
  for(unsigned r=0;r<rows;++r){auto dot=iq3::bf16_bits(integrated::arithmetic::row(m.type,data.data()+r*rb,x.data(),k,4));float v=iq3::bits_float(uint32_t(dot)<<16);for(unsigned st=0;st<4;++st){float old=iq3::bits_float(uint32_t(stream[st*rows+r])<<16),inj=iq3::bits_float(uint32_t(inject[st])<<16);wanted[st*rows+r]=iq3::bf16_bits(old+v*(2.f*(1.f/(1.f+detmath::exp(-(inj/4.f))))));}}

  #ifndef OWN_RT_HOST_ONLY
  auto baseline=m;baseline.y=alloc(rows*2);baseline.workspace=alloc(rows*16);auto e=integrated::dense(d,baseline,4);if(!d.wait(e.last,std::chrono::minutes(20)))throw std::runtime_error("unfused residual dot deadline");timing(e);auto residual=alloc(wanted.size()*2);elementwise(3,rows,{spec.other,baseline.y,spec.auxiliary,residual});verify(read(residual,wanted.size()*2),wanted,"unfused HC residual host parity");
  #endif
  auto plan=packet21::prepare_batch(d,{spec});auto table=upload(plan.descriptor_bytes.data(),plan.descriptor_bytes.size());auto event=packet21::gemv_batch(d,plan,table);if(!d.wait(event.last,std::chrono::minutes(20)))throw std::runtime_error("residual deadline");timing(event);auto got=read(spec.destination,wanted.size()*2);verify(got,wanted,"coordinate residual exactness");record(got);values+=got.size();++cases;d.retire_completed_events();
 }
 // Routed shared input, distinct status outputs, invalid-index safe substitute,
 // and the independent same-launch top-probability normalization work-group.
 {
  constexpr unsigned rows=3,k=512,count=2,experts=2;std::vector<uint16_t> x(k);for(unsigned i=0;i<k;++i)x[i]=iq3::bf16_bits(float(int(i%17)-8)/16.f);
  iq3::Route routes[count]={{1,0,rows},{99,0,rows}};uint32_t zero[count]={0,0};float prob[count]={0.2f,0.3f};
  auto xid=upload(x.data(),x.size()*2),rid=upload(routes,sizeof routes);packet21::BatchSpec spec;spec.shared_input=true;spec.paired=true;spec.output=packet21::OutputTransform::silu_product;spec.other=alloc(count*rows*2);spec.route_prob=upload(prob,sizeof prob);spec.route_top=count;
  std::vector<uint16_t> wanted[2];
  for(unsigned peer=0;peer<2;++peer){auto& m=peer?spec.peer:spec.matrix;m.type=peer?iq3::Type::IQ3_S:iq3::Type::IQ2_S;m.rows=rows;m.columns=k;m.count=count;m.experts=experts;m.routes=rid;m.status=upload(zero,sizeof zero);m.x=xid;m.y=alloc(count*rows*2);auto data=weights(m.type,rows*experts,k,19+peer);m.w=upload(data.data(),data.size());auto rb=integrated::arithmetic::row_bytes(m.type,k,2);wanted[peer].resize(count*rows,0x7fc0);for(unsigned r=0;r<rows;++r)wanted[peer][r]=iq3::bf16_bits(integrated::arithmetic::row(m.type,data.data()+(rows+r)*rb,x.data(),k,2));}

  #ifndef OWN_RT_HOST_ONLY
  std::vector<uint16_t> repeated=x;repeated.insert(repeated.end(),x.begin(),x.end());auto replicated=upload(repeated.data(),repeated.size()*2);
  for(unsigned peer=0;peer<2;++peer){auto baseline=peer?spec.peer:spec.matrix;baseline.x=replicated;baseline.y=alloc(count*rows*2);baseline.status=upload(zero,sizeof zero);auto e=iq3::kopt3::multiply(d,{baseline},iq3::kopt3::Variant::constant);if(!d.wait(e.last,std::chrono::minutes(20)))throw std::runtime_error("unfused routed deadline");timing(e);verify(read(baseline.y,count*rows*2),wanted[peer],"unfused routed host parity");auto status=read(baseline.status,sizeof zero);uint32_t words[2];std::memcpy(words,status.data(),sizeof words);if(words[0]!=0||words[1]!=1)throw std::runtime_error("unfused route guards");}
  auto normalized=alloc(sizeof prob);elementwise(4,count,{spec.route_prob,normalized});auto raw=read(normalized,sizeof prob);float outputs[2];std::memcpy(outputs,raw.data(),sizeof outputs);float total=prob[0]+prob[1];for(unsigned j=0;j<count;++j)if(std::bit_cast<uint32_t>(outputs[j])!=std::bit_cast<uint32_t>(prob[j]/total))throw std::runtime_error("unfused probability parity");
  #endif
  auto plan=packet21::prepare_batch(d,{spec});auto table=upload(plan.descriptor_bytes.data(),plan.descriptor_bytes.size());auto event=packet21::gemv_batch(d,plan,table);if(!d.wait(event.last,std::chrono::minutes(20)))throw std::runtime_error("route deadline");timing(event);
  for(unsigned peer=0;peer<2;++peer){auto m=peer?spec.peer:spec.matrix;auto got=read(m.y,count*rows*2);verify(got,wanted[peer],"guarded routed exactness");auto status=read(m.status,sizeof zero);uint32_t words[2];std::memcpy(words,status.data(),sizeof words);if(words[0]!=0||words[1]!=1)throw std::runtime_error("distinct routed status guard");record(got);record(status);values+=got.size();++cases;}
  auto probabilities=read(spec.route_prob,sizeof prob);float observed[2];std::memcpy(observed,probabilities.data(),sizeof observed);float sum=prob[0]+prob[1];for(unsigned i=0;i<2;++i)if(std::bit_cast<uint32_t>(observed[i])!=std::bit_cast<uint32_t>(prob[i]/sum))throw std::runtime_error("route probability exactness");record(probabilities);++cases;d.retire_completed_events();
 }
 if(!output.empty()){std::filesystem::create_directories(output);std::ofstream f(output/"output.bin",std::ios::binary);f.write(reinterpret_cast<const char*>(output_bytes.data()),output_bytes.size());}
 auto receipt=d.shutdown(std::chrono::seconds(60));if(!receipt.safe_to_exit || receipt.exit_code)throw std::runtime_error("fixture shutdown");
 if(!output.empty()){std::filesystem::create_directories(output);std::ofstream binary(output/"output.bin",std::ios::binary);binary.write(reinterpret_cast<const char*>(output_bytes.data()),output_bytes.size());binary.close();
 unsigned char digest[SHA256_DIGEST_LENGTH];SHA256(output_bytes.data(),output_bytes.size(),digest);std::ostringstream hex;for(auto b:digest)hex<<std::hex<<std::setw(2)<<std::setfill('0')<<unsigned(b);
 std::ofstream json(output/"receipt.json");json<<"{\"schema\":\"own-runtime.iq3.packet21.fixtures.v1\",\"passed\":true,\"device_executed\":"<<(authorized?"true":"false")<<",\"fused_unfused_exact\":true,\"host_exact\":true,\"arithmetic\":\"iq3-p17-detmath-v2\",\"owner_cards\":1,\"fixture_output_sha256\":\""<<hex.str()<<"\",\"max_submission_ns\":"<<max_submission_ns<<",\"sequential_owners\":1,\"safe_to_exit\":true,\"teardown\":["<<receipt.json()<<"],\"fixtures\":"<<cases<<",\"values\":"<<values<<"}\n";}
 std::cout<<"{\"gate\":\"GEMV mixed-grid row bundles\",\"cases\":"<<cases<<",\"values\":"<<values<<",\"dense_paired_fnv64\":\""<<std::hex<<hash<<"\",\"passed\":true}\n";
 }catch(const std::exception& e){packet23::failure(d,output,e.what());return 1;}
 }catch(const std::exception& e){std::cerr<<e.what()<<'\n';if(!failure_output.empty()){std::filesystem::create_directories(failure_output);if(!std::filesystem::exists(failure_output/"failure.json"))std::ofstream(failure_output/"failure.json")<<"{\"passed\":false,\"error\":"<<ownrt::quote(e.what())<<",\"teardown\":{\"status\":\"owner not constructed\",\"in_flight\":0,\"live_bytes\":0,\"in_flight_event_ids\":[],\"registered_borrowers\":[]}}\n";}return 1;}}
