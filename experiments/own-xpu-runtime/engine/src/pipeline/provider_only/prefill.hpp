#pragma once
// Separate authenticated OP15 publication; never an accepted ROW/SeedRecord.
#include "pipeline/provider_only/peers.hpp"
#include "gsq-rco-iq3s/state-bundle/build/source-v4/prefill_wire.hpp"
namespace ownrt::provider_only::bulk {
constexpr uint32_t magic=0x314b4843,ack_magic=0x314b4143,version=1;
constexpr int op=28;constexpr size_t record_offset=1536,ack_offset=1024;
struct Record {
 uint32_t magic_=magic,version_=version,bytes=1280,published_sequence=0;
 uint32_t role=0,stage=0,stages=0,parity=0,start=0,count=0,rows=0,stream_bytes=0;
 uint32_t opcode=15,command_sequence=0,lookahead=UINT32_MAX,reserved=0;
 uint64_t epoch=0;ring_next::Digest request{},prompt_sha{},before{},after{},raw_sha{};
 std::array<uint8_t,24> zero{};std::array<int32_t,256> tokens{};
};
struct Ack {
 uint32_t magic_=ack_magic,version_=version,bytes=256,sequence=0;
 uint32_t start=0,count=0,parity=0,rows=0,stream_bytes=0,stages=0,seed_sequence=0,final_sequence=0,next_seed=0,flags=1,reserved0=0,reserved1=0;
 uint64_t epoch=0,serial=0;ring_next::Digest request{},prompt_sha{},seed_sha{},final_sha{},raw_sha{};
 std::array<uint8_t,16> zero{};
};
static_assert(sizeof(Record)==1280&&sizeof(Ack)==256);
static_assert(record_offset+2*sizeof(Record)==4096&&ack_offset+sizeof(Ack)<=record_offset);
inline ring_next::Digest digest_bytes(const void* p,size_t bytes){return ring_next::wire::digest(std::span<const uint8_t>(static_cast<const uint8_t*>(p),bytes));}
inline std::string hex(const ring_next::Digest& d){constexpr char h[]="0123456789abcdef";std::string s;for(auto b:d){s+=h[b>>4];s+=h[b&15];}return s;}
inline ring_next::Digest parse_sha(const std::string& text){
 ring_next::need(text.size()==64,"bulk prompt SHA extent");ring_next::Digest out{};
 for(size_t i=0;i<64;++i){char c=text[i];int n=c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:-1;ring_next::need(n>=0,"bulk prompt SHA lowercase");out[i/2]|=uint8_t(n<<(i%2?0:4));}return out;
}
class Prompt {
 ReadOnlyMap map_;std::vector<int32_t> tokens_;std::vector<ring_next::Digest> prefixes_;
 static size_t extent(const std::filesystem::path& path){struct stat st{};ring_next::need(!::lstat(path.c_str(),&st)&&S_ISREG(st.st_mode)&&st.st_size>=12&&st.st_size<=262144*4&&st.st_size%4==0,"bulk prompt regular LEi32 extent");return size_t(st.st_size);}
public:
 ring_next::Digest sha{};
 Prompt(const std::filesystem::path& path,const std::string& expected,const ring_next::wire::Context& context)
 :map_(path,extent(path)){
  const size_t n=map_.size();map_.identity(true);sha=digest_bytes(map_.data(),n);ring_next::need(sha==parse_sha(expected),"bulk immutable prompt SHA");tokens_.resize(n/4);
  prefixes_.push_back(ring_next::request_prefix(context.request,context.epoch));
  for(size_t i=0;i<tokens_.size();++i){uint32_t t=0;for(int b=0;b<4;++b)t|=uint32_t(map_.data()[4*i+b])<<(8*b);ring_next::need(t<uint32_t(context.vocab),"bulk prompt vocabulary");tokens_[i]=int32_t(t);prefixes_.push_back(ring_next::extend(prefixes_.back(),uint32_t(i),t));}map_.identity(true);
 }
 void stable()const{map_.identity(true);}
 size_t size()const{return tokens_.size();}
 int token(size_t p)const{ring_next::need(p<tokens_.size(),"bulk immutable lookahead bound");return tokens_[p];}
 const ring_next::Digest& prefix(size_t p)const{ring_next::need(p<prefixes_.size(),"bulk prefix bound");return prefixes_[p];}
};
inline void validate(const Record& r,int role,const ring_next::wire::Context& c,const Prompt& prompt,int rows){
 ring_next::need(r.magic_==magic&&r.version_==version&&r.bytes==sizeof r&&r.published_sequence>0&&r.published_sequence==r.command_sequence&&r.role==uint32_t(role)&&r.stage==uint32_t(role==1?0:c.stages-1)&&r.stages==uint32_t(c.stages)&&r.parity<2&&r.count>0&&r.count<=r.rows&&r.rows==uint32_t(rows)&&rows>0&&rows<=256&&r.stream_bytes==uint32_t(c.stream_bytes)&&r.opcode==15&&!r.reserved&&r.zero==std::array<uint8_t,24>{}&&r.epoch==c.epoch&&r.request==c.request&&r.prompt_sha==prompt.sha,"bulk actual chunk metadata");
 ring_next::need(size_t(r.start)+r.count<=prompt.size()-2&&r.start%r.rows==0&&r.parity==(r.start/r.rows)%2&&r.count==std::min(size_t(r.rows),prompt.size()-2-r.start)&&r.before==prompt.prefix(r.start)&&r.after==prompt.prefix(r.start+r.count),"bulk full no-head prefix extent");
 ring_next::need(role!=1||r.raw_sha==ring_next::Digest{},"bulk seed has no raw payload claim");
 for(size_t i=0;i<256;++i)ring_next::need(r.tokens[i]==(role==1&&i<r.count?prompt.token(r.start+i):0),"bulk actual copied token/padding");
 ring_next::need(r.lookahead==(role==1?uint32_t(prompt.token(r.start+r.count)):UINT32_MAX),"bulk immutable lookahead");
}
inline Record make(const ring_next::wire::Context& c,const Prompt& prompt,int rows,int sequence,int start,int count,int parity,int role,const int* tokens,const uint8_t* raw){
 Record r;r.published_sequence=r.command_sequence=sequence;r.role=role;r.stage=role==1?0:c.stages-1;r.stages=c.stages;r.parity=parity;r.start=start;r.count=count;r.rows=rows;r.stream_bytes=c.stream_bytes;r.epoch=c.epoch;r.request=c.request;r.prompt_sha=prompt.sha;r.before=prompt.prefix(start);r.after=prompt.prefix(start+count);r.raw_sha=role==1?ring_next::Digest{}:digest_bytes(raw,size_t(count)*c.stream_bytes);
 if(role==1){ring_next::need(tokens,"bulk actual target tokens");std::copy_n(tokens,count,r.tokens.begin());r.lookahead=prompt.token(start+count);}validate(r,role,c,prompt,rows);return r;
}
inline void publish(uint8_t* map,const Record& r){
 auto* dest=reinterpret_cast<Record*>(map+record_offset+r.parity*sizeof(Record));__atomic_store_n(&dest->published_sequence,0,__ATOMIC_RELEASE);Record copy=r;copy.published_sequence=0;std::memcpy(dest,&copy,sizeof copy);__atomic_store_n(&dest->published_sequence,r.published_sequence,__ATOMIC_RELEASE);
}
struct Witness {Record seed,final;std::vector<uint8_t> hidden;};
class Peers {
 ReadOnlyMap seed_,final_;int rows_,stream_;
public:
 Peers(const std::filesystem::path& seed,const std::filesystem::path& final,int rows,int stream)
 :seed_(seed,::pipeline::prefill::bytes(rows,stream)),final_(final,::pipeline::prefill::bytes(rows,stream)),rows_(rows),stream_(stream){ring_next::need(rows>0&&rows<=256&&stream>0&&!seed_.same_inode(final_),"bulk readonly distinct bounded peers");}
 Witness capture(const ring_next::wire::Context& c,const Prompt& prompt,int start,int count,int parity){
  ring_next::need(parity>=0&&parity<2&&count>0&&count<=rows_,"bulk command extent");prompt.stable();seed_.identity();final_.identity();Witness w;
  for(const auto* bytes:{seed_.data(),final_.data()}){const auto& h=*reinterpret_cast<const ::pipeline::prefill::Header*>(bytes);ring_next::need(h.magic==::pipeline::prefill::magic&&h.version==::pipeline::prefill::version&&h.rows==uint32_t(rows_)&&h.stream_bytes==uint32_t(stream_),"bulk peer header geometry");}
  const auto* a=reinterpret_cast<const Record*>(seed_.data()+record_offset+parity*sizeof(Record));const auto* b=reinterpret_cast<const Record*>(final_.data()+record_offset+parity*sizeof(Record));auto as=__atomic_load_n(&a->published_sequence,__ATOMIC_ACQUIRE),bs=__atomic_load_n(&b->published_sequence,__ATOMIC_ACQUIRE);ring_next::need(as&&bs,"bulk actual publication absent");
  std::memcpy(&w.seed,a,sizeof w.seed);std::memcpy(&w.final,b,sizeof w.final);validate(w.seed,1,c,prompt,rows_);validate(w.final,2,c,prompt,rows_);
  ring_next::need(w.seed.start==uint32_t(start)&&w.seed.count==uint32_t(count)&&w.seed.parity==uint32_t(parity)&&w.final.start==w.seed.start&&w.final.count==w.seed.count&&w.final.parity==w.seed.parity,"bulk seed/final command pairing");
  const auto* raw=final_.data()+4096+size_t(2+parity)*rows_*stream_;w.hidden.assign(raw,raw+size_t(count)*stream_);
  ring_next::need(w.final.raw_sha==digest_bytes(w.hidden.data(),w.hidden.size()),"bulk actual owned raw SHA");
  ring_next::need(as==__atomic_load_n(&a->published_sequence,__ATOMIC_ACQUIRE)&&bs==__atomic_load_n(&b->published_sequence,__ATOMIC_ACQUIRE)&&as==w.seed.published_sequence&&bs==w.final.published_sequence,"bulk publication changed while copying");
  seed_.identity();final_.identity();prompt.stable();return w;
 }
};
} // namespace ownrt::provider_only::bulk
