#pragma once
// Isolated prerequisite. No native CLI, Owner reset guard or runtime is changed.
#include "pipeline/ring/reset_descriptor.hpp"
#include "pipeline/provider_only/prefill.hpp"
#include <memory>
namespace ownrt::provider_only::suite {
namespace reset=ring_next::reset;
using Context=ring_next::wire::Context;
inline bool geometry(const Context&a,const Context&b){return a.stage==b.stage&&a.stages==b.stages&&a.stream_bytes==b.stream_bytes&&a.vocab==b.vocab&&a.depth==b.depth;}
struct Prepared {
 reset::Descriptor descriptor;Context next;std::unique_ptr<bulk::Prompt> prompt;
 // Caller supplies the ACTUAL owner context after its existing reset succeeds.
 // This proves authority ordering only, not device zeroing or publication reset.
 std::unique_ptr<bulk::Prompt> release_after_owner_reset(const Context& actual){
  ring_next::need(prompt&&geometry(actual,next)&&actual.epoch==next.epoch&&actual.request==next.request,"suite prompt install before actual owner reset");
  prompt->stable();return std::move(prompt);
 }
};
class Suite {
 struct Entry{std::filesystem::path path;std::string sha;size_t count=0;std::unique_ptr<ReadOnlyMap> retained;};
 ReadOnlyMap manifest_;std::string raw_,sha_;int capacity_;Context geometry_;std::vector<Entry> entries_;
 static size_t extent(const std::filesystem::path& path,bool capability){
  ring_next::need(capability,"dedicated suite explicit startup capability");struct stat st{};
  ring_next::need(!::lstat(path.c_str(),&st)&&S_ISREG(st.st_mode)&&st.st_size>0&&st.st_size<=8192,"suite bounded regular manifest");return size_t(st.st_size);
 }
public:
 Suite(const std::filesystem::path& path,const std::string& expected_sha,const std::string& model_sha,const std::string& policy_sha,int capacity,const Context& context,bool capability=false)
 :manifest_(path,extent(path,capability)),capacity_(capacity),geometry_(context){
  ring_next::wire::context(context);manifest_.identity(true);raw_.assign(reinterpret_cast<const char*>(manifest_.data()),manifest_.size());sha_=bulk::hex(bulk::digest_bytes(raw_.data(),raw_.size()));
  ring_next::need(reset::sha(expected_sha)&&sha_==expected_sha&&reset::sha(model_sha)&&reset::sha(policy_sha)&&capacity>=544&&capacity<=262144&&capacity%32==0,"suite startup identities/capacity");
  const auto values=reset::Json(raw_).parse();ring_next::need(values.size()==42,"suite exact manifest fields");
  auto text=[&](const std::string& key){auto i=values.find(key);ring_next::need(i!=values.end()&&i->second.quoted&&std::none_of(i->second.text.begin(),i->second.text.end(),[](char c){return uint8_t(c)<32;}),"suite string field");return i->second.text;};
  auto integer=[&](const std::string& key){auto i=values.find(key);ring_next::need(i!=values.end()&&!i->second.quoted,"suite integer field");uint64_t n=0;const auto& s=i->second.text;auto p=std::from_chars(s.data(),s.data()+s.size(),n);ring_next::need(p.ec==std::errc{}&&p.ptr==s.data()+s.size(),"suite integer range");return n;};
  ring_next::need(text("schema")=="ownrt.dedicated-prompt-suite.v1"&&integer("requests")==12&&integer("context")==uint64_t(capacity)&&integer("max_new")==512&&text("model_identity_sha256")==model_sha&&text("policy_sha256")==policy_sha,"suite fixed twelve-task runtime identity");
  for(size_t i=0;i<12;++i){const auto key="prompt_"+std::to_string(i)+"_";Entry e;e.path=text(key+"path");e.sha=text(key+"sha256");const auto count=integer(key+"tokens");
   ring_next::need(e.path.is_absolute()&&e.path==e.path.lexically_normal()&&reset::sha(e.sha)&&count>=3&&count<=uint64_t(capacity-512),"suite bounded prompt entry");e.count=size_t(count);e.retained=std::make_unique<ReadOnlyMap>(e.path,e.count*4);e.retained->identity(true);
   bulk::Prompt checked(e.path,e.sha,context);ring_next::need(checked.size()==e.count,"suite actual prompt token count");e.retained->identity(true);entries_.push_back(std::move(e));
  }stable();
 }
 void stable()const{manifest_.identity(true);for(const auto&e:entries_)e.retained->identity(true);}
 reset::PromptAuthority authority(size_t index)const{ring_next::need(index<entries_.size(),"suite selected prompt index");stable();const auto&e=entries_[index];return {sha_,e.sha,index,e.count};}
 Prepared prepare(const std::filesystem::path& descriptor,const std::filesystem::path& original,const Context& current,int owner,int command,bool capability=false)const{
  ring_next::need(capability&&geometry(current,geometry_),"suite transition capability/geometry");stable();
  const auto first=reset::parse(reset::read(descriptor),true);const auto selected=authority(first.prompt.index);
  auto d=reset::load_dedicated(descriptor,original,current.epoch,bulk::hex(current.request),owner,command,selected,true);
  ring_next::need(first.raw==d.raw,"suite reset descriptor changed between selection and binding");
  auto next=current;next.epoch=d.next_epoch;next.request=reset::digest(d.next_request);const auto&e=entries_[selected.index];
  auto prompt=std::make_unique<bulk::Prompt>(e.path,e.sha,next);ring_next::need(prompt->size()==e.count&&prompt->prefix(0)==ring_next::request_prefix(next.request,next.epoch),"suite new request prefix authority");stable();
  return {std::move(d),next,std::move(prompt)};
 }
};
} // namespace ownrt::provider_only::suite
