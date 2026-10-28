#include <string>
#include <vector>
#include <set>
#include <algorithm>
#include <cstdio>
#include <fstream>
#include <cstring>
#include <cassert>
#include <cstdint>
#include <filesystem>
struct ggml_tensor {char name[64];int type;int64_t ne[4];size_t nb[4];void* data;};
constexpr int GGML_TYPE_F32=0;
static void ggml_backend_tensor_get(ggml_tensor*t,void*out,size_t off,size_t n){std::memcpy(out,(char*)t->data+off,n);}
struct LayerCapture {
    std::string out; int position=243, batch_start=0, batch_tokens=0;
    std::set<int> seen; std::vector<int> output_positions; bool failed=false;
};
static bool capture_layer(ggml_tensor * t, bool ask, void * opaque) {
    auto & c=*static_cast<LayerCapture *>(opaque);
    int layer=-1, used=0;
    const bool selected=std::sscanf(t->name,"l_last-%d%n",&layer,&used)==1 &&
        t->name[used]=='\0' && layer>=0 && layer<48 &&
        c.position>=c.batch_start && c.position<c.batch_start+c.batch_tokens;
    if(ask)return selected;
    if(!selected)return true;
    int row=c.position-c.batch_start;
    // qwen4exp crops layer47 before FFN to requested logit rows.
    if(layer==47 && t->ne[2]!=c.batch_tokens){
        auto it=std::find(c.output_positions.begin(),c.output_positions.end(),c.position);
        if(t->ne[2]!=int64_t(c.output_positions.size()) || it==c.output_positions.end()){
            c.failed=true;return true; // observer errors must never cancel model evaluation
        }
        row=int(it-c.output_positions.begin());
    }
    if(t->type!=GGML_TYPE_F32 || t->ne[0]!=2560 || t->ne[1]!=4 ||
       row<0 || row>=t->ne[2] || (layer!=47 && t->ne[2]!=c.batch_tokens) || t->ne[3]!=1 || t->nb[0]!=4 ||
       !c.seen.insert(layer).second){c.failed=true;return true;}
    std::vector<float> values(4*2560);
    for(int stream=0;stream<4;++stream)
        ggml_backend_tensor_get(t, values.data()+stream*2560,
            size_t(row)*t->nb[2]+size_t(stream)*t->nb[1],2560*sizeof(float));
    char file[64];std::snprintf(file,sizeof file,"/layer-%02d.f32",layer);
    std::ofstream f(c.out+file,std::ios::binary);
    f.write(reinterpret_cast<const char*>(values.data()),values.size()*sizeof(float));
    if(!f){c.failed=true;return true;}
    return true;
}

int main(int argc,char**argv){assert(argc==2);std::filesystem::create_directory(argv[1]);
 LayerCapture c;c.out=argv[1];c.batch_tokens=244;c.output_positions={243};
 std::vector<float> data(10240*244);for(size_t i=0;i<data.size();++i)data[i]=float(i);
 ggml_tensor t{};t.type=0;t.ne[0]=2560;t.ne[1]=4;t.ne[2]=244;t.ne[3]=1;t.nb[0]=4;t.nb[1]=10240;t.nb[2]=40960;t.data=data.data();
 for(int i=0;i<47;++i){std::snprintf(t.name,64,"l_last-%d",i);assert(capture_layer(&t,true,&c));assert(capture_layer(&t,false,&c));}
 std::strcpy(t.name,"l_last-47");t.ne[2]=1;t.data=data.data()+243*10240;
 assert(capture_layer(&t,true,&c));assert(capture_layer(&t,false,&c));assert(c.seen.size()==48&&!c.failed);
 for(int i=0;i<48;++i){char n[64];std::snprintf(n,64,"/layer-%02d.f32",i);std::ifstream f(c.out+n,std::ios::binary);std::vector<float> v(10240);f.read((char*)v.data(),40960);assert(f.gcount()==40960);for(int j=0;j<10240;++j)assert(v[j]==data[243*10240+j]);}
 // Duplicate, bad shape, absent cropped position and file errors NEVER cancel evaluation.
 assert(capture_layer(&t,false,&c)&&c.failed);
 LayerCapture bad;bad.out=argv[1];bad.batch_tokens=244;bad.output_positions={242};assert(capture_layer(&t,false,&bad)&&bad.failed);
 bad=LayerCapture{};bad.out=argv[1];bad.batch_tokens=244;bad.output_positions={243};t.type=1;assert(capture_layer(&t,false,&bad)&&bad.failed);
 bad=LayerCapture{};bad.out="/does-not-exist/sc117";bad.batch_tokens=244;bad.output_positions={243};t.type=0;assert(capture_layer(&t,false,&bad)&&bad.failed);
 std::puts("PASS exact r2 callback:48 rows, cropped final mapping, duplicate/shape/mapping/file errors never cancel");}
