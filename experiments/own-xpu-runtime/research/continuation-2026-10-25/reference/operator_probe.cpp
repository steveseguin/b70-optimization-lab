// CPU only. Native headers and the retained CPU reference library are exercised
// directly; no model loading, device enumeration, or inference is performed.
#define OWN_RT_HOST_ONLY
#include "stage2/packet194-expert-diet-engine/specialised.hpp"
#include "vec.h"
#include <bit>
#include <cstdio>
#include <fstream>
#include <stdexcept>
#include <vector>

static void pair(const char* name, float native, float cpu) {
    std::printf("\"%s\":{\"native\":%.9g,\"cpu\":%.9g,\"native_bits\":%u,\"cpu_bits\":%u}",
                name, native, cpu, std::bit_cast<unsigned>(native), std::bit_cast<unsigned>(cpu));
}
static float cpu_dot(const float* a, const float* b) {
    float value = 0;
    ggml_vec_dot_f32(128, &value, 0, a, 0, b, 0, 1);
    return value;
}
static float native_dot(const float* a, const float* b) {
    return specialised::dot128([&](int i) { return a[i]*b[i]; });
}
static std::vector<float> load(const char* path,int n) {
    std::ifstream input(path,std::ios::binary|std::ios::ate);
    if (!input || input.tellg()!=n*4) throw std::runtime_error("fixture extent");
    std::vector<float> v(n);input.seekg(0);input.read(reinterpret_cast<char*>(v.data()),n*4);return v;
}
static void rms(const std::vector<float>& x) {
    const int n = int(x.size()), chunks = specialised::ceildiv(n, 32);
    std::vector<float> partial(chunks);
    for (int c=0; c<chunks; ++c)
        partial[c] = specialised::subtree(n, c, [&](int i) { return x[i]*x[i]; });
    float native_mean = specialised::upper(partial.data(), chunks)/float(n);
    // ggml_compute_forward_rms_norm_f32: F32 square, F64 sum, division
    // in double, and one conversion to F32 before adding epsilon.
    double sum = 0;
    for (float v : x) sum += double(v*v);
    float cpu_mean = sum/n;
    pair("mean", native_mean, cpu_mean); std::printf(",");
    float ni = detmath::rsqrt(native_mean+1e-6f);
    float ci = 1.0f/std::sqrt(cpu_mean+1e-6f);
    pair("inverse", ni, ci);
    int changed=0; double max_delta=0;
    for (float v:x) { float a=v*ni,b=v*ci; changed += std::bit_cast<unsigned>(a)!=std::bit_cast<unsigned>(b); max_delta=std::max(max_delta,std::abs(double(a)-b)); }
    std::printf(",\"normalized_values_differ\":%d,\"max_abs_normalized_delta\":%.17g",changed,max_delta);
}
int main(int argc, char** argv) {
    if (argc != 5) throw std::invalid_argument("operator_probe EMBEDDING.f32 GDN_CONV.f32 STATE.f32 Y.f32");
    std::ifstream input(argv[1],std::ios::binary|std::ios::ate);
    if (!input || input.tellg()!=2560*4) throw std::runtime_error("expected exactly one F32 embedding row");
    std::vector<float> embedding(2560); input.seekg(0); input.read(reinterpret_cast<char*>(embedding.data()),2560*4);
    std::printf("{\"scope\":\"operator witnesses, not attribution of six output discrepancies\",\"rms_frozen_embedding\":{");
    rms(embedding); std::printf("},\"rms_fixed\":{");
    // Positive sums with a known roundoff loss at the first tree node.
    std::vector<float> fixed(2560,0.25f); fixed[0]=4096.f; rms(fixed);
    std::printf("},\"gdn_query_normalization_frozen\":{");
    std::ifstream conv(argv[2],std::ios::binary|std::ios::ate);
    if (!conv || conv.tellg()!=10240*4) throw std::runtime_error("GDN conv extent");
    float query[128];conv.seekg(0);conv.read(reinterpret_cast<char*>(query),sizeof(query));
    const float ns = specialised::dot128([&](int i) { return query[i]*query[i]; });
    double cs=0;for(float q:query) cs+=double(q*q);
    const float cm=cs/128,ci=1.f/std::sqrt(cm+1e-6f/128.f),scale=1.f/std::sqrt(128.f);
    const float ni=std::sqrt(ns+1e-6f);
    int changed=0,formula_only_changed=0;double max_delta=0;
    for (float q:query) {float native=q/ni,cpu=(q*ci)*scale;
        float same_sum=(q*(1.f/std::sqrt(ns/128.f+1e-6f/128.f)))*scale;
        changed+=std::bit_cast<unsigned>(native)!=std::bit_cast<unsigned>(cpu);
        formula_only_changed+=std::bit_cast<unsigned>(native)!=std::bit_cast<unsigned>(same_sum);
        max_delta=std::max(max_delta,std::abs(double(native)-cpu));}
    std::printf("\"values\":128,\"values_differ\":%d,\"formula_only_values_differ\":%d,\"max_abs_delta\":%.17g",changed,formula_only_changed,max_delta);
    std::printf("},\"gdn_fixed\":{");
    float x[128]={},y[128]={};
    x[0]=16777216.f; x[1]=1.f; x[2]=-16777216.f; x[3]=1.f;
    for (float& v:y) v=1.f;
    pair("dot",native_dot(x,y),cpu_dot(x,y));std::printf(",");
    // Exact mathematical update is -2^-46; separate F32 multiplication loses it.
    const float delta=0x1.fffffcp-1f, key=0x1.000002p0f;
    float state[128],keys[128];
    for (int i=0;i<128;++i) { state[i]=-1.f; keys[i]=key; }
    float native_update=state[0]+delta*key;
    ggml_vec_mad_f32(128,state,keys,delta);
    pair("state_update",native_update,state[0]);std::printf(",\"state_update_inputs\":{\"state\":-1,\"delta_bits\":%u,\"key_bits\":%u}",
        std::bit_cast<unsigned>(delta),std::bit_cast<unsigned>(key));
    for (int i=0;i<128;++i) { x[i]=0; y[i]=0; }
    x[0]=-1.f; y[0]=1.f; x[64]=delta; y[64]=key;
    std::printf(",");pair("dot_fma_witness",native_dot(x,y),cpu_dot(x,y));
    // Isolate scale placement using the same native dot reduction on both sides.
    for (int i=0;i<128;++i) { x[i]=float((i*17)%31-15)/7.f; y[i]=float((i*13)%29-14)/11.f; }
    std::printf(",");pair("dot_rational_fixed",native_dot(x,y),cpu_dot(x,y));
    float scaled[128]; for(int i=0;i<128;++i) scaled[i]=y[i]/std::sqrt(128.f);
    std::printf(",");pair("scale_placement_same_reduction",native_dot(x,scaled),native_dot(x,y)*(1.f/std::sqrt(128.f)));
    std::printf("},\"gdn_frozen_post_update_output\":{");
    auto qkv=load(argv[2],10240),post_state=load(argv[3],48*128*128),gpu_y=load(argv[4],48*128);
    int diff[9]={};double maxd[9]={};
    for(int h=0;h<48;++h){
        const float* raw=qkv.data()+(h%16)*128;
        float qnorm[128],qscaled[128],qcpu[128],qr[128],qir[128],qird[128],qcombined[128],qrecipproduct[128];
        float nsum=specialised::dot128([&](int i){return raw[i]*raw[i];});
        double csum=0;for(int i=0;i<128;++i)csum+=double(raw[i]*raw[i]);
        float nden=detmath::sqrt(nsum+1e-6f),cmean=csum/128;
        float cinv=1.f/std::sqrt(cmean+1e-6f/128.f),root=detmath::sqrt(128.f),cscale=1.f/std::sqrt(128.f);
        for(int i=0;i<128;++i){qnorm[i]=raw[i]/nden;qscaled[i]=qnorm[i]/root;qcpu[i]=(raw[i]*cinv)*cscale;
            qr[i]=qnorm[i]*cscale;qir[i]=(raw[i]*(1.f/nden))*cscale;qird[i]=(raw[i]*(1.f/nden))/root;
            qcombined[i]=raw[i]*((1.f/nden)*cscale);qrecipproduct[i]=raw[i]*(1.f/(nden*root));}
        for(int j=0;j<128;++j){int g=h*128+j;const float* row=post_state.data()+g*128;
            float results[9]={native_dot(row,qscaled),cpu_dot(row,qscaled),native_dot(row,qnorm)*cscale,cpu_dot(row,qcpu)*cscale,
                              native_dot(row,qr),native_dot(row,qir),native_dot(row,qird),native_dot(row,qcombined),native_dot(row,qrecipproduct)};
            for(int mode=0;mode<9;++mode){diff[mode]+=std::bit_cast<unsigned>(results[mode])!=std::bit_cast<unsigned>(gpu_y[g]);maxd[mode]=std::max(maxd[mode],std::abs(double(results[mode])-gpu_y[g]));}
        }
    }
    const char* names[]={"native_source_equation_replay","cpu_dot_same_operands","post_scale_same_native_reduction","cpu_normalization_dot_post_scale",
                         "native_reciprocal_constant_scale","native_reciprocal_both","native_reciprocal_norm_only","native_combined_reciprocals","native_reciprocal_product"};
    std::printf("\"values\":6144");
    for(int m=0;m<9;++m)std::printf(",\"%s\":{\"values_differ_from_gpu\":%d,\"max_abs_delta\":%.17g}",names[m],diff[m],maxd[m]);
    std::printf("}}\n");
}
