#include "gsq-rco-iq3s/state-bundle/build/source-v4/l4_raw_history.hpp"
#include <openssl/evp.h>
#include <cassert>
#include <iostream>
static std::string hash(const l4raw::Bytes&b){unsigned char d[32];unsigned n;assert(EVP_Digest(b.data(),b.size(),d,&n,EVP_sha256(),nullptr)==1);std::string s;for(auto x:d){s+="0123456789abcdef"[x>>4];s+="0123456789abcdef"[x&15];}return s;}
template<class F>void rejects(F f){bool failed=false;try{f();}catch(const std::runtime_error&){failed=true;}assert(failed);}
int main(int argc,char**argv){assert(argc==2);std::filesystem::path root=argv[1];assert(std::filesystem::create_directory(root));
 l4raw::Bytes zero_state(3145728),zero_history(122880);std::array<l4raw::Bytes,4> data;for(size_t i=0;i<4;++i)data[i].assign(l4raw::extents[i],uint8_t(i+1));
 {l4raw::Recorder r(root/"complete",hash);for(int p=0;p<244;++p){r.begin(p,0,42,p==243?1:0,false,p%2);if(!p)r.initial_zero(zero_state,zero_history);r.capture(data);r.finish_row();}assert(r.complete());rejects([&]{r.begin(0,999,42,0,false,0);});}
 rejects([&]{l4raw::Recorder r(root/"complete",hash);}); // exclusive path, never overwrite
 {l4raw::Recorder r(root/"bad-sequence",hash);rejects([&]{r.begin(1,1,42,0,false,0);});r.begin(0,0,42,0,false,0);r.initial_zero(zero_state,zero_history);r.capture(data);r.finish_row();rejects([&]{r.begin(1,1,42,0,false,1);});assert(!r.complete());}
 {l4raw::Recorder r(root/"wrong-extent",hash);r.begin(0,0,42,0,false,0);r.initial_zero(zero_state,zero_history);auto broken=data;broken[2].pop_back();rejects([&]{r.capture(broken);});assert(std::filesystem::file_size(root/"wrong-extent/history.bin")==0);rejects([&]{r.finish_row();});assert(!std::filesystem::exists(root/"wrong-extent/seal.json"));}
 {l4raw::Recorder r(root/"duplicate",hash);r.begin(0,0,42,0,false,0);r.initial_zero(zero_state,zero_history);r.capture(data);rejects([&]{r.capture(data);});assert(!r.complete());}
 {l4raw::Recorder r(root/"bad-initial",hash);r.begin(0,0,42,0,false,0);zero_history[0]=1;rejects([&]{r.initial_zero(zero_state,zero_history);});assert(!std::filesystem::exists(root/"bad-initial/initial.json"));zero_history[0]=0;}
 {l4raw::Recorder r(root/"speculative",hash);rejects([&]{r.begin(0,0,42,0,true,0);});rejects([&]{r.begin(0,0,42,1,false,0);});}
 std::cout<<"PASS full bounded recorder; ordering, duplicate, speculative, fixture, zero-state, extent, exclusivity and incomplete-seal rejection\n";
}
