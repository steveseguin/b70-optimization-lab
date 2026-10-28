#pragma once
#include "pipeline/provider_only/wire.hpp"
#include <filesystem>
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
namespace ownrt::provider_only {
struct Witness {recursive_provider::SeedRecord seed;recursive_provider::FinalRecord final;std::vector<uint8_t> hidden;};
// Explicit provider role: seed owner is target stage0 even for a standalone
// process. Never set context.stage=1 just to bypass the older target-stage Peer.
class ReadOnlyMap {
 std::filesystem::path path_;int fd_=-1;const uint8_t* bytes_=nullptr;struct stat initial_{};
public:
 ReadOnlyMap(const std::filesystem::path& path,size_t size):path_(path){
  ring_next::need(path.is_absolute(),"provider peer absolute path");
  fd_=::open(path.c_str(),O_RDONLY|O_NOFOLLOW|O_NONBLOCK);
  ring_next::need(fd_>=0,"provider peer readonly open");
  if(::fstat(fd_,&initial_)||!S_ISREG(initial_.st_mode)||uint64_t(initial_.st_size)!=size){::close(fd_);fd_=-1;throw std::runtime_error("provider peer regular exact extent");}
  auto p=::mmap(nullptr,size,PROT_READ,MAP_SHARED,fd_,0);
  if(p==MAP_FAILED){::close(fd_);fd_=-1;throw std::runtime_error("provider peer readonly mapping");}bytes_=static_cast<const uint8_t*>(p);
 }
 ~ReadOnlyMap(){if(bytes_)::munmap(const_cast<uint8_t*>(bytes_),size_t(initial_.st_size));if(fd_>=0)::close(fd_);}
 ReadOnlyMap(const ReadOnlyMap&)=delete;ReadOnlyMap&operator=(const ReadOnlyMap&)=delete;
 size_t size()const{return size_t(initial_.st_size);}
 const uint8_t* data()const{return bytes_;}
 bool same_inode(const ReadOnlyMap& other)const{return initial_.st_dev==other.initial_.st_dev&&initial_.st_ino==other.initial_.st_ino;}
 void identity(bool immutable=false)const{
  struct stat current{},named{};
  ring_next::need(!::fstat(fd_,&current)&&!::lstat(path_.c_str(),&named)&&S_ISREG(named.st_mode)&&
   current.st_dev==initial_.st_dev&&current.st_ino==initial_.st_ino&&current.st_size==initial_.st_size&&
   named.st_dev==initial_.st_dev&&named.st_ino==initial_.st_ino&&named.st_size==initial_.st_size,
   "provider peer inode/extent changed");
  if(immutable)ring_next::need(current.st_mtim.tv_sec==initial_.st_mtim.tv_sec&&current.st_mtim.tv_nsec==initial_.st_mtim.tv_nsec&&
   current.st_ctim.tv_sec==initial_.st_ctim.tv_sec&&current.st_ctim.tv_nsec==initial_.st_ctim.tv_nsec,"provider replay archive changed");
 }
};
class LivePeers {
 ReadOnlyMap seed_,final_;
public:
 LivePeers(const std::filesystem::path& seed,const std::filesystem::path& final):seed_(seed,wire::shared_bytes),final_(final,wire::shared_bytes){ring_next::need(!seed_.same_inode(final_),"provider seed/final owners must differ");}
 Witness capture(const ring_next::wire::Context& context){
  ring_next::wire::context(context);seed_.identity();final_.identity();
  const auto a=recursive_provider::seed_published(seed_.data()),b=recursive_provider::published(final_.data());
  ring_next::need(a>0&&b>0,"provider target peers have no committed publication");Witness out;
  std::memcpy(&out.seed,seed_.data()+recursive_provider::seed_record_offset,sizeof out.seed);
  std::memcpy(&out.final,final_.data()+recursive_provider::final_record_offset,sizeof out.final);
  out.hidden.assign(final_.data()+live_draft::hidden_offset,final_.data()+live_draft::hidden_offset+context.stream_bytes);
  ring_next::need(a==recursive_provider::seed_published(seed_.data())&&b==recursive_provider::published(final_.data())&&
   out.seed.published_sequence==a&&out.final.published_sequence==b,"provider target publication changed during capture");
  seed_.identity();final_.identity();recursive_provider::seed_row(out.seed,context);
  recursive_provider::validate_final_record(out.final,context,out.hidden);return out;
 }
};
} // namespace ownrt::provider_only
