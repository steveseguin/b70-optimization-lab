"""Development transform: share actual reset/arm traversal with CPU transport."""
from pathlib import Path
P=Path(__file__).resolve().parent;p=P/'micro.cpp';s=p.read_text()
s=s.replace('#include <chrono>','#include <chrono>\n#include <optional>\n#include <sys/resource.h>\n#include <sys/statvfs.h>\n#include <sys/sysinfo.h>')
s=s.replace('static volatile std::sig_atomic_t stopped=0;','static volatile std::sig_atomic_t stopped=0;\nstatic bool preparing=false;\nstatic std::ofstream sensors;\nstatic unsigned prepare_steps=0;')
s=s.replace(' sycl::queue q{sycl::gpu_selector_v,{sycl::property::queue::in_order{},sycl::property::queue::enable_profiling{}}};',' std::optional<sycl::queue> device_queue;\n sycl::queue& queue(){require(!preparing,"device API forbidden during CPU preparation");if(!device_queue)device_queue.emplace(sycl::gpu_selector_v,sycl::property_list{sycl::property::queue::in_order{},sycl::property::queue::enable_profiling{}});return *device_queue;}')
s=s.replace(' m.ptr=sycl::malloc_device(bytes,q);require(m.ptr,"device allocation");q.memset(m.ptr,0,bytes).wait_and_throw();',' if(preparing)m.ptr=m.host.data();else{m.ptr=sycl::malloc_device(bytes,queue());require(m.ptr,"device allocation");queue().memset(m.ptr,0,bytes).wait_and_throw();}')
s=s.replace(' q.memcpy(m.ptr,m.host.data(),m.bytes).wait_and_throw();',' if(!preparing)queue().memcpy(m.ptr,m.host.data(),m.bytes).wait_and_throw();')
s=s.replace(' for(auto&[name,m]:mem)if(!name.starts_with("w:"))q.memcpy(m.host.data(),m.ptr,m.bytes);q.wait_and_throw();',' if(!preparing){for(auto&[name,m]:mem)if(!name.starts_with("w:"))queue().memcpy(m.host.data(),m.ptr,m.bytes);queue().wait_and_throw();}')
s=s.replace(' void wait(){q.wait_and_throw();}',' void wait(){if(!preparing)queue().wait_and_throw();}')
s=s.replace(' q.wait_and_throw();for(auto&[name,m]:mem)sycl::free(m.ptr,q);',' if(device_queue){queue().wait_and_throw();for(auto&[name,m]:mem)sycl::free(m.ptr,queue());}')
s=s.replace('rt.q','rt.queue()')
s=s.replace('formats[name]={t,rb};int fd=-1;','formats[name]={t,rb};if(preparing)continue;int fd=-1;')
s=s.replace('{std::ifstream f(std::string(P166_ROOT)+"/rope.bf16",std::ios::binary);','{if(!preparing){std::ifstream f(std::string(P166_ROOT)+"/rope.bf16",std::ios::binary);').replace('require(bool(f),"rope bytes");rt.upload("rope");}','require(bool(f),"rope bytes");rt.upload("rope");}}')
s=s.replace(' void hc(const std::string&t,unsigned row,unsigned batch){',' void hc(const std::string&t,unsigned row,unsigned batch){if(preparing){++prepare_steps;hc_bound(t,row);if(batch==2)hc_bound(t,1);return;}')
s=s.replace('template<unsigned batch> void dense_impl(std::string cls,std::vector<Matrix>m){','template<unsigned batch> void dense_impl(std::string cls,std::vector<Matrix>m){if(preparing){++prepare_steps;for(auto&b:m)require(b.w&&b.x[0]&&b.x[1]&&b.y[0]&&b.y[1],"matrix bindings");return;}')
s=s.replace(' if(cls=="attention_projection"){unsigned row=', ' if(!preparing&&cls=="attention_projection"){unsigned row=')
s=s.replace(' void nonmat(std::string cls,ng::Shape s,ng::Args a){',' void nonmat(std::string cls,ng::Shape s,ng::Args a){if(preparing){++prepare_steps;require(a.p[15]&&a.p[17]&&a.p[18],"nonmatrix controls");return;}')
s=s.replace(' void combine(std::string branch,std::string inject,unsigned row,unsigned batch){',' void combine(std::string branch,std::string inject,unsigned row,unsigned batch){if(preparing){++prepare_steps;require(rt.p(branch,row)&&rt.p(inject,row),"combine bindings");return;}')
s=s.replace('auto a=expert(row,down),b=expert(batch==2?1:row,down);','auto a=expert(row,down),b=expert(batch==2?1:row,down);if(preparing){++prepare_steps;return;}')
s=s.replace('auto p=route_args(row),b=route_args(batch==2?1:row);','auto p=route_args(row),b=route_args(batch==2?1:row);if(preparing){++prepare_steps;return;}')
s=s.replace('auto a=shared_args(row),b=shared_args(batch==2?1:row);','auto a=shared_args(row),b=shared_args(batch==2?1:row);if(preparing){++prepare_steps;return;}')
s=s.replace(' void attention(unsigned row,unsigned batch){',' void attention(unsigned row,unsigned batch){if(preparing){++prepare_steps;require(rt.p("selected",row)&&rt.p("keys")&&rt.p("values"),"attention bindings");return;}')
# Record actual kernel/process/space readings, with no mocked sensor values.
s=s.replace(' void reset(unsigned pos,unsigned seed){',''' void sensor(unsigned pos,unsigned arm,unsigned repeat){
  struct rusage usage{};struct sysinfo info{};struct statvfs disk{};require(!getrusage(RUSAGE_SELF,&usage)&&!sysinfo(&info)&&!statvfs("/",&disk),"real sensors");
  require(uint64_t(usage.ru_maxrss)*1024<=4ull*1024*1024*1024,"CPU memory limit");require(uint64_t(disk.f_bavail)*disk.f_frsize>=27000000000ull,"CPU disk floor");
  auto&m=rt.mem.at("streams");auto*p=(uint8_t*)m.host.data();std::vector<uint8_t>sample(p,p+64);sensors<<"{\\"kind\\":\\"sensor\\",\\"layer\\":"<<layer<<",\\"position\\":"<<pos<<",\\"arm\\":"<<arm<<",\\"repeat\\":"<<repeat<<",\\"max_rss_bytes\\":"<<uint64_t(usage.ru_maxrss)*1024<<",\\"free_ram_bytes\\":"<<uint64_t(info.freeram)*info.mem_unit<<",\\"disk_free_bytes\\":"<<uint64_t(disk.f_bavail)*disk.f_frsize<<",\\"streams_address\\":"<<uintptr_t(m.ptr)<<",\\"state_sample_sha256\\":\\""<<digest(sample)<<"\\",\\"prepare_steps\\":"<<prepare_steps<<"}\\n";
 }
 void reset(unsigned pos,unsigned seed){''')
old='if(std::getenv("ENTRY_PREPARE_OUTPUT")){require(mode=="device"&&device&&real,"real launch arguments required");std::cout<<"PASS parser before device; full preparation gate pending\\n";return 0;}'
new='''if(auto*out=std::getenv("ENTRY_PREPARE_OUTPUT")){require(mode=="device"&&device&&real,"real launch arguments required");preparing=true;sensors.open(std::filesystem::path(out)/"real-arm-sensors.jsonl");require(bool(sensors),"sensor output");
  for(unsigned layer:{0u,3u}){Layer l(layer,false);l.init_weights();l.init_buffers();for(unsigned pos:{2u,3u,31u})for(unsigned rep=0;rep<200;++rep)for(unsigned j=0;j<2;++j){unsigned arm=(rep+j)%2;l.reset(pos,166+pos);l.sensor(pos,arm,rep);if(arm)l.run(0,2);else{l.run(0,1);l.run(1,1);}}}
  sensors.close();std::cout<<"PASS CPU preparation before first device call; real reset/arm sequence, synthetic weight transport; no arithmetic qualification\\n";return 0;}'''
assert old in s;s=s.replace(old,new);p.write_text(s)
