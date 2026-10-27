// OpenCL CPU-device bitwise test of the actual round2 GDN producer/consumer bodies.
#include "stage2/packet194-expert-diet-engine/round2_submit.cpp"
#include <algorithm>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <string>
#include <vector>

struct Fixture {
 std::vector<unsigned char> qkv=std::vector<unsigned char>(40960),gate=std::vector<unsigned char>(192),beta=std::vector<unsigned char>(192);
 std::vector<unsigned char> input=std::vector<unsigned char>(3145728),state=std::vector<unsigned char>(3145728),y=std::vector<unsigned char>(24576);
 std::vector<float> decay=std::vector<float>(48),bias=std::vector<float>(48),scratch=std::vector<float>(round2::gdn_prep_floats);
 int32_t active=1,error=0,pos=0;
 bool f32=false,alias=false;
 size_t unit()const{return f32?4:2;}
 void put(std::vector<unsigned char>& v,size_t i,float x){if(f32)std::memcpy(v.data()+4*i,&x,4);else{uint16_t b=ng::Args::bits(x);std::memcpy(v.data()+2*i,&b,2);}}
 ng::Args args(){ng::Args a;a.f32=f32;a.p[0]=qkv.data();a.p[1]=gate.data();a.p[2]=beta.data();a.p[3]=decay.data();a.p[4]=bias.data();a.p[5]=alias?state.data():input.data();a.p[6]=y.data();a.p[7]=state.data();a.p[15]=&error;a.p[17]=&pos;a.p[18]=&active;a.p[19]=scratch.data();return a;}
};

static Fixture make_fixture(bool f32,bool alias,int scenario){
 Fixture d;d.f32=f32;d.alias=alias;uint32_t seed=0x43a975+scenario;
 auto fill=[&](std::vector<unsigned char>& v){for(size_t i=0;i<v.size()/d.unit();++i){seed=1664525*seed+1013904223;d.put(v,i,float(int(seed%257)-128)/512.f);}};
 fill(d.qkv);fill(d.gate);fill(d.beta);fill(d.input);fill(d.state);
 for(size_t i=0;i<d.y.size()/d.unit();++i)d.put(d.y,i,std::bit_cast<float>(0x7e317e31u));
 for(int h=0;h<48;++h){d.decay[h]=-0.125f-float(h)/512;d.bias[h]=float(int(h%9)-4)/16;}
 if(scenario==1)d.active=0;
 if(scenario==2)d.pos=-1;
 if(scenario==3){d.put(d.gate,0,20.f);d.put(d.gate,1,19.875f);d.put(d.gate,2,-100.f);d.put(d.beta,0,-100.f);d.put(d.beta,1,100.f);d.put(d.qkv,0,std::bit_cast<float>(1u));d.put(d.qkv,1,std::bit_cast<float>(0x8001u));}
 if(scenario==4)d.error=7;
 if(alias)d.state=d.input;
 return d;
}

struct DeviceData {
 sycl::queue q;
 unsigned char *qkv,*gate,*beta,*input,*state,*y;float *decay,*bias,*scratch;int32_t *active,*error,*pos;
 DeviceData(const Fixture& d):q(sycl::cpu_selector_v){
  auto bytes=[&](const std::vector<unsigned char>& v){return v.size();};
  qkv=sycl::malloc_shared<unsigned char>(bytes(d.qkv),q);gate=sycl::malloc_shared<unsigned char>(bytes(d.gate),q);beta=sycl::malloc_shared<unsigned char>(bytes(d.beta),q);
  input=sycl::malloc_shared<unsigned char>(bytes(d.input),q);state=sycl::malloc_shared<unsigned char>(bytes(d.state),q);y=sycl::malloc_shared<unsigned char>(bytes(d.y),q);
  decay=sycl::malloc_shared<float>(48,q);bias=sycl::malloc_shared<float>(48,q);scratch=sycl::malloc_shared<float>(round2::gdn_prep_floats,q);
  active=sycl::malloc_shared<int32_t>(1,q);error=sycl::malloc_shared<int32_t>(1,q);pos=sycl::malloc_shared<int32_t>(1,q);
  copy_in(d);
 }
 void copy_in(const Fixture& d){
  auto cp=[&](unsigned char* p,const std::vector<unsigned char>& v){std::memcpy(p,v.data(),v.size());};cp(qkv,d.qkv);cp(gate,d.gate);cp(beta,d.beta);cp(input,d.input);cp(state,d.state);cp(y,d.y);
  std::memcpy(decay,d.decay.data(),192);std::memcpy(bias,d.bias.data(),192);*active=d.active;*error=d.error;*pos=d.pos;
 }
 ng::Args args(bool f32,bool alias){ng::Args a;a.f32=f32;a.p[0]=qkv;a.p[1]=gate;a.p[2]=beta;a.p[3]=decay;a.p[4]=bias;a.p[5]=alias?state:input;a.p[6]=y;a.p[7]=state;a.p[15]=error;a.p[17]=pos;a.p[18]=active;return a;}
 void run(bool candidate,ng::Shape s,bool f32,bool alias,int rows=1){auto a=args(f32,alias);float* prepared=scratch;
  if(candidate){q.parallel_for(sycl::nd_range<1>(16*32,32),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{round2::gdn_prep_device(s,a,prepared,it);}).wait_and_throw();
   if(rows==2)q.parallel_for(sycl::nd_range<1>(3072*32,32),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{round2::gdn_device2<true>(s,a,prepared,it,6144);});
   else q.parallel_for(sycl::nd_range<1>(1536*32,32),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{round2::gdn_device4<true>(s,a,prepared,it,6144);});
  }else q.parallel_for(sycl::nd_range<1>(6144*32,32),[=](sycl::nd_item<1> it)[[sycl::reqd_sub_group_size(32)]]{round2::gdn_device<false>(s,a,prepared,it);});
  q.wait_and_throw();
 }
 void copy_out(Fixture& d){auto cp=[&](std::vector<unsigned char>& v,const unsigned char* p){std::memcpy(v.data(),p,v.size());};cp(d.state,state);cp(d.y,y);d.active=*active;d.error=*error;d.pos=*pos;if(!d.alias)cp(d.input,input);}
 void next_token(){if(state!=input)q.memcpy(input,state,3145728).wait();}
 ~DeviceData(){for(void* p:{(void*)qkv,(void*)gate,(void*)beta,(void*)input,(void*)state,(void*)y,(void*)decay,(void*)bias,(void*)scratch,(void*)active,(void*)error,(void*)pos})sycl::free(p,q);}
};

static size_t compare(const Fixture& a,const Fixture& b){
 size_t n=0;auto eq=[&](const void* x,const void* y,size_t bytes){if(std::memcmp(x,y,bytes)){auto p=static_cast<const unsigned char*>(x),q=static_cast<const unsigned char*>(y);size_t i=0;while(p[i]==q[i])++i;std::fprintf(stderr," mismatch offset=%zu ref=%02x cand=%02x refword=%08x candword=%08x\n",i,p[i],q[i],*(const uint32_t*)(p+(i&~3ull)),*(const uint32_t*)(q+(i&~3ull)));throw std::runtime_error("bitwise mismatch");}n+=bytes;};
 eq(a.state.data(),b.state.data(),a.state.size());eq(a.y.data(),b.y.data(),a.y.size());eq(&a.error,&b.error,4);eq(&a.pos,&b.pos,4);eq(&a.active,&b.active,4);return n;
}

int main(){try{
 size_t bytes=0;unsigned cases=0,calls=0;
 for(int rows:{2,4})for(bool f32:{false,true})for(bool packed:{false,true})for(bool alias:{false,true})for(int scenario=0;scenario<5;++scenario){
  Fixture ref=make_fixture(f32,alias,scenario),cand=ref;DeviceData dr(ref),dc(cand);
  if(!cases)std::fprintf(stderr,"device: %s\n",dr.q.get_device().get_info<sycl::info::device::name>().c_str());
  ng::Shape s{};s.op=ng::gdn;s.tokens=1;s.capacity=4096;s.flags=2|8|(packed?4:0)|(f32?ng::f32_activations_flag:0);
  for(int t=0;t<4;++t){dr.run(false,s,f32,alias);dc.run(true,s,f32,alias,rows);dr.copy_out(ref);dc.copy_out(cand);bytes+=compare(ref,cand);++calls;
   if(scenario!=2){++*dr.pos;++*dc.pos;}dr.next_token();dc.next_token();
  }
  ++cases;
 }
 std::printf("PASS cases=%u calls=%u full_state_bytes=%llu total_compared_bytes=%zu\n",cases,calls,(unsigned long long)calls*3145728ull,bytes);return 0;
 }catch(const std::exception& e){std::fprintf(stderr,"FAIL %s\n",e.what());return 1;}}
