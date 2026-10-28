// Source-only preparation: real production route stages and real ggml graph, SAME logits.
#include "ggml.h"
#include "ggml-cpu.h"
#include "stage2/packet194-expert-diet-engine/specialised.hpp"
#include <fstream>
#include <filesystem>
#include <iostream>
#include <iomanip>
#include <cstring>
#include <cassert>
#include <numeric>
static void write(std::string p,const void*x,size_t n){std::ofstream f(p,std::ios::binary);f.write((const char*)x,n);assert(f);}
int main(int argc,char**argv){assert(argc==3);std::string input=argv[1],out=argv[2];assert(std::filesystem::create_directory(out));std::vector<float>logits(512);if(input=="--fixture-ties")std::fill(logits.begin(),logits.end(),0.f);else{std::ifstream f(input,std::ios::binary);f.read((char*)logits.data(),2048);assert(f.gcount()==2048);}for(float x:logits)assert(std::isfinite(x));
 std::vector<float>x(2560,0.f),expert(25600),weights(10),scratch;std::vector<int32_t>ids(10,-1),routes(30),down(30);int32_t error=0,position=243,active=1;ng::Shape s;s.op=ng::route_gather;s.width=512;s.extra=10;s.heads=4;s.flags=ng::f32_activations_flag;s.capacity=4096;ng::Args a;a.f32=true;a.p[0]=logits.data();a.p[1]=x.data();a.p[2]=ids.data();a.p[3]=weights.data();a.p[4]=expert.data();a.p[5]=routes.data();a.p[6]=down.data();a.p[15]=&error;a.p[17]=&position;a.p[18]=&active;scratch.resize(specialised::scratch_floats(s));
 auto run=[&]<int ST>(){for(size_t i=0;i<specialised::work_items(s,ST);++i)specialised::body<ng::route_gather,ST>(s,a,i,scratch.data(),specialised::HostGuard{});};run.template operator()<0>();run.template operator()<1>();run.template operator()<2>();run.template operator()<3>();run.template operator()<4>();assert(error==0);const float*nativeprob=scratch.data()+2*((512+31)/32)+512;
 ggml_init_params ip{4*1024*1024,nullptr,false};auto*c=ggml_init(ip);auto*t=ggml_new_tensor_2d(c,GGML_TYPE_F32,512,1);std::memcpy(t->data,logits.data(),2048);auto*probs=ggml_soft_max(c,t);auto*topk=ggml_argsort_top_k(c,probs,10);auto*p3=ggml_reshape_3d(c,probs,1,512,1);auto*w=ggml_get_rows(c,p3,topk);auto*w2=ggml_reshape_2d(c,w,10,1);auto*sum=ggml_sum_rows(c,w2);auto*clamp=ggml_clamp(c,sum,6.103515625e-5f,INFINITY);auto*norm=ggml_div(c,w2,clamp);auto*g=ggml_new_graph(c);ggml_build_forward_expand(g,norm);assert(ggml_graph_compute_with_ctx(c,g,1)==GGML_STATUS_SUCCESS);
 std::ofstream meta(out+"/graph-shapes.json");meta<<"{";bool comma=false;
 for(auto item:{std::pair{"input",t},std::pair{"probs",probs},std::pair{"topk",topk},std::pair{"weights_gather",w},std::pair{"weights_flat",w2},std::pair{"sum",sum},std::pair{"clamp",clamp},std::pair{"norm",norm}}){auto*q=item.second;meta<<(comma?",":"")<<"\""<<item.first<<"\":{\"type\":\""<<ggml_type_name(q->type)<<"\",\"ne\":[";for(int i=0;i<4;++i)meta<<(i?",":"")<<q->ne[i];meta<<"],\"nb\":[";for(int i=0;i<4;++i)meta<<(i?",":"")<<q->nb[i];meta<<"]}";comma=true;}meta<<"}\n";meta.close();assert(meta);
 auto*cpuids=(int32_t*)topk->data;auto*cpuprob=(float*)probs->data;auto*cpuweight=(float*)norm->data;
 write(out+"/input-logits.f32",logits.data(),2048);write(out+"/native-probs.f32",nativeprob,2048);write(out+"/ggml-probs.f32",cpuprob,2048);write(out+"/native-ids.i32",ids.data(),40);write(out+"/ggml-ids.i32",cpuids,40);write(out+"/native-weights.f32",weights.data(),40);write(out+"/ggml-weights.f32",cpuweight,40);write(out+"/native-routes.i32",routes.data(),120);write(out+"/native-routes-down.i32",down.data(),120);
 auto cutoff=[&](const char*label,const float*p){std::vector<int>order(512);std::iota(order.begin(),order.end(),0);std::sort(order.begin(),order.end(),[&](int x,int y){return p[x]>p[y]||(p[x]==p[y]&&x<y);});int a=order[9],b=order[10];std::cout<<label<<" cutoff10_id="<<a<<" cutoff11_id="<<b<<" p10="<<std::setprecision(17)<<p[a]<<" p11="<<p[b]<<" exact_probability_tie="<<(p[a]==p[b])<<" logit10="<<logits[a]<<" logit11="<<logits[b]<<"\n";};cutoff("native",nativeprob);cutoff("ggml",cpuprob);
 int iddiff=0,pdiff=0,wdiff=0;for(int i=0;i<10;++i){iddiff+=ids[i]!=cpuids[i];wdiff+=std::memcmp(&weights[i],&cpuweight[i],4)!=0;std::cout<<"slot="<<i<<" native_id="<<ids[i]<<" ggml_id="<<cpuids[i]<<" native_weight="<<weights[i]<<" ggml_weight="<<cpuweight[i]<<"\n";}for(int i=0;i<512;++i)pdiff+=std::memcmp(nativeprob+i,cpuprob+i,4)!=0;
 std::cout<<"id_slot_differences="<<iddiff<<" probability_bit_differences="<<pdiff<<" weight_bit_differences="<<wdiff<<"\n";
 if(input=="--fixture-ties"){for(int i=0;i<10;++i)assert(ids[i]==i);for(int i=0;i<512;++i)assert(nativeprob[i]==1.f/512.f);for(int i=0;i<10;++i)assert(weights[i]==1.f/10.f);} // no claim about unspecified CPU equal-key order
 ggml_free(c);return 0; // differences are findings; preserve all vectors, no epsilon acceptance
}
