#include "gsq-rco-iq3s/state-bundle/build/source-v4/l4_raw_history.hpp"
#include <openssl/evp.h>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <functional>
#include <algorithm>
static void require(bool b,const char*s){if(!b)throw std::runtime_error(s);}
struct Request { int32_t op,token,position,fixture,speculative,sequence, reserved[2]; };
struct Reply { int32_t status,token,error,bytes,sequence,rank,reserved[2]; double busy_ms,gpu_ms,redo_ms,reserved_ms; };
static_assert(sizeof(Request)==32&&sizeof(Reply)==64);
struct Mailbox{uint32_t abort=0,reply_sequence=0,request_sequence=0;Request request{};};
static uint32_t load(uint32_t&x){return x;}
static void publish(uint32_t&x,uint32_t n){x=n;}
static double clock_now(){return 0;}
enum {half=1,draft=9};
struct Backend {
 Mailbox&m;std::function<Reply(const Request&)>execute;std::function<void()>cancel=[]{};
 uint32_t seq=0;bool pending[2]={false,false};Request commands[2]{};double sent[2]{};Reply local{};size_t stream_bytes=0;
 void start(int rank,int op,int token=0,int position=0,int fixture=0,int speculative=0){
  require(!pending[rank],"native double pending");cancel();require(!load(m.abort),"native peer failed");Request r{op,token,position,fixture,speculative,0,{0,0}};commands[rank]=r;sent[rank]=clock_now();pending[rank]=true;
  if(rank==0){if(op==draft)r.sequence=position;commands[rank]=r;local=execute(r);if(op==half)stream_bytes=local.bytes;}
  else {require(load(m.reply_sequence)==seq,"native outstanding mailbox");require(seq<UINT32_MAX,"native sequence overflow");r.sequence=int32_t(seq+1);commands[rank]=r;m.request=r;publish(m.request_sequence,++seq);}
 }
};
static std::string hash(const l4raw::Bytes&b){unsigned char d[32];unsigned n;assert(EVP_Digest(b.data(),b.size(),d,&n,EVP_sha256(),nullptr)==1);std::string s;for(auto x:d){s+="0123456789abcdef"[x>>4];s+="0123456789abcdef"[x&15];}return s;}
int main(int argc,char**argv){assert(argc==2);std::filesystem::path out=argv[1];assert(std::filesystem::create_directory(out));
 l4raw::Recorder recorder(out/"history",hash);std::array<l4raw::Bytes,4>fields;for(size_t j=0;j<4;++j)fields[j].assign(l4raw::extents[j],uint8_t(j+1));
 Mailbox box;int position=0;Backend backend{box,[&](const Request&r){
  assert(r.op==half&&r.position==position&&r.sequence==0&&r.reserved[0]==0&&r.reserved[1]==0);
  recorder.begin(r.position,r.sequence,r.token,r.fixture,r.speculative,r.position%2);
  if(r.position==0)recorder.initial_zero(l4raw::Bytes(3145728),l4raw::Bytes(122880));
  recorder.capture(fields);recorder.finish_row();return Reply{};
 }};
 const int length=244;auto fixture=[&](int p){return std::max(0,p-length+2);};
 for(position=0;position<244;++position){backend.start(0,half,42,position,fixture(position),false);backend.pending[0]=false;}
 assert(recorder.complete());
 backend.start(1,half,42,0,0,false);assert(box.request.sequence==1);backend.pending[1]=false;box.reply_sequence=1;
 backend.start(1,half,42,1,0,false);assert(box.request.sequence==2);
 std::cout<<"PASS extracted real Backend::start rank0 HALF sequence0 for244 rows; registered fixture0..0,1; remote rank1 incrementing sequence remains separate\n";
}
