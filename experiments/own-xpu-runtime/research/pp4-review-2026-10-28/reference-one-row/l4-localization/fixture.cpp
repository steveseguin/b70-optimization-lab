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
enum {GGML_TYPE_F32,GGML_TYPE_I32};
enum {GGML_OP_RESHAPE,GGML_OP_MUL,GGML_OP_RMS_NORM,GGML_OP_SCALE,GGML_OP_DSV4_HC_PRE,GGML_OP_MUL_MAT,GGML_OP_UNARY,GGML_OP_SSM_CONV,GGML_OP_REPEAT,GGML_OP_VIEW};
enum {GGML_UNARY_OP_SIGMOID,GGML_UNARY_OP_SILU};
int ggml_get_unary_op(ggml_tensor*){return GGML_UNARY_OP_SIGMOID;} // mock never observes unary nodes
void ggml_backend_tensor_get(ggml_tensor*t,void*out,size_t off,size_t n){std::memcpy(out,(char*)t->data+off,n);}
#include "l4-capture.hpp"
static void setup(ggml_tensor&t,const char*name,int op,int a,int b,int e,int d,void*data){
 std::strcpy(t.name,name);t.type=GGML_TYPE_F32;t.op=op;t.ne[0]=a;t.ne[1]=b;t.ne[2]=e;t.ne[3]=d;t.nb[0]=4;
 for(int i=1;i<4;++i)t.nb[i]=t.nb[i-1]*t.ne[i-1];t.data=data;
}
int main(int argc,char**argv){assert(argc==2);std::filesystem::create_directory(argv[1]);
 L4Capture c;c.out=argv[1];c.batch_tokens=244;
 std::vector<float>history(128*16*244);for(size_t i=0;i<history.size();++i)history[i]=float(i);
 ggml_tensor q;setup(q,"q_conv_predelta-4",GGML_OP_SCALE,128,16,244,1,history.data());
 for(int i=0;i<3;++i)assert(capture_l4(&q,true,&c)&&c.seen.empty());
 assert(capture_l4(&q,false,&c)&&!c.failed);
 std::ifstream f(c.out+"/q_conv_predelta-4.f32",std::ios::binary);std::vector<float>saved(history.size());f.read((char*)saved.data(),saved.size()*4);assert(saved==history);
 assert(capture_l4(&q,false,&c)&&c.failed); // duplicate cannot cancel
 c.failed=false;std::vector<float>state(128*128*48,0.f);ggml_tensor s;setup(s,"state_predelta-4",GGML_OP_RESHAPE,128,128,48,1,state.data());
 assert(capture_l4(&s,false,&c)&&!c.failed); // whole-batch initial state only
 std::vector<float>gate(48*244);ggml_tensor g;setup(g,"gate-4",GGML_OP_MUL,48,244,1,1,gate.data());assert(capture_l4(&g,false,&c)&&!c.failed);
 c.failed=false;ggml_tensor bad;setup(bad,"k_conv_predelta-4",GGML_OP_SCALE,128,17,244,1,history.data());assert(capture_l4(&bad,false,&c)&&c.failed);
 assert(!l4_complete(c)); // partial fixture must never qualify a real model capture
}
