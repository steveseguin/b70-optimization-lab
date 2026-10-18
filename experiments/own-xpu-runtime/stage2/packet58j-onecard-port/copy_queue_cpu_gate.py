#!/usr/bin/env python3
"""Compile actual copy-queue constructor fragments against a CPU interop mock.
No SYCL library, Level Zero loader or device is loaded. The old handle must be
rejected by the documented v2 contract; the fixed handle must retain the
copy-only ordinal, asynchronous mode and explicit ownership.
"""
from compile_turn import turn
import hashlib,json,os,subprocess,tempfile
from pathlib import Path
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 pre=r'''
#include <cstdint>
#include <memory>
#include <stdexcept>
#include <vector>
#include <variant>
#include <string>
#include <type_traits>
constexpr int ZE_RESULT_SUCCESS=0, ZE_STRUCTURE_TYPE_COMMAND_QUEUE_GROUP_PROPERTIES=1,
 ZE_STRUCTURE_TYPE_COMMAND_QUEUE_DESC=2, ZE_COMMAND_QUEUE_MODE_ASYNCHRONOUS=3;
constexpr int ZE_COMMAND_QUEUE_FLAG_IN_ORDER=2;
constexpr int ZE_COMMAND_QUEUE_GROUP_PROPERTY_FLAG_COPY=1,ZE_COMMAND_QUEUE_GROUP_PROPERTY_FLAG_COMPUTE=2;
struct Q{};struct L{};using ze_command_queue_handle_t=Q*;using ze_command_list_handle_t=L*;
struct ze_command_queue_group_properties_t {int stype=0;int flags=0;unsigned numQueues=0;};
struct ze_command_queue_desc_t {int stype=0;unsigned ordinal=0;int mode=0;int flags=0;};
bool created=false;int native_=1,native_device=2,d=2,context=1,handler=0,properties=7;int*context_=&context;
int zeDeviceGetCommandQueueGroupProperties(int,unsigned*n,ze_command_queue_group_properties_t*g){
 if(!g){*n=3;return 0;}g[0].flags=3;g[0].numQueues=1;g[1].flags=1;g[1].numQueues=0;g[2].flags=1;g[2].numQueues=1;return 0;}
void descriptor(const ze_command_queue_desc_t*p){if(p->ordinal!=2||p->mode!=3||p->stype!=2)throw std::runtime_error("wrong engine/descriptor");created=true;}
int zeCommandQueueCreate(int,int,const ze_command_queue_desc_t*p,Q**out){descriptor(p);static Q q;*out=&q;return 0;}
int zeCommandListCreateImmediate(int,int,const ze_command_queue_desc_t*p,L**out){descriptor(p);if(p->flags!=ZE_COMMAND_QUEUE_FLAG_IN_ORDER)throw std::runtime_error("in-order flag missing");static L l;*out=&l;return 0;}
namespace sycl {
 enum class backend {ext_oneapi_level_zero};
 namespace ext::oneapi::level_zero {enum class ownership {keep};}
 struct queue{};
 struct Input {std::variant<Q*,L*> handle;int device;ext::oneapi::level_zero::ownership owner;int props;};
 template<backend>queue make_queue(Input in,int ctx,int){
  if(!std::holds_alternative<L*>(in.handle))throw std::runtime_error("UR_RESULT_ERROR_UNSUPPORTED_FEATURE");
  if(in.device!=2||ctx!=1||in.props!=7||in.owner!=ext::oneapi::level_zero::ownership::keep)throw std::runtime_error("interop contract changed");return {};
 }
}
std::unique_ptr<sycl::queue>copy_queue_;
'''
 records=[];sources={str(Path(__file__).relative_to(ROOT)):sha(Path(__file__))}
 with tempfile.TemporaryDirectory(prefix="copy-queue-cpu-",dir=P/"build") as tmp:
  for name,source,fixed in (("parent",P.parent/"packet58-onecard/single_device.cpp",False),("58b",P/"single_device.cpp",True)):
   s=source.read_text();start=s.index("uint32_t n=0;");end=s.index('label_+=":copy-only-ordinal=',start)
   body=s[start:end];handle="ze_command_list_handle_t" if fixed else "ze_command_queue_handle_t"
   suffix='return created&&bool(copy_queue_)?0:2;}catch(const std::exception&e){return std::string(e.what())=="UR_RESULT_ERROR_UNSUPPORTED_FEATURE"?44:3;}}'
   code=pre+"int main(){"+handle+" native_copy_=nullptr;try {"+body+suffix
   cpp=Path(tmp)/(name+".cpp");binary=Path(tmp)/name;cpp.write_text(code)
   with turn():subprocess.run(["g++","-std=c++20","-O0",str(cpp),"-o",str(binary)],check=True)
   result=subprocess.run([str(binary)])
   assert result.returncode==(0 if fixed else 44),(name,result.returncode)
   sources[str(source.relative_to(ROOT))]=sha(source)
   records.append(dict(variant=name,exit_code=result.returncode,expected=True))
 row=dict(passed=True,device_executed=False,schema="packet58b.copy-queue-cpu.v1",sources=sources,records=records,
  checks=["old regular handle rejected", "immediate handle accepted", "copy-only nonempty ordinal", "asynchronous mode", "native in-order flag", "keep ownership", "same context/device/properties"],
  limitation="CPU interop contract mock; native import and DMA still require coordinator K1")
 (P/"evidence/copy-queue-cpu.json").write_text(json.dumps(row,indent=2)+"\n");print(json.dumps(row))
if __name__=="__main__":main()
