// Model-free fixture. Prepared only: compile/run held during measured request.
#include <string>
#include <vector>
#include <set>
#include <algorithm>
#include <cstring>
#include <cstdio>
#include <fstream>
#include <cassert>
#include <cstdint>
#include <filesystem>
struct ggml_tensor{char name[80]{};int type=0,op=0;int64_t ne[4]{1,1,1,1};size_t nb[4]{};ggml_tensor*src[2]{};void*data=nullptr;};
constexpr int GGML_TYPE_F32=0,GGML_TYPE_I32=1,GGML_OP_MUL_MAT=2,GGML_OP_SOFT_MAX=3,GGML_OP_VIEW=4,GGML_OP_DIV=5;
void ggml_backend_tensor_get(ggml_tensor*t,void*out,size_t off,size_t n){std::memcpy(out,(char*)t->data+off,n);}
#include "router-capture.hpp"
int main(int argc,char**argv){assert(argc==2);std::filesystem::create_directory(argv[1]);
 std::vector<int32_t> data(512*244);for(int i=0;i<int(data.size());++i)data[i]=i;
 ggml_tensor t;t.type=GGML_TYPE_I32;t.op=GGML_OP_VIEW;t.ne[0]=10;t.ne[1]=244;t.nb[0]=4;t.nb[1]=2048;t.data=data.data();std::strcpy(t.name,"ffn_moe_topk-4");
 RouterCapture c;c.out=argv[1];c.batch_tokens=244;c.output_positions={243};
 for(int i=0;i<3;++i)assert(capture_router(&t,true,&c)&&c.seen.empty());
 assert(capture_router(&t,false,&c)&&!c.failed);
 std::ifstream f(c.out+"/layer-04-ids.i32",std::ios::binary);int32_t v[10];f.read((char*)v,40);for(int i=0;i<10;++i)assert(v[i]==243*512+i);
 assert(capture_router(&t,false,&c)&&c.failed); // duplicate never cancels
 c.failed=false;std::strcpy(t.name,"ffn_moe_topk-47");t.ne[1]=1;
 assert(capture_router(&t,false,&c)&&!c.failed); // final layer maps to row zero
 c.failed=false;std::strcpy(t.name,"ffn_moe_topk-46");t.ne[1]=1;
 assert(capture_router(&t,false,&c)&&c.failed); // nonfinal crop invalid, continues
 c.failed=false;std::strcpy(t.name,"ffn_moe_weights_norm-5");t.type=GGML_TYPE_F32;t.op=GGML_OP_DIV;t.ne[1]=244;t.nb[1]=40;
 assert(capture_router(&t,false,&c)&&!c.failed);
 std::strcpy(t.name,"unselected");assert(!capture_router(&t,true,&c));assert(capture_router(&t,false,&c));
}
