#include <string>
#include <vector>
#include <cstring>
#include <fstream>
#include <cassert>
#include <filesystem>
#include <cstdint>
#include <cstdio>
struct ggml_tensor {char name[64]{};int type=0,op=0;int64_t ne[4]{1,1,1,1};size_t nb[4]{};ggml_tensor*src[2]{};char op_params[16]{};void*data=nullptr;};
constexpr int GGML_TYPE_F32=0,GGML_OP_RESHAPE=1,GGML_OP_MUL=2,GGML_OP_RMS_NORM=3;
void ggml_backend_tensor_get(ggml_tensor*t,void*out,size_t off,size_t n){std::memcpy(out,(char*)t->data+off,n);}
struct NormCapture {
    std::string out; int position=243,batch_start=0,batch_tokens=0;
    bool seen=false,failed=false;
};
static bool capture_norm(ggml_tensor * t,bool ask,void * opaque){
    auto &c=*static_cast<NormCapture*>(opaque);
    bool named=std::strcmp(t->name,"hc_norm-0")==0 && c.position>=c.batch_start && c.position<c.batch_start+c.batch_tokens;
    if(ask)return named&&!c.seen;
    if(!named)return true;
    if(c.seen){c.failed=true;return true;} // never cancel graph evaluation
    c.seen=true;
    auto bad=[&]{c.failed=true;return true;};
    auto *m=t->src[0];auto *r=m?m->src[0]:nullptr;auto *g=m?m->src[1]:nullptr;auto *x=r?r->src[0]:nullptr;
    auto f32=[](ggml_tensor*q){return q&&q->type==GGML_TYPE_F32&&q->nb[0]==4;};
    if(t->op!=GGML_OP_RESHAPE||!m||m->op!=GGML_OP_MUL||!r||r->op!=GGML_OP_RMS_NORM||
       !f32(t)||!f32(x)||!f32(g)||t->ne[0]!=10240||t->ne[1]!=c.batch_tokens||t->ne[2]!=1||t->ne[3]!=1||
       x->ne[0]!=2560||x->ne[1]!=4||x->ne[2]!=c.batch_tokens||x->ne[3]!=1||
       g->ne[0]!=2560||g->ne[1]!=4||g->ne[2]!=1||g->ne[3]!=1)return bad();
    float eps;std::memcpy(&eps,r->op_params,4);if(eps!=1e-6f)return bad();
    const int row=c.position-c.batch_start;
    std::vector<float> input(10240),gain(10240),output(10240);
    for(int stream=0;stream<4;++stream){
      ggml_backend_tensor_get(x,input.data()+stream*2560,size_t(row)*x->nb[2]+stream*x->nb[1],10240);
      ggml_backend_tensor_get(g,gain.data()+stream*2560,stream*g->nb[1],10240);
    }
    ggml_backend_tensor_get(t,output.data(),size_t(row)*t->nb[1],40960);
    auto save=[&](const char*name,const std::vector<float>&v){std::ofstream f(c.out+name,std::ios::binary);f.write((const char*)v.data(),40960);return bool(f);};
    if(!save("/hc-a-input.f32",input)||!save("/hc-a-gain.f32",gain)||!save("/hc-a-output.f32",output))return bad();
    std::ofstream meta(c.out+"/norm-capture.json");
    meta<<"{\"position\":"<<c.position<<",\"dtype\":\"F32\",\"shape\":[4,2560],\"bytes_each\":40960,\"epsilon\":1e-6,\"chain\":\"RESHAPE(MUL(RMS_NORM(input),gain))\",\"occurrence\":1}";
    if(!meta)return bad();
    return true;
}

int main(int argc,char**argv){assert(argc==2);std::filesystem::create_directory(argv[1]);
 std::vector<float> in(10240*244),gain(10240),out(10240*244);for(size_t i=0;i<in.size();++i){in[i]=float(i);out[i]=-float(i);}for(int i=0;i<10240;++i)gain[i]=float(i)/7;
 ggml_tensor t,m,r,g,x;std::strcpy(t.name,"hc_norm-0");t.op=1;m.op=2;r.op=3;t.src[0]=&m;m.src[0]=&r;m.src[1]=&g;r.src[0]=&x;
 for(auto*q:{&t,&g,&x})q->nb[0]=4;
 t.ne[0]=10240;t.ne[1]=244;t.nb[1]=40960;t.data=out.data();
 x.ne[0]=g.ne[0]=2560;x.ne[1]=g.ne[1]=4;x.ne[2]=244;x.nb[1]=g.nb[1]=10240;x.nb[2]=40960;x.data=in.data();g.data=gain.data();float eps=1e-6f;std::memcpy(r.op_params,&eps,4);
 NormCapture c;c.out=argv[1];c.batch_tokens=244;
 for(int i=0;i<5;++i)assert(capture_norm(&t,true,&c)&&!c.seen);assert(capture_norm(&t,false,&c)&&c.seen&&!c.failed);assert(!capture_norm(&t,true,&c));
 for(auto name:{"input","gain","output"}){std::string f=c.out+"/hc-a-"+name+".f32";std::ifstream file(f,std::ios::binary);std::vector<float> v(10240);file.read((char*)v.data(),40960);assert(file.gcount()==40960);for(int i=0;i<10240;++i)assert(v[i]==(std::string(name)=="input"?in[243*10240+i]:std::string(name)=="gain"?gain[i]:out[243*10240+i]));}
 assert(capture_norm(&t,false,&c)&&c.failed); // erroneous duplicate observation cannot cancel
 auto reset=[&]{NormCapture n;n.out=argv[1];n.batch_tokens=244;return n;};
 c=reset();t.ne[1]=1;assert(capture_norm(&t,false,&c)&&c.failed);t.ne[1]=244; // unexpected cropping rejected
 c=reset();m.op=99;assert(capture_norm(&t,false,&c)&&c.failed);m.op=2;
 c=reset();eps=1e-5f;std::memcpy(r.op_params,&eps,4);assert(capture_norm(&t,false,&c)&&c.failed);eps=1e-6f;std::memcpy(r.op_params,&eps,4);
 c=reset();c.out="/does-not-exist/sc117";assert(capture_norm(&t,false,&c)&&c.failed);
 c=reset();std::strcpy(t.name,"hc_norm-1");assert(!capture_norm(&t,true,&c));assert(capture_norm(&t,false,&c)&&!c.seen);
 std::puts("PASS exact norm observer: first observation, duplicate asks, row mapping, shape/op/epsilon/file errors continue");}
