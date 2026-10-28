from pathlib import Path
import json,hashlib
ROOT=Path('/home/steve/llm-optimizations/experiments/own-xpu-runtime')
HERE=Path(__file__).resolve().parent
source=ROOT/'engine/src/stage2/packet194-expert-diet-engine/native_controller.hpp'
s=source.read_text();a=s.index(' void start(int rank,int op,');b=s.index('\n Reply wait(',a);method=s[a:b]
rank=(ROOT/'engine/src/gsq-rco-iq3s/state-bundle/build/source-v4/rank.hpp').read_text();request=next(x for x in rank.splitlines() if x.startswith('struct Request {'));reply=next(x for x in rank.splitlines() if x.startswith('struct Reply {'))
prefix='''#include "gsq-rco-iq3s/state-bundle/build/source-v4/l4_raw_history.hpp"
#include <openssl/evp.h>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <functional>
#include <algorithm>
static void require(bool b,const char*s){if(!b)throw std::runtime_error(s);}
'''+request+'\n'+reply+'''
static_assert(sizeof(Request)==32&&sizeof(Reply)==64);
struct Mailbox{uint32_t abort=0,reply_sequence=0,request_sequence=0;Request request{};};
static uint32_t load(uint32_t&x){return x;}
static void publish(uint32_t&x,uint32_t n){x=n;}
static double clock_now(){return 0;}
enum {half=1,draft=9};
struct Backend {
 Mailbox&m;std::function<Reply(const Request&)>execute;std::function<void()>cancel=[]{};
 uint32_t seq=0;bool pending[2]={false,false};Request commands[2]{};double sent[2]{};Reply local{};size_t stream_bytes=0;
'''+method+'''\n};
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
 std::cout<<"PASS extracted real Backend::start rank0 HALF sequence0 for244 rows; registered fixture0..0,1; remote rank1 incrementing sequence remains separate\\n";
}
'''
(HERE/'wire-fixture.cpp').write_text(prefix)
(HERE/'wire-fixture-source.json').write_text(json.dumps({'source':str(source),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'extracted_start_sha256':hashlib.sha256(method.encode()).hexdigest(),'limitations':'Actual method extracted unchanged; mailbox/clock/cancel/device-free execute are fixture stubs. Not a whole Engine or device execution test.'},indent=2)+'\n')
