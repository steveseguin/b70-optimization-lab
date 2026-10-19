// Packet175 D2 warm-ahead micro: packet166 M1 layer path (lab-owned production arithmetic)
// with an optional L2 warm-ahead kernel before every dense GEMV. Arithmetic is unchanged.
#include "paired_wrappers.hpp"
#include "weights.hpp"
#include <fstream>
#include <iostream>
#include <map>
#include <functional>
#include <atomic>
#include <csignal>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <unistd.h>
#include <fcntl.h>
#include <filesystem>
#include <openssl/evp.h>
#include <chrono>
#include <optional>
#include <sys/resource.h>
#include <sys/statvfs.h>
#include <sys/sysinfo.h>
namespace ownrt {uint64_t next_handle(){static std::atomic<uint64_t>n{1};return n++;}}
static volatile std::sig_atomic_t stopped=0;
static bool preparing=false;
static std::ofstream sensors;
static unsigned prepare_steps=0;
static bool semantic_buffer(const std::string&n){return n.find("scratch")==std::string::npos&&n.find("workspace")==std::string::npos&&!n.ends_with(".partial")&&n!="counts"&&n!="scores"&&n!="probabilities";}
static void stop(int){stopped=1;}
static std::string digest(const std::vector<uint8_t>&v){unsigned char d[32];unsigned n=0;EVP_Digest(v.data(),v.size(),d,&n,EVP_sha256(),nullptr);std::string s;for(auto x:d){s+="0123456789abcdef"[x>>4];s+="0123456789abcdef"[x&15];}return s;}
static bool quiet_read(){for(auto&entry:std::filesystem::directory_iterator("/proc")){auto name=entry.path().filename().string();if(name==std::to_string(getpid())||name.empty()||name.find_first_not_of("0123456789")!=std::string::npos)continue;std::ifstream f(entry.path()/"comm");std::string comm;std::getline(f,comm);if(comm=="own-rt-iq3"||comm=="micro-device"||comm=="d2-micro-device")return false;}return true;}
static void require(bool x,const std::string&s){if(!x)throw std::runtime_error(s);}
using U=uint16_t;using V=std::vector<void*>;using Type=iq3::Type;
constexpr unsigned H=2560,TOP=10,CAP=4096,BUDGET=2048;
struct Mem {
 std::vector<uint32_t> host;void*ptr=nullptr;size_t bytes=0,stride=0;
};
struct Runtime {
 std::map<std::string,Mem> mem;
#ifndef OWN_RT_HOST_ONLY
 std::optional<sycl::queue> device_queue;
 sycl::queue& queue(){require(!preparing,"device API forbidden during CPU preparation");if(!device_queue)device_queue.emplace(sycl::gpu_selector_v,sycl::property_list{sycl::property::queue::in_order{},sycl::property::queue::enable_profiling{}});return *device_queue;}
 std::vector<std::pair<std::string,sycl::event>> events;
#endif
 Mem& alloc(std::string name,size_t bytes,size_t stride=0){auto[it,ok]=mem.try_emplace(name);require(ok,"duplicate allocation "+name);auto&m=it->second;m.bytes=bytes;m.stride=stride;m.host.resize((bytes+3)/4);
#ifdef OWN_RT_HOST_ONLY
 m.ptr=m.host.data();
#else
 if(preparing)m.ptr=m.host.data();else{m.ptr=sycl::malloc_device(bytes,queue());require(m.ptr,"device allocation");queue().memset(m.ptr,0,bytes).wait_and_throw();}
#endif
 return m;}
 void* p(const std::string&name,unsigned row=0){auto&m=mem.at(name);return (uint8_t*)m.ptr+row*m.stride;}
 U* u(const std::string&name,unsigned row=0){return (U*)p(name,row);}
 void upload(const std::string&name){auto&m=mem.at(name);
#ifndef OWN_RT_HOST_ONLY
 if(!preparing)queue().memcpy(m.ptr,m.host.data(),m.bytes).wait_and_throw();
#endif
 }
 void download(){
#ifndef OWN_RT_HOST_ONLY
 if(!preparing){for(auto&[name,m]:mem)if(!name.starts_with("w:"))queue().memcpy(m.host.data(),m.ptr,m.bytes);queue().wait_and_throw();}
#endif
 }
 void clear(){for(auto&[name,m]:mem)if(!name.starts_with("w:")){std::fill(m.host.begin(),m.host.end(),0);upload(name);}}
#ifndef OWN_RT_HOST_ONLY
 void record(std::string cls,sycl::event e){events.emplace_back(cls,e);}
 void wait(){if(!preparing)queue().wait_and_throw();}
#else
 void wait(){}
#endif
 ~Runtime(){
#ifndef OWN_RT_HOST_ONLY
 if(device_queue){queue().wait_and_throw();for(auto&[name,m]:mem)sycl::free(m.ptr,queue());}
#endif
 }
};
struct Matrix {const uint8_t*w;const U*x[2];U*y[2];float*scratch[2];unsigned k,n,split,rb;Type type;};
inline std::array<float,2> lane(Matrix b,unsigned row,unsigned begin,unsigned end,unsigned l,unsigned batch){
 const auto*w=b.w+size_t(row)*b.rb;
 auto f=[&]<Type T>(){auto v=p68c::dense_lane<T>(w,b.x[0],b.x[batch==2?1:0],b.k,begin,end,l);return v;};
 switch(b.type){case Type::Q6_K:return f.template operator()<Type::Q6_K>();case Type::Q8_0:return f.template operator()<Type::Q8_0>();case Type::F32:return f.template operator()<Type::F32>();case Type::BF16:return f.template operator()<Type::BF16>();default:throw std::runtime_error("dense format");}
}
#ifndef OWN_RT_HOST_ONLY
inline std::array<float,2> device_lane(Matrix b,unsigned row,unsigned begin,unsigned end,unsigned l){
 // No throwing runtime type fallback in device code.
 auto*w=b.w+size_t(row)*b.rb;
 switch(b.type){case Type::Q6_K:return p68c::dense_lane<Type::Q6_K>(w,b.x[0],b.x[1],b.k,begin,end,l);case Type::Q8_0:return p68c::dense_lane<Type::Q8_0>(w,b.x[0],b.x[1],b.k,begin,end,l);case Type::F32:return p68c::dense_lane<Type::F32>(w,b.x[0],b.x[1],b.k,begin,end,l);default:return p68c::dense_lane<Type::BF16>(w,b.x[0],b.x[1],b.k,begin,end,l);}
}
struct Team {sycl::nd_item<1>it;float*x;template<class F>void each(int n,F f)const{for(int j=it.get_local_linear_id();j<n;j+=it.get_local_range(0))f(j);}void barrier()const{it.barrier(sycl::access::fence_space::global_and_local);}int error(ng::Args a)const{return sycl::atomic_ref<int32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(*a.i(15)).load();}void fail(ng::Args a)const{sycl::atomic_ref<int32_t,sycl::memory_order::relaxed,sycl::memory_scope::device,sycl::access::address_space::global_space>(*a.i(15)).store(1);}float sum(int n,int base=0)const{for(int stride=1;stride<n;stride*=2){each((n+stride*2-1)/(stride*2),[&](int j){int i=j*stride*2;x[base+i]=x[base+i]+(i+stride<n?x[base+i+stride]:0.f);});barrier();}return x[base];}};
#endif
struct Layer {
 Runtime rt;unsigned layer;bool real;bool proof=true;bool warm=false;std::map<std::string,std::pair<Type,unsigned>> formats;std::vector<std::string> stages;
 explicit Layer(unsigned l,bool r):layer(l),real(r){}
 std::string wn(std::string s){return "w:"+s;}
 void init_weights(){
  require(!real||quiet_read(),"timing process active; no model read");
  require(!real||(syscall(SYS_ioprio_get,1,0)>>13)==3,"ionice -c3 required");
  for(auto&s:weight_specs){std::string full=s.name,prefix="blk."+std::to_string(layer)+".";if(!full.starts_with(prefix))continue;auto name=full.substr(prefix.size());Type t=s.type==0?Type::F32:s.type==8?Type::Q8_0:s.type==14?Type::Q6_K:s.type==20?Type::IQ4_NL:s.type==22?Type::IQ2_S:Type::BF16;
   unsigned rb=s.k?unsigned(s.bytes/s.rows):0;size_t size=s.bytes;
   if(t==Type::Q6_K||t==Type::Q8_0)rb=iq3::expanded::row_bytes(t,s.k);
   if(t==Type::IQ2_S)rb=p90::expert_stride(s.k);
   if(s.k)size=size_t(rb)*s.rows;
   auto&m=rt.alloc(wn(name),size);formats[name]={t,rb};if(preparing)continue;int fd=-1;
   if(real){fd=open(s.path,O_RDONLY);require(fd>=0,"weight open");struct stat st{};require(!fstat(fd,&st)&&uint64_t(st.st_size)==s.size&&uint64_t(st.st_ino)==s.inode&&uint64_t(st.st_dev)==s.device&&uint64_t(st.st_mtim.tv_sec)*1000000000+st.st_mtim.tv_nsec==s.mtime&&uint64_t(st.st_ctim.tv_sec)*1000000000+st.st_ctim.tv_nsec==s.ctime,"weight identity");}
   unsigned rawrb=s.k?unsigned(s.bytes/s.rows):unsigned(s.bytes);unsigned nrows=s.k?s.rows:1;
   for(unsigned first=0;first<nrows;){unsigned count=std::min(nrows-first,std::max(16u,(1024*1024/rawrb/16)*16));std::vector<uint8_t>raw(size_t(count)*rawrb);if(real){require(quiet_read(),"timing process became active; stop reads");require(pread(fd,raw.data(),raw.size(),s.offset+size_t(first)*rawrb)==ssize_t(raw.size()),"short model read");}else{
    uint32_t seed=166+first+layer;for(auto&v:raw){seed=1664525*seed+1013904223;v=seed>>24;}
    if(t==Type::F32){for(size_t i=0;i<raw.size()/4;++i){float x=name.find("norm")!=std::string::npos?1.f:name=="ssm_a"?-1.f:float(int(i%17)-8)/1024.f;std::memcpy(raw.data()+4*i,&x,4);}}
    else if(t==Type::BF16){for(size_t i=0;i<raw.size()/2;++i){U x=iq3::bf16_bits(float(int(i%17)-8)/1024.f);std::memcpy(raw.data()+2*i,&x,2);}}
    else{auto f=iq3::layout(t);for(size_t off=0;off<raw.size();off+=f.bytes){size_t scale=off+(t==Type::Q6_K?208:0);raw[scale]=0;raw[scale+1]=0x10;}}
   }
   auto*dest=(uint8_t*)m.host.data()+size_t(first)*rb;
   if(t==Type::Q6_K||t==Type::Q8_0){auto v=iq3::expanded::expand(t,raw.data(),raw.size(),s.k);std::memcpy(dest,v.data(),v.size());}
   else if(t==Type::IQ2_S){for(unsigned row=0;row<count;++row)p90::expert_repack(s.k,raw.data()+row*rawrb,dest+row*rb);}
   else if(t==Type::IQ4_NL){std::vector<uint8_t>packed(raw.size());for(unsigned row=0;row<count;++row)p49bgemv::repack_row(t,s.k,raw.data()+row*rawrb,packed.data()+row*rb);auto v=p100::transpose(packed.data(),count);std::memcpy(dest,v.data(),v.size());}
   else std::memcpy(dest,raw.data(),raw.size());
   first+=count;
  }
  if(fd>=0)close(fd);rt.upload(wn(name));
#ifndef OWN_RT_HOST_ONLY
  m.host.clear();m.host.shrink_to_fit();
#endif
  }
 }
 void tensor(const std::string&n,size_t elems,size_t width=2,bool state=false){rt.alloc(n,elems*width*(state?1:2),state?0:elems*width);}
 void init_buffers(){
  tensor("streams",10240);tensor("streams_after_attention",10240);tensor("position",1,4);tensor("error",1,4);tensor("active",1,4);tensor("one",1,4);
  tensor("rope",rope_constants::bytes,1,true);{if(!preparing){std::ifstream f(std::string(P175_ROOT)+"/rope.bf16",std::ios::binary);auto&m=rt.mem.at("rope");f.read((char*)m.host.data(),m.bytes);require(bool(f),"rope bytes");rt.upload("rope");}}
  for(auto tag:{"a","f"}){std::string t=tag;for(auto[n,z]:std::initializer_list<std::pair<const char*,unsigned>>{{"norm",10240},{"low",320},{"act",320},{"gate",10240},{"mix",2560},{"inject",4}})tensor(t+"."+n,z);tensor(t+".scratch",320,4);tensor(t+".workspace",32,4);}
  tensor("dense.scratch",12288*8,4);tensor("warm.scratch",2,4);tensor("warm.never.scratch",1,4);
#ifdef OWN_RT_HOST_ONLY
  rt.alloc("w:evict",4096);
#else
  rt.alloc("w:evict",size_t(256)<<20);if(!preparing){rt.mem.at("w:evict").host.clear();rt.mem.at("w:evict").host.shrink_to_fit();}
#endif
  for(auto[n,z]:std::initializer_list<std::pair<const char*,unsigned>>{{"attention",2560},{"router",512},{"sg",640},{"su",640},{"sa",640},{"shared_gate",1},{"down",2560},{"mixture",2560},{"moe",2560},{"eg",6400},{"eu",6400},{"ea",6400},{"ed",25600}})tensor(n,z);
  for(auto[n,z]:std::initializer_list<std::pair<const char*,unsigned>>{{"ids",10},{"prob",10},{"routes",30},{"downroutes",30},{"statusg",10},{"statusu",10},{"statusd",10},{"route.scratch",1088}})tensor(n,z,4);
  if(layer==0){for(auto[n,z]:std::initializer_list<std::pair<const char*,unsigned>>{{"qkv",10240},{"z",6144},{"alpha",48},{"beta",48},{"conv",10240},{"y",6144},{"gated",6144}})tensor(n,z);tensor("history",10240*3,2,true);tensor("state",48*128*128,2,true);tensor("state.first",48*128*128,2,true);tensor("history.first",10240*3,2,true);}
  else{for(auto[n,z]:std::initializer_list<std::pair<const char*,unsigned>>{{"qgate",12288},{"k",512},{"v",512},{"iq",512},{"ik",128},{"q",6144},{"gate",6144},{"kn",512},{"iqn",512},{"y",6144}})tensor(n,z);tensor("keys",CAP*512,2,true);tensor("values",CAP*512,2,true);tensor("raw",CAP*128,2,true);tensor("pooled",(CAP/4)*128,2,true);tensor("selected",BUDGET+3,4);tensor("select.scratch",CAP/4,4);tensor("counts",1,4);tensor("qsa.scratch",24*2*258,4);tensor("scores",24*(BUDGET+3),4);tensor("probabilities",24*(BUDGET+3),4);}
  for(auto&n:std::vector<std::string>{"qkv","z","alpha","beta","qgate","k","v","iq","ik","attention","router","sg","su","shared_gate"})if(rt.mem.contains(n))tensor(n+".partial",rt.mem.at(n).stride/2*8,4);
 }
 void sensor(unsigned pos,unsigned arm,unsigned repeat){
  struct rusage usage{};struct sysinfo info{};struct statvfs disk{};require(!getrusage(RUSAGE_SELF,&usage)&&!sysinfo(&info)&&!statvfs("/",&disk),"real sensors");
  require(uint64_t(usage.ru_maxrss)*1024<=4ull*1024*1024*1024,"CPU memory limit");require(uint64_t(disk.f_bavail)*disk.f_frsize>=27000000000ull,"CPU disk floor");
  uint64_t allocation_identity=1469598103934665603ull;for(auto&[n,m]:rt.mem){allocation_identity=(allocation_identity^uintptr_t(m.ptr))*1099511628211ull;allocation_identity=(allocation_identity^m.bytes)*1099511628211ull;}auto&m=rt.mem.at("streams");auto*p=(uint8_t*)m.host.data();std::vector<uint8_t>sample(p,p+64);auto&state=rt.mem.at(layer==0?"state":"keys");auto*statep=(uint8_t*)state.host.data();sample.insert(sample.end(),statep,statep+64);sensors<<"{\"kind\":\"sensor\",\"layer\":"<<layer<<",\"position\":"<<pos<<",\"arm\":"<<arm<<",\"repeat\":"<<repeat<<",\"max_rss_bytes\":"<<uint64_t(usage.ru_maxrss)*1024<<",\"free_ram_bytes\":"<<uint64_t(info.freeram)*info.mem_unit<<",\"disk_free_bytes\":"<<uint64_t(disk.f_bavail)*disk.f_frsize<<",\"streams_address\":"<<uintptr_t(m.ptr)<<",\"allocation_identity\":"<<allocation_identity<<",\"state_sample_sha256\":\""<<digest(sample)<<"\",\"prepare_steps\":"<<prepare_steps<<"}\n";
 }
 void reset(unsigned pos,unsigned seed){
  for(auto&[n,m]:rt.mem)if(!n.starts_with("w:")&&n!="rope"){std::fill(m.host.begin(),m.host.end(),0);if(n=="streams"||n=="state"||n=="history"||n=="keys"||n=="values"||n=="raw"||n=="pooled"){auto*p=(U*)m.host.data();for(size_t i=0;i<m.bytes/2;++i){seed=seed*1664525+1013904223;p[i]=iq3::bf16_bits(float(int(seed%255)-127)/128.f);}}if(n=="position"){m.host[0]=pos;m.host[1]=pos+1;}if(n=="active")m.host[0]=m.host[1]=1;if(n=="one")m.host[0]=m.host[1]=std::bit_cast<uint32_t>(1.f);rt.upload(n);}
#ifndef OWN_RT_HOST_ONLY
 rt.events.clear();
#endif
 }
 // D2 arm B: touch every 64-byte line of the next GEMV's weights (one 32-bit load per line, folded
 // into a never-taken sink store), so each line passes through L2 before the GEMV. Writes nothing.
 // Whole weight allocation the GEMV reads (1-D tensors such as ffn_gate_inp_shexp have rb=0).
 size_t weight_bytes(const void*ptr){for(auto&[n,m]:rt.mem)if(n.starts_with("w:")&&m.ptr==ptr)return m.bytes;require(false,"weight allocation");return 0;}
 void warm_ahead(std::vector<std::pair<const void*,size_t>> spans){if(!warm||preparing){if(warm)++prepare_steps;return;}
  for(auto[ptr,bytes]:spans)require(ptr&&bytes&&bytes%4==0,"warm span");
#ifndef OWN_RT_HOST_ONLY
  for(auto[ptr,bytes]:spans){const uint32_t*w=(const uint32_t*)ptr;size_t lines=(bytes+63)/64;uint32_t*sink=(uint32_t*)rt.p("warm.scratch");const uint32_t*never=(const uint32_t*)rt.p("warm.never.scratch");
   rt.record("warm",rt.queue().submit([=](sycl::handler&h){h.parallel_for(sycl::nd_range<1>(((lines+255)/256)*256,256),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{size_t i=it.get_global_linear_id();uint32_t v=i<lines?w[i*16]:0u;if(v==0x9e3779b9u&&never[0]==0x51u)sink[0]=v;});}));}
#else
  volatile uint32_t fold=0;for(auto[ptr,bytes]:spans)for(size_t i=0;i<bytes/4;i+=16)fold=fold^((const uint32_t*)ptr)[i];
#endif
 }
 // Realism interposer: stream-read a 256 MiB buffer before each row's layer pass, standing in for the
 // other layers of the token so every weight starts cold, as in the real body.
 void evict(){if(preparing){++prepare_steps;return;}
#ifndef OWN_RT_HOST_ONLY
  const uint32_t*w=(const uint32_t*)rt.p("w:evict");size_t words=rt.mem.at("w:evict").bytes/4;uint32_t*sink=(uint32_t*)rt.p("warm.scratch");const uint32_t*never=(const uint32_t*)rt.p("warm.never.scratch");
  rt.record("evict",rt.queue().submit([=](sycl::handler&h){h.parallel_for(sycl::nd_range<1>(words/4,256),[=](sycl::nd_item<1>it){size_t i=it.get_global_linear_id()*4;uint32_t v=w[i]^w[i+1]^w[i+2]^w[i+3];if(v==0x9e3779b9u&&never[0]==0x51u)sink[1]=v;});}));
#endif
 }
 p60::Bound hc_bound(const std::string&t,unsigned row){auto prefix=t=="a"?"hc_attn_":"hc_ffn_";return {rt.u("streams",row),(float*)rt.p(wn(std::string(prefix)+"norm.weight")),(uint8_t*)rt.p(wn(std::string(prefix)+"down.weight")),(uint8_t*)rt.p(wn(std::string(prefix)+"up.weight")),(uint8_t*)rt.p(wn(std::string(prefix)+"inject.weight")),rt.u(t+".norm",row),rt.u(t+".low",row),rt.u(t+".act",row),rt.u(t+".gate",row),rt.u(t+".mix",row),rt.u(t+".inject",row),(float*)rt.p(t+".scratch",row),(float*)rt.p(t+".workspace",row),(uint32_t*)rt.p("error",row),(uint32_t*)rt.p("active",row),(uint32_t*)rt.p("position",row),CAP};}
 void hc(const std::string&t,unsigned row,unsigned batch){if(preparing){++prepare_steps;hc_bound(t,row);if(batch==2)hc_bound(t,1);return;}std::array<p60::Bound,2>b{hc_bound(t,row),hc_bound(t,batch==2?1:row)};
#ifdef OWN_RT_HOST_ONLY
 auto prefix=std::string(t=="a"?"hc_attn_":"hc_ffn_");for(unsigned r=0;r<batch;++r)p60::host_norm(b[r]);warm_ahead({{b[0].low_w,rt.mem.at(wn(prefix+"down.weight")).bytes},{b[0].inject_w,rt.mem.at(wn(prefix+"inject.weight")).bytes}});for(unsigned r=0;r<batch;++r)p60::host_low_inject(b[r]);warm_ahead({{b[0].gate_w,rt.mem.at(wn(prefix+"up.weight")).bytes}});for(unsigned r=0;r<batch;++r)p73hc::host(b[r]);
#else
 if(batch==1){auto prefix=std::string(t=="a"?"hc_attn_":"hc_ffn_");rt.record("hc_norm",p60::norm_kernel(rt.queue(),b[0],{}));warm_ahead({{b[0].low_w,rt.mem.at(wn(prefix+"down.weight")).bytes},{b[0].inject_w,rt.mem.at(wn(prefix+"inject.weight")).bytes}});rt.record("hc_low_inject",p60::low_inject_kernel(rt.queue(),b[0],{}));warm_ahead({{b[0].gate_w,rt.mem.at(wn(prefix+"up.weight")).bytes}});rt.record("hc_gate_mix",p73hc::device(rt.queue(),b[0],{}));}
 else{rt.record("hc_norm",p166hc::norm_kernel(rt.queue(),b,batch,{}));rt.record("hc_low_inject",p166hc::low_inject_kernel(rt.queue(),b,batch,{}));rt.record("hc_gate_mix",p166hc::gate_mix(rt.queue(),b,batch,{}));}
#endif
 }
 Matrix matrix(std::string w,std::string x,std::string y,unsigned k,unsigned n,unsigned split,unsigned row,unsigned batch){require(rt.mem.contains(y+".partial"),"scratch must be preallocated");auto[t,rb]=formats.at(w);auto variant=integrated::arithmetic::r5_variant(t,n,k,1,false);split=(variant==1||variant==4||variant==7)?4:1;return {(uint8_t*)rt.p(wn(w)),{rt.u(x,row),rt.u(x,batch==2?1:row)},{rt.u(y,row),rt.u(y,batch==2?1:row)},{(float*)rt.p(y+".partial",row),(float*)rt.p(y+".partial",batch==2?1:row)},k,n,split,rb,t};}
 template<unsigned batch> void dense_impl(std::string cls,std::vector<Matrix>m){if(preparing){++prepare_steps;for(auto&b:m)require(b.w&&b.x[0]&&b.x[1]&&b.y[0]&&b.y[1],"matrix bindings");return;}
#ifdef OWN_RT_HOST_ONLY
 for(auto b:m)for(unsigned out=0;out<b.n;++out){float part[2][4]{};for(unsigned z=0;z<b.split;++z){auto bounds=iq3::kopt2::bounds(b.k,z,b.split);float leaves[2][32];for(unsigned l=0;l<32;++l){auto v=lane(b,out,bounds.first,bounds.second,l,batch);for(unsigned r=0;r<batch;++r)leaves[r][l]=v[r];}for(unsigned r=0;r<batch;++r){part[r][z]=iq3::tree32(leaves[r]);if(b.split==4&&cls!="small_tuple"&&b.n!=512)b.scratch[r][out*8+z]=part[r][z];}}
 for(unsigned r=0;r<batch;++r){b.y[r][out]=iq3::bf16_bits(b.split==1?part[r][0]:(part[r][0]+part[r][1])+(part[r][2]+part[r][3]));
 if(proof){unsigned variant=integrated::arithmetic::r5_variant(b.type,b.n,b.k,1,false);auto expected=iq3::bf16_bits(integrated::arithmetic::row(b.type,b.w+size_t(out)*b.rb,b.x[r],b.k,variant));require(b.y[r][out]==expected,"dense arithmetic oracle mismatch");}}}
#else
 std::array<Matrix,4>bs{};require(m.size()<=4,"tuple size");std::copy(m.begin(),m.end(),bs.begin());
 if(cls=="small_tuple"&&m.size()==4){
  std::array<std::array<p39::Bound,4>,2>bb{};
  for(unsigned t=0;t<batch;++t)for(unsigned j=0;j<4;++j){auto z=m[j];auto&b=bb[t][j];b.w=z.w;b.x=z.x[t];b.y=z.y[t];b.rows=z.n;b.rb=z.rb;}
  constexpr unsigned total=128+160+160+1;
  rt.record(cls,rt.queue().submit([=](sycl::handler&h){sycl::local_accessor<float,1>scratch(16,h);h.parallel_for(sycl::nd_range<1>(batch*total*128,128),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
   unsigned group=it.get_group_linear_id(),token=group/total;group%=total;auto b=bb[token];auto*p=scratch.get_multi_ptr<sycl::access::decorated::no>().get();
   if(group<128)p49dvirtual::dense_device<Type::F32,2560,4,4,p39::Kind::expert_checks>(b[0],group,it,p);
   else if(group<288)p49dvirtual::dense_device<Type::Q6_K,2560,4,4,p39::Kind::expert_checks>(b[1],group-128,it,p);
   else if(group<448)p49dvirtual::dense_device<Type::Q6_K,2560,4,4,p39::Kind::expert_checks>(b[2],group-288,it,p);
   else p49dvirtual::dense_device<Type::F32,2560,4,4,p39::Kind::expert_checks>(b[3],group-448,it,p);
  });}));return;
 }
 const bool local_split=cls=="small_tuple"||(m.size()==1&&m[0].n==512);
 if(local_split){
  unsigned count=m.size(),rows_per_group=cls=="small_tuple"?1:4,split=m[0].split,work=rows_per_group*split*32,groups=0;
  for(auto b:m)groups+=(b.n+rows_per_group-1)/rows_per_group;
  rt.record(cls,rt.queue().submit([=](sycl::handler&h){sycl::local_accessor<float,1>scratch(batch*rows_per_group*split,h);h.parallel_for(sycl::nd_range<1>(size_t(groups)*work,work),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{
   unsigned idx=it.get_group_linear_id(),j=0;while(j+1<count&&idx>=(bs[j].n+rows_per_group-1)/rows_per_group){idx-=(bs[j].n+rows_per_group-1)/rows_per_group;++j;}auto b=bs[j];unsigned sub=it.get_local_linear_id()/32,l=it.get_local_linear_id()%32,within=sub/split,part=sub%split,out=idx*rows_per_group+within;auto bounds=iq3::kopt2::bounds(b.k,part,split);
   std::array<float,2>v{};if(out<b.n)v=device_lane(b,out,bounds.first,bounds.second,l);
   for(unsigned t=0;t<batch;++t){v[t]=p68c::tree(it.get_sub_group(),v[t]);if(!l)scratch[(t*rows_per_group+within)*split+part]=v[t];}it.barrier(sycl::access::fence_space::local_space);
   if(out<b.n&&!l&&!part)for(unsigned t=0;t<batch;++t){unsigned off=(t*rows_per_group+within)*split;b.y[t][out]=iq3::bf16_bits(split==1?scratch[off]:(scratch[off]+scratch[off+1])+(scratch[off+2]+scratch[off+3]));}
  });}));return;
 }
 unsigned count=m.size(),groups=0;for(auto b:m)groups+=b.n*b.split;
 unsigned work=cls=="attention_projection"?256:32;
 rt.record(cls,rt.queue().submit([=](sycl::handler&h){h.parallel_for(sycl::nd_range<1>(((size_t(groups)*32+work-1)/work)*work,work),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{unsigned idx=it.get_global_linear_id()/32,j=0;if(idx>=groups)return;while(j+1<count&&idx>=bs[j].n*bs[j].split){idx-=bs[j].n*bs[j].split;++j;}auto b=bs[j];unsigned out=idx/b.split,part=idx%b.split,l=it.get_local_linear_id()%32;auto bounds=iq3::kopt2::bounds(b.k,part,b.split);auto v=device_lane(b,out,bounds.first,bounds.second,l);for(unsigned r=0;r<batch;++r){v[r]=p68c::tree(it.get_sub_group(),v[r]);if(!l){if(b.split==1)b.y[r][out]=iq3::bf16_bits(v[r]);else b.scratch[r][out*8+part]=v[r];}}});}));
 for(auto b:m)if(b.split==4){
  if(cls=="attention_projection"){
   unsigned row=(b.y[0]==rt.u("attention",0))?0:1;
   std::array<U*,2>streams{rt.u("streams",row),rt.u("streams",batch==2?1:row)};std::array<const U*,2>inject{rt.u("a.inject",row),rt.u("a.inject",batch==2?1:row)};
   rt.record(cls,rt.queue().submit([=](sycl::handler&h){sycl::local_accessor<float,1>factor(4*batch,h);h.parallel_for(sycl::nd_range<1>(((size_t(b.n)+255)/256)*256,256),[=](sycl::nd_item<1>it){unsigned out=it.get_global_linear_id(),local=it.get_local_linear_id();if(local<4)for(unsigned t=0;t<batch;++t)factor[t*4+local]=2.f*ng::sigmoid(p39::widen(inject[t][local])/4.f);it.barrier(sycl::access::fence_space::local_space);if(out>=b.n)return;for(unsigned t=0;t<batch;++t){auto*p=b.scratch[t]+out*8;auto y=iq3::bf16_bits((p[0]+p[1])+(p[2]+p[3]));b.y[t][out]=y;for(unsigned stream=0;stream<4;++stream){unsigned i=stream*b.n+out;streams[t][i]=iq3::bf16_bits(p39::widen(streams[t][i])+p39::widen(y)*factor[t*4+stream]);}}});}));
  }else rt.record(cls,rt.queue().submit([=](sycl::handler&h){h.parallel_for(sycl::range<1>(b.n),[=](sycl::id<1>i){for(unsigned r=0;r<batch;++r){auto*p=b.scratch[r]+i[0]*8;b.y[r][i[0]]=iq3::bf16_bits((p[0]+p[1])+(p[2]+p[3]));}});}));
 }

#endif
 }
 void dense(std::string cls,std::vector<Matrix>m,unsigned batch){if(!preparing){std::vector<std::pair<const void*,size_t>>spans;for(auto&b:m)spans.push_back({b.w,weight_bytes(b.w)});warm_ahead(spans);}else if(warm)warm_ahead({});if(batch==1)dense_impl<1>(cls,m);else dense_impl<2>(cls,m);
 if(!preparing&&cls=="attention_projection"){unsigned row=m[0].y[0]==rt.u("attention",0)?0:1;
#ifdef OWN_RT_HOST_ONLY
  combine("attention","a.inject",row,batch);
#else
  if(proof)rt.queue().memcpy(rt.p("streams_after_attention",row),rt.p("streams",row),batch*10240*2);
#endif
 }}
 ng::Args args(unsigned row,std::initializer_list<std::pair<int,std::string>>names){ng::Args a{};for(auto[i,n]:names)a.p[i]=rt.p(n,row);a.p[15]=rt.p("error",row);a.p[16]=rt.p("rope");a.p[17]=rt.p("position",row);a.p[18]=rt.p("active",row);return a;}
 void nonmat(std::string cls,ng::Shape s,ng::Args a){if(preparing){++prepare_steps;require(a.p[15]&&a.p[17]&&a.p[18],"nonmatrix controls");return;}
 if(proof&&a.p[17]==rt.p("position",0)&&(s.op==ng::gdn||s.op==ng::conv))a.p[8]=rt.p(s.op==ng::gdn?"state.first":"history.first");
#ifdef OWN_RT_HOST_ONLY
 if(s.op==ng::gdn)p82brec::host<true>(s,a);else if(s.op==ng::select){auto*g=(float*)rt.p("select.scratch",a.p[17]==rt.p("position",0)?0:1);round2::cpu_stage<ng::select,0>(s,a,g);round2::cpu_stage<ng::select,1>(s,a,g);}else ng::cpu(s,a);
#else
 if(s.op==ng::gdn){p82brec::Kernel<true>k;k.shape=s;rt.record(cls,k.submit(rt.queue(),a.p,{}));return;}
 if(s.op==ng::select){auto*g=(float*)rt.p("select.scratch",a.p[17]==rt.p("position",0)?0:1);auto issue=[&]<int Stage>(){rt.record(cls,rt.queue().submit([=](sycl::handler&h){sycl::local_accessor<float,1>scratch(256,h);h.parallel_for(sycl::nd_range<1>(size_t(round2::groups(s))*32,32),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{round2::group<ng::select,Stage>(s,a,it.get_group_linear_id(),g,Team{it,scratch.get_multi_ptr<sycl::access::decorated::no>().get()});});}));};issue.template operator()<0>();issue.template operator()<1>();return;}
 if(s.op==ng::gated_norm||s.op==ng::prepare||s.op==ng::pool){auto issue=[&]<ng::Op Code>(){rt.record(cls,rt.queue().submit([=](sycl::handler&h){sycl::local_accessor<float,1>scratch(ng::local_floats(s),h);h.parallel_for(sycl::nd_range<1>(size_t(ng::groups(s))*256,256),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{p42tiny::cooperative_group<Code>(s,a,it.get_group_linear_id(),Team{it,scratch.get_multi_ptr<sycl::access::decorated::no>().get()});});}));};if(s.op==ng::gated_norm)issue.template operator()<ng::gated_norm>();else if(s.op==ng::prepare)issue.template operator()<ng::prepare>();else issue.template operator()<ng::pool>();return;}
 unsigned work=128,groups=ng::groups(s),local=ng::local_floats(s);
 rt.record(cls,rt.queue().submit([=](sycl::handler&h){sycl::local_accessor<float,1>scratch(local,h);h.parallel_for(sycl::nd_range<1>(size_t(groups)*work,work),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{ng::group(s,a,it.get_group_linear_id(),Team{it,scratch.get_multi_ptr<sycl::access::decorated::no>().get()});});}));
#endif
 }
 void combine(std::string branch,std::string inject,unsigned row,unsigned batch){if(preparing){++prepare_steps;require(rt.p(branch,row)&&rt.p(inject,row),"combine bindings");return;}std::array<U*,2>x{rt.u("streams",row),rt.u("streams",batch==2?1:row)};std::array<const U*,2>b{rt.u(branch,row),rt.u(branch,batch==2?1:row)},g{rt.u(inject,row),rt.u(inject,batch==2?1:row)};
#ifdef OWN_RT_HOST_ONLY
 for(unsigned r=0;r<batch;++r)for(unsigned i=0;i<10240;++i)x[r][i]=p39::combine(x[r][i],b[r][i%2560],g[r][i/2560]);
#else
 rt.record("combine",rt.queue().submit([=](sycl::handler&h){h.parallel_for(sycl::range<1>(batch*10240),[=](sycl::id<1>id){unsigned r=id[0]/10240,i=id[0]%10240;x[r][i]=p39::combine(x[r][i],b[r][i%2560],g[r][i/2560]);});}));
#endif
  if(proof&&branch=="attention"){
#ifdef OWN_RT_HOST_ONLY
   for(unsigned r=0;r<batch;++r)std::memcpy(rt.p("streams_after_attention",row+r),rt.p("streams",row+r),10240*2);
#else
   rt.queue().memcpy(rt.p("streams_after_attention",row),rt.p("streams",row),batch*10240*2);
#endif
  }
 }
 V expert(unsigned r,bool down){V p(19,nullptr);p[0]=rt.p(wn(down?"ffn_down_exps.weight":"ffn_gate_exps.weight"));p[1]=rt.p(wn(down?"ffn_down_exps.weight":"ffn_up_exps.weight"));p[2]=rt.p(down?"ea":"f.mix",r);p[3]=rt.p(down?"ed":"eg",r);p[4]=rt.p(down?"ed":"eu",r);p[5]=rt.p(down?"downroutes":"routes",r);p[6]=rt.p(down?"statusd":"statusg",r);p[7]=rt.p(down?"statusd":"statusu",r);p[16]=rt.p("error",r);p[17]=rt.p("active",r);return p;}
 void experts(unsigned row,unsigned batch,bool down){auto a=expert(row,down),b=expert(batch==2?1:row,down);if(preparing){++prepare_steps;return;}
#ifdef OWN_RT_HOST_ONLY
 if(down){p100::Kernel<2>k;for(unsigned r=0;r<batch;++r)k.run(r?b:a);}else if(batch==1){p90exp::Kernel<Type::IQ2_S,2560,64,false,true>k;k.run(a);}else{V p{a[0],a[1],a[2],b[2],a[3],b[3],a[4],b[4],a[5],b[5],a[6],b[6],a[7],b[7],a[16],b[16],a[17],b[17]};p68c::ExpertKernel<Type::IQ2_S>k;k.run(p);}
#else
 if(down){if(batch==1){p100::Kernel<2>k;rt.record("expert_down",k.submit(rt.queue(),a,{}));}else{a.insert(a.end(),b.begin(),b.end());rt.record("expert_down",p166down::submit(batch,rt.queue(),a,{}));}}
 else if(batch==1){p90exp::Kernel<Type::IQ2_S,2560,64,false,true>k;rt.record("expert_gate_up",k.submit(rt.queue(),a,{}));}else{V p{a[0],a[1],a[2],b[2],a[3],b[3],a[4],b[4],a[5],b[5],a[6],b[6],a[7],b[7],a[16],b[16],a[17],b[17]};p68c::ExpertKernel<Type::IQ2_S>k;rt.record("expert_gate_up",k.submit(rt.queue(),p,{}));}
#endif
 }
 integrated::Spec route_spec(){integrated::Spec s{};s.op=integrated::Op::route;s.ni=1;s.no=4;s.nw=0;s.g.h=2560;s.g.mid=640;s.g.context=CAP;s.site.shape[1]=10;size_t sizes[]={512,10,10,30,30};flash::Scalar types[]={flash::Scalar::bf16,flash::Scalar::u32,flash::Scalar::f32,flash::Scalar::u32,flash::Scalar::u32};for(int i=0;i<5;++i){s.sizes[i]=sizes[i];s.types[i]=types[i];}return s;}
 V route_args(unsigned r){V p;for(auto n:{"router","ids","prob","routes","downroutes","route.scratch","error","position","active","rope","sg","su","sa"})p.push_back(rt.p(n,r));return p;}
 void route(unsigned row,unsigned batch){auto s=route_spec();auto p=route_args(row),b=route_args(batch==2?1:row);if(preparing){++prepare_steps;return;}
#ifdef OWN_RT_HOST_ONLY
 p109route::Kernel k;k.spec=s;k.run(p);if(batch==2)k.run(b);
#else
 if(batch==1){p109route::Kernel k;k.spec=s;rt.record("route_shared_activation",k.submit(rt.queue(),p,{}));}else{p.insert(p.end(),b.begin(),b.end());rt.record("route_shared_activation",p166route::submit(s,batch,rt.queue(),p,{}));}
#endif
 }
 V shared_args(unsigned r){V p{rt.p(wn("ffn_down_shexp.weight"))};for(auto n:{"sa","down","ed","prob","mixture","shared_gate","one","moe","error","position","active"})p.push_back(rt.p(n,r));return p;}
 void shared(unsigned row,unsigned batch){auto a=shared_args(row),b=shared_args(batch==2?1:row);if(preparing){++prepare_steps;if(warm)warm_ahead({});return;}warm_ahead({{rt.p(wn("ffn_down_shexp.weight")),rt.mem.at(wn("ffn_down_shexp.weight")).bytes}});
#ifdef OWN_RT_HOST_ONLY
 p109::SharedDown k;k.capacity=CAP;k.run(a);if(batch==2)k.run(b);
#else
 if(batch==1){p109::SharedDown k;k.capacity=CAP;rt.record("shared_down_mix",k.submit(rt.queue(),a,{}));}else{std::array<p109::TailBound,2>bb{p109::bind(a,CAP),p109::bind(b,CAP)};
 rt.record("shared_down_mix",rt.queue().submit([=](sycl::handler&h){h.parallel_for(sycl::nd_range<1>(2560*32,32),[=](sycl::nd_item<1>it)[[sycl::reqd_sub_group_size(32)]]{unsigned r=it.get_group_linear_id(),lane=it.get_local_linear_id();auto v=p68c::dense_lane<Type::Q8_0>(bb[0].weight+r*760,bb[0].input,bb[1].input,640,0,640,lane);for(unsigned t=0;t<2;++t){v[t]=p68c::tree(it.get_sub_group(),v[t]);if(!lane)p109::tail(bb[t],r,v[t]);}});}));}
#endif
 }
 void attention(unsigned row,unsigned batch){if(preparing){++prepare_steps;require(rt.p("selected",row)&&rt.p("keys")&&rt.p("values"),"attention bindings");return;}ng::Shape s{};s.op=ng::attention_score;s.tokens=batch;s.capacity=CAP;s.budget=BUDGET;s.extent=64;auto a=args(row,{{0,"q"},{1,"gate"},{2,"keys"},{3,"values"},{4,"selected"},{5,"y"},{6,"scores"},{7,"probabilities"}});
#ifdef OWN_RT_HOST_ONLY
 p47ref::cpu_split(s,a);
#else
 auto e=p47::candidate(rt.queue(),s,a,(int*)rt.p("counts",row),(float*)rt.p("qsa.scratch",row),true);for(auto ev:e)rt.record("qsa_attention",ev);
#endif
 }
 void run(unsigned row,unsigned batch){require(!stopped,"cooperative stop");hc("a",row,batch);auto mat=[&](std::string w,std::string x,std::string y,unsigned k,unsigned n,unsigned split){return matrix(w,x,y,k,n,split,row,batch);};ng::Shape s{};s.tokens=batch;s.capacity=CAP;s.budget=BUDGET;s.extent=64;s.flags=8;
 if(layer==0){dense("projection",{mat("attn_qkv.weight","a.mix","qkv",2560,10240,4)},batch);dense("projection",{mat("attn_gate.weight","a.mix","z",2560,6144,4)},batch);dense("small_tuple",{mat("ssm_alpha.weight","a.mix","alpha",2560,48,4),mat("ssm_beta.weight","a.mix","beta",2560,48,4)},batch);
 s.op=ng::conv;s.width=10240;s.extra=1;nonmat("conv",s,args(row,{{0,"qkv"},{1,"history"},{2,wn("ssm_conv1d.weight")},{3,"conv"},{4,"history"}}));
 s.op=ng::gdn;s.flags=14;s.extra=0;nonmat("gdn_recurrence",s,args(row,{{0,"conv"},{1,"alpha"},{2,"beta"},{3,wn("ssm_a")},{4,wn("ssm_dt.bias")},{5,"state"},{6,"y"},{7,"state"}}));
 s.op=ng::gated_norm;s.heads=48;s.flags=8;nonmat("gdn_norm_gate",s,args(row,{{0,"y"},{1,"z"},{2,wn("ssm_norm.weight")},{3,"gated"}}));
 dense("attention_projection",{mat("ssm_out.weight","gated","attention",6144,2560,4)},batch);
 }else{dense("projection",{mat("attn_q.weight","a.mix","qgate",2560,12288,4)},batch);dense("projection",{mat("attn_k.weight","a.mix","k",2560,512,4)},batch);dense("projection",{mat("attn_v.weight","a.mix","v",2560,512,4)},batch);dense("projection",{mat("indexer.q_proj.weight","a.mix","iq",2560,512,4)},batch);dense("projection",{mat("indexer.k_proj.weight","a.mix","ik",2560,128,4)},batch);
 s.op=ng::prepare;nonmat("qsa_prepare",s,args(row,{{0,"qgate"},{1,"k"},{2,"iq"},{3,wn("attn_q_norm.weight")},{4,wn("attn_k_norm.weight")},{5,wn("indexer.q_norm.weight")},{6,"q"},{7,"gate"},{8,"kn"},{9,"iqn"}}));
 s.op=ng::pool;nonmat("qsa_pool",s,args(row,{{0,"kn"},{1,"v"},{2,"ik"},{3,wn("indexer.k_norm.weight")},{4,"keys"},{5,"values"},{6,"raw"},{7,"pooled"}}));s.op=ng::select;nonmat("qsa_select",s,args(row,{{0,"iqn"},{1,"pooled"},{2,"selected"}}));attention(row,batch);dense("attention_projection",{mat("attn_output.weight","y","attention",6144,2560,4)},batch);
 }
 hc("f",row,batch);
 dense("small_tuple",{mat("ffn_gate_inp.weight","f.mix","router",2560,512,4),mat("ffn_gate_shexp.weight","f.mix","sg",2560,640,4),mat("ffn_up_shexp.weight","f.mix","su",2560,640,4),mat("ffn_gate_inp_shexp.weight","f.mix","shared_gate",2560,1,4)},batch);
 route(row,batch);experts(row,batch,false);s.op=ng::activation;s.width=6400;s.extra=1;s.flags=0;nonmat("expert_activation",s,args(row,{{0,"eg"},{1,"eu"},{2,"ea"}}));experts(row,batch,true);shared(row,batch);combine("moe","f.inject",row,batch);rt.wait();
 }
 void valid(){
 for(auto n:{"error","statusg","statusu","statusd"})for(auto v:rt.mem.at(n).host)require(v==0,std::string("nonzero native status: ")+n);
 for(auto&[n,m]:rt.mem){bool bf=!n.starts_with("w:")&&n!="rope"&&((m.stride&&m.stride==m.bytes/2&&m.stride%2==0)||n=="state"||n=="history"||n=="state.first"||n=="history.first"||n=="keys"||n=="values"||n=="raw"||n=="pooled");
 if(n=="position"||n=="active"||n=="error"||n=="one"||n=="ids"||n=="prob"||n=="routes"||n=="downroutes"||n.starts_with("status")||n.ends_with("scratch")||n.ends_with("workspace")||n.ends_with("partial")||n=="selected"||n=="counts"||n=="scores"||n=="probabilities")bf=false;
 if(bf){auto*v=(const U*)m.host.data();for(size_t i=0;i<m.bytes/2;++i)require((v[i]&0x7f80)!=0x7f80,"nonfinite BF16: "+n);}}
 }
 std::map<std::string,std::vector<uint8_t>> snapshot(){rt.download();valid();std::map<std::string,std::vector<uint8_t>>out;for(auto&[n,m]:rt.mem)if(!n.starts_with("w:")&&n!="rope"){auto*p=(uint8_t*)m.host.data();out[n]={p,p+m.bytes};}return out;}
};
static void pass(Layer&l){l.evict();l.run(0,1);l.evict();l.run(1,1);}
int main(int argc,char**argv){try{bool real=false,device=false;unsigned repeats=240;std::string mode="",oracle_path="";int rank=-1;constexpr unsigned POS=31,SEED=166+POS;
 if(argc==2&&std::string(argv[1])=="--help"){std::cout<<"--rank 0 --mode cpu|device --weights synthetic|real --oracle PATH --repeats 240 --coordinator-admitted-device-window\n";return 0;}
 for(int i=1;i<argc;++i){std::string k=argv[i];if(k=="--coordinator-admitted-device-window"){device=true;continue;}require(i+1<argc,"missing option argument");std::string v=argv[++i];if(k=="--rank"){require(v=="0","rank must be0");rank=0;}else if(k=="--mode"){require(v=="cpu"||v=="device","mode");mode=v;}else if(k=="--weights"){require(v=="synthetic"||v=="real","weights");real=v=="real";}else if(k=="--oracle"){oracle_path=v;}else if(k=="--repeats"){require(v=="240","240 repeats required");repeats=240;}else throw std::runtime_error("unknown option "+k);}
 require(rank==0&&!mode.empty(),"rank/mode required");
 if(auto*out=std::getenv("ENTRY_PREPARE_OUTPUT")){require(mode=="device"&&device&&real,"real launch arguments required");preparing=true;sensors.open(std::filesystem::path(out)/"real-arm-sensors.jsonl");require(bool(sensors),"sensor output");
  for(unsigned layer:{0u,3u}){Layer l(layer,false);l.init_weights();l.init_buffers();for(unsigned arm:{0u,1u}){l.warm=arm==1;l.proof=true;l.reset(POS,SEED);l.sensor(POS,arm,0);pass(l);}
   for(unsigned rep=0;rep<repeats;++rep)for(unsigned j=0;j<2;++j){unsigned arm=(rep+j)%2;l.warm=arm==1;l.proof=false;l.reset(POS,SEED);l.sensor(POS,arm,rep+1);pass(l);}}
  sensors.close();std::cout<<"PASS CPU preparation before first device call; real reset/arm sequence, synthetic weight transport; no arithmetic qualification\n";return 0;}
#ifdef OWN_RT_HOST_ONLY
 require(mode=="cpu"&&!device,"CPU binary mode");
#else
 require(mode=="device"&&device&&real,"device execution requires real weights and admission");
#endif
 std::map<std::string,std::string> oracle;
 if(mode=="device"){require(!oracle_path.empty(),"device needs the inherited GNU/Intel agreed real-weight oracle");std::ifstream f(oracle_path);require(bool(f),"CPU oracle missing");unsigned l,p;std::string n,hash;while(f>>l>>p>>n>>hash){require(hash.size()==64,"oracle digest");require(oracle.emplace(std::to_string(l)+"/"+std::to_string(p)+"/"+n,hash).second,"duplicate oracle");}require(f.eof()&&!oracle.empty(),"CPU oracle parse");}
 std::signal(SIGTERM,stop);std::signal(SIGINT,stop);
 bool all=true;
 for(unsigned layer:{0u,3u}){Layer l(layer,real);l.init_weights();l.init_buffers();
  // Reference: arm A with proof stores (packet166 M1 rows 0 and 1, same reset seed).
  l.proof=true;l.warm=false;l.reset(POS,SEED);pass(l);auto expected=l.snapshot();
  // Arm B with proof stores must match in every buffer, proof-only buffers included.
  l.proof=true;l.warm=true;l.reset(POS,SEED);pass(l);auto actual=l.snapshot();size_t diffs=0;
  for(auto&[n,v]:expected){size_t d=0;require(actual.at(n).size()==v.size(),"snapshot extent");for(size_t i=0;i<v.size();++i)d+=v[i]!=actual.at(n)[i];diffs+=d;if(mode=="device"&&semantic_buffer(n)){auto key=std::to_string(layer)+"/"+std::to_string(POS)+"/"+n;require(oracle.contains(key)&&oracle.at(key)==digest(v),"CPU oracle differs: "+key);}std::cout<<"{\"kind\":\"bytes\",\"layer\":"<<layer<<",\"position\":"<<POS<<",\"buffer\":\""<<n<<"\",\"compared_bytes\":"<<v.size()<<",\"different_bytes\":"<<d<<",\"sha256\":\""<<digest(v)<<"\"}\n";}all=all&&!diffs;
#ifndef OWN_RT_HOST_ONLY
  require(!diffs,"device A/B exactness failed");
  for(unsigned rep=0;rep<repeats;++rep)for(unsigned j=0;j<2;++j){unsigned arm=(rep+j)%2;l.proof=false;l.warm=arm==1;l.reset(POS,SEED);pass(l);auto timed=l.snapshot();size_t checked=0;for(auto&[n,v]:expected)if(n!="state.first"&&n!="history.first"&&n!="streams_after_attention"){require(timed.at(n)==v,"timed arm oracle mismatch: "+n);++checked;}std::cout<<"{\"kind\":\"oracle\",\"layer\":"<<layer<<",\"position\":"<<POS<<",\"repeat\":"<<rep<<",\"arm\":"<<arm<<",\"passed\":true,\"compared_buffers\":"<<checked<<"}\n";unsigned index=0;for(auto&[cls,e]:l.rt.events){auto start=e.get_profiling_info<sycl::info::event_profiling::command_start>(),end=e.get_profiling_info<sycl::info::event_profiling::command_end>();std::cout<<"{\"kind\":\"sample\",\"layer\":"<<layer<<",\"position\":"<<POS<<",\"repeat\":"<<rep<<",\"arm\":"<<arm<<",\"event\":"<<index++<<",\"class\":\""<<cls<<"\",\"start_ns\":"<<start<<",\"end_ns\":"<<end<<"}\n";}std::cout<<std::flush;}
#endif
 }
 std::cout<<"{\"kind\":\"summary\",\"passed\":"<<(all?"true":"false")<<",\"drained\":true,\"identity\":\"iq3-p49-split32-v1\",\"layer_complete\":true,\"intermediate_checks_complete\":true,\"zero_errors\":true,\"finite_outputs\":true,\"ab_byte_identical\":"<<(all?"true":"false")<<",\"cpu_oracle_match\":"<<(mode=="device"?"true":"false")<<",\"backend\":\""<<(mode=="device"?"device":"cpu")<<"\"}\n";return all?0:1;
}catch(const std::exception&e){std::cerr<<"REFUSED: "<<e.what()<<'\n';return 1;}}
