#pragma once
#include "pipeline/recursive_provider/seed_peer.hpp"
// Included after runtime filesystem/IPC types. The provider never writes
// the final owner's map. Its inode is pinned once and rechecked at every read.
namespace pipeline::recursive_provider {
class Peer {
 fs::path path,last_receipt;int fd=-1;const uint8_t* mapping=nullptr;dev_t device{};ino_t inode{};
public:
 struct Event {ownrt::recursive_provider::FinalRecord record;std::vector<uint8_t> hidden;};
 explicit Peer(fs::path source):path(std::move(source)){require(path.is_absolute(),"recursive final peer path must be absolute");}
 ~Peer(){if(mapping)::munmap(const_cast<uint8_t*>(mapping),shared_bytes);if(fd>=0)::close(fd);}
 Peer(const Peer&)=delete;Peer& operator=(const Peer&)=delete;
 void request_boundary(){
  if(fd<0)return; // initial reset can precede the first lazy peer binding
  struct stat current{},named{};require(!::fstat(fd,&current)&&!::lstat(path.c_str(),&named)&&S_ISREG(named.st_mode)&&current.st_dev==device&&current.st_ino==inode&&current.st_size==shared_bytes&&named.st_dev==device&&named.st_ino==inode&&named.st_size==shared_bytes,"recursive final peer identity changed");
 }
 void open_for(const fs::path& receipt){
  if(fd<0){fd=::open(path.c_str(),O_RDONLY|O_NOFOLLOW|O_NONBLOCK);require(fd>=0,"recursive final peer open");struct stat st{};
   require(!::fstat(fd,&st)&&S_ISREG(st.st_mode)&&st.st_size==shared_bytes,"recursive final peer exact mapping");device=st.st_dev;inode=st.st_ino;
   auto* p=::mmap(nullptr,shared_bytes,PROT_READ,MAP_SHARED,fd,0);require(p!=MAP_FAILED,"recursive final peer readonly mmap");mapping=static_cast<const uint8_t*>(p);
  }
  request_boundary();
  if(last_receipt!=receipt){save(receipt,"{\"path\":"+ownrt::quote(path.string())+",\"device\":"+std::to_string(uint64_t(device))+",\"inode\":"+std::to_string(uint64_t(inode))+",\"bytes\":"+std::to_string(shared_bytes)+",\"readonly\":true}");last_receipt=receipt;
  }

 }
 Event capture(const ownrt::ring_next::wire::Context& context,const fs::path& receipt){
  open_for(receipt);
  const auto before=ownrt::recursive_provider::published(mapping);require(before>0,"recursive final peer has no stable committed event");Event event;
  std::memcpy(&event.record,mapping+ownrt::recursive_provider::final_record_offset,sizeof event.record);
  require(context.stream_bytes>0&&context.stream_bytes<=int(slot_bytes),"recursive peer hidden bound");event.hidden.assign(mapping+ownrt::live_draft::hidden_offset,mapping+ownrt::live_draft::hidden_offset+context.stream_bytes);
  const auto after=ownrt::recursive_provider::published(mapping);require(before==after&&event.record.published_sequence==before,"recursive final event changed while copied");
  ownrt::recursive_provider::validate_final_record(event.record,context,event.hidden);return event;
 }

 ownrt::recursive_provider::SeedRecord capture_seed(const ownrt::ring_next::wire::Context& context,const fs::path& receipt){
  require(context.stage>0&&context.stage<context.stages-1,"remote seed peer owner");open_for(receipt);
  const auto before=ownrt::recursive_provider::seed_published(mapping);require(before>0,"stage0 has no accepted seed journal");
  ownrt::recursive_provider::SeedRecord record;std::memcpy(&record,mapping+ownrt::recursive_provider::seed_record_offset,sizeof record);
  const auto after=ownrt::recursive_provider::seed_published(mapping);require(before==after&&record.published_sequence==before,"accepted seed journal changed while copied");
  ownrt::recursive_provider::seed_row(record,context);return record;
 }
};
}
