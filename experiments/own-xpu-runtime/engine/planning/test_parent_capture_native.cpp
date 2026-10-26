// Focused Host-only peer/admission ownership and exact capture wire fixture.
#include <cmath>
#include <sstream>
#include <iomanip>
#include "pipeline/recursive_provider/batch.hpp"
#include <filesystem>
#include <fstream>
#include <sys/mman.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <cassert>
namespace ownrt {inline std::string quote(const std::string& s){return "\""+s+"\"";}}
namespace pipeline {
namespace fs=std::filesystem;
constexpr size_t slot_bytes=65536,shared_bytes=4*slot_bytes+4096+64;
using ownrt::ring_next::need;
inline void require(bool b,const char* s){need(b,s);}
inline void save(const fs::path& p,const std::string& s){std::ofstream f(p);f<<s;assert(f);}
struct Request{int32_t op,token,position,fixture,speculative,sequence,reserved[2];};
}
#include "pipeline/recursive_provider/admission.hpp"
#include "pipeline/recursive_provider/capture_ready.hpp"
int main(int argc,char** argv){
 assert(argc==2);namespace fs=std::filesystem;namespace w=ownrt::ring_next::wire;namespace rp=ownrt::recursive_provider;
 const fs::path dir=fs::absolute(argv[1]);assert(fs::create_directory(dir));
 const auto path=dir/"shared.bin";int fd=::open(path.c_str(),O_CREAT|O_EXCL|O_RDWR,0600);assert(fd>=0&&::ftruncate(fd,pipeline::shared_bytes)==0);
 auto* map=static_cast<uint8_t*>(::mmap(nullptr,pipeline::shared_bytes,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0));assert(map!=MAP_FAILED);
 w::Context context{0,{},0,4,16,97};context.request[0]=17;
 rp::FinalRecord record;record.stage=3;record.published_sequence=3;record.row.id=1;record.row.position=0;record.row.token=7;record.row.owner=3;record.row.final=1;record.row.publication_ticket=2;record.row.request=context.request;
 record.row.before=ownrt::ring_next::request_prefix(context.request,0);record.row.after=ownrt::ring_next::extend(record.row.before,0,7);record.row.payload_sha=w::digest({});
 record.hidden.bytes=16;record.hidden.position=0;record.hidden.final_stage=3;record.hidden.stages=4;record.hidden.row_ticket=2;record.hidden.commit_sequence=3;record.hidden.input_token=7;
 std::vector<uint8_t> relay(16,23);auto digest=w::digest(relay);constexpr char hex[]="0123456789abcdef";
 for(size_t i=0;i<digest.size();++i){record.hidden.hidden_sha256[2*i]=hex[digest[i]>>4];record.hidden.hidden_sha256[2*i+1]=hex[digest[i]&15];}
 std::memcpy(map+ownrt::live_draft::hidden_offset,relay.data(),relay.size());rp::publish(map,record);
 pipeline::recursive_provider::Peer peer(path);auto event=peer.capture(context,dir/"peer.json");
 ownrt::ring_next::Row seed{0,2,1,7,1,11,1,false,context.request,record.row.after,{}};seed.after=ownrt::ring_next::extend(seed.before,1,11);
 w::RowMeta meta;meta.id=seed.id;meta.parent=seed.parent;meta.position=seed.position;meta.token=seed.token;meta.fixture=seed.fixture;meta.request=seed.request;meta.before=seed.before;meta.after=seed.after;meta.payload_sha=w::digest({});
 pipeline::Request request{27,11,1,1,2,9,{0,0}};
 auto header=record.hidden;
 auto admitted=pipeline::recursive_provider::admit_batch(request,context,seed,event,{reinterpret_cast<const uint8_t*>(&meta),sizeof meta},{reinterpret_cast<const uint8_t*>(&header),sizeof header},relay,1);
 ownrt::recursive_provider_next::Sequence sequence(context);sequence.admit(admitted.input,admitted.expected);
 const auto captured=rp::captured(context,seed,event.record,request.sequence,1);
 // This is exactly the boundary after which final ROW is allowed to overwrite
 // the final owner's buffers. Neither admitted input nor capture identity aliases it.
 std::memset(map+rp::final_record_offset,0xa5,sizeof record);
 std::memset(map+ownrt::live_draft::hidden_offset,0x5a,relay.size());
 std::fill(relay.begin(),relay.end(),99);std::memset(&header,0,sizeof header);
 sequence.admit(admitted.input,admitted.expected);
 assert(admitted.input.hidden==std::vector<uint8_t>(16,23)&&event.hidden==admitted.input.hidden);
 assert(captured.final_record_sha==w::digest({reinterpret_cast<const uint8_t*>(&record),sizeof record}));
 assert(captured.sequence==9&&captured.seed==2&&captured.parent==1&&captured.provider_serial==1);
 std::ofstream out(dir/"capture.bin",std::ios::binary);out.write(reinterpret_cast<const char*>(&captured),sizeof captured);out.close();
 std::ofstream original(dir/"record.bin",std::ios::binary);original.write(reinterpret_cast<const char*>(&record),sizeof record);original.close();
 ::munmap(map,pipeline::shared_bytes);::close(fd);
}
