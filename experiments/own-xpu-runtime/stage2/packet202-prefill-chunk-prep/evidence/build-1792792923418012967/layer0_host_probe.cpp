// Synthetic CPU differential proof of the layer0 GDN attention branch core.
// No model files, native owner, device API, service or cache operation.
#include "production_reference.hpp"
#include "chunk_plan.hpp"
#include <openssl/evp.h>
#include <charconv>
#include <cstring>
#include <iostream>
#include <map>
#include <string>
using U16=std::vector<uint16_t>;
constexpr unsigned K=2560,Q=10240,Z=6144,S=48*128*128;
static void need(bool ok,const char* reason){if(!ok)throw std::runtime_error(reason);}
static std::string hash_bytes(const void* data,size_t bytes){unsigned char out[32];unsigned n=0;
 need(EVP_Digest(data,bytes,out,&n,EVP_sha256(),nullptr)==1&&n==32,"SHA256");std::string s;
 for(auto b:out){s+="0123456789abcdef"[b>>4];s+="0123456789abcdef"[b&15];}return s;}
template<class T>static std::string hash(const std::vector<T>&v){return hash_bytes(v.data(),v.size()*sizeof(T));}
static uint16_t bf(float x){return ng::Args::bits(x);}
static size_t number(const char* text){size_t out=0;std::string s(text);auto r=std::from_chars(s.data(),s.data()+s.size(),out);
 need(!s.empty()&&r.ec==std::errc{}&&r.ptr==s.data()+s.size(),"strict unsigned integer required");return out;}
struct Weights {std::vector<uint8_t> qkv,z;std::string raw_qkv,raw_z;size_t stride=0;};
static std::vector<uint8_t> weights(unsigned rows,unsigned seed,std::string& raw_hash){
 constexpr size_t raw_stride=2100;std::vector<uint8_t> raw(rows*raw_stride);
 for(unsigned r=0;r<rows;++r)for(unsigned block=0;block<10;++block){auto b=raw.data()+r*raw_stride+block*210;
  for(unsigned i=0;i<192;++i)b[i]=uint8_t((r*17+block*31+i*13+seed)^(i>>2));
  for(unsigned i=0;i<16;++i)b[192+i]=uint8_t(int((r+block+i+seed)%7)-3);
  b[208]=0;b[209]=0x24; // finite exact FP16 2^-6 scale
 }
 raw_hash=hash(raw);return iq3::expanded::expand(iq3::Type::Q6_K,raw.data(),raw.size(),K);
}
static Weights make_weights(){Weights w;w.stride=iq3::expanded::row_bytes(iq3::Type::Q6_K,K);
 need(w.stride==3380,"expanded resident stride mismatch");w.qkv=weights(Q,7,w.raw_qkv);w.z=weights(Z,19,w.raw_z);
 need(w.qkv.size()==34611200&&w.z.size()==20766720,"p201 stored-byte census mismatch");return w;}
static U16 dense_serial(const std::vector<uint8_t>&w,const uint16_t*x,unsigned rows,size_t stride){U16 y(rows);
 for(unsigned r=0;r<rows;++r){float lanes[32];for(unsigned lane=0;lane<32;++lane)
  lanes[lane]=p33::dense_lane<iq3::Type::Q6_K,K>(w.data()+r*stride,x,0,K,lane);
  y[r]=iq3::bf16_bits(iq3::tree32(lanes));}return y;}
// New pair: one decoded weight/scale, two independent original ordered chains.
// Serial authority above calls frozen p33 directly, not this implementation.
static U16 dense_pair(const std::vector<uint8_t>&w,const U16&x,unsigned rows,size_t stride){U16 y(2*rows);
 for(unsigned r=0;r<rows;++r){float lanes[2][32]{};const auto*row=w.data()+r*stride;
  for(unsigned lane=0;lane<32;++lane)for(unsigned tile=lane*8;tile<K;tile+=256){
   const float scale=iq3::bits_float(iq3::u32(row+K+4*(tile/16)));
   for(unsigned j=0;j<8&&tile+j<K;++j){const float weight=scale*float(iq3::signed8(row[tile+j]));
    const float a=iq3::bits_float(uint32_t(x[tile+j])<<16),b=iq3::bits_float(uint32_t(x[K+tile+j])<<16);
    const float p0=weight*a,p1=weight*b;lanes[0][lane]=lanes[0][lane]+p0;lanes[1][lane]=lanes[1][lane]+p1;
   }
  }
  for(unsigned rowid=0;rowid<2;++rowid)y[rowid*rows+r]=iq3::bf16_bits(iq3::tree32(lanes[rowid]));
 }return y;}
struct Fixture {U16 x,history,state,a,b;std::vector<float> conv_weights,decay,bias;};
static Fixture fixture(const std::string&name){Fixture f;f.x.resize(2*K);f.history.resize(Q*3);f.state.resize(S);f.a.resize(96);f.b.resize(96);
 f.conv_weights.resize(Q*4);f.decay.resize(48);f.bias.resize(48);
 for(unsigned i=0;i<2*K;++i){float value=float(int((i*13+i/K*29)%101)-50)/128.f;
  if(name=="bf16_rounding")value=std::bit_cast<float>(uint32_t(0x3f000000u+((i%8)<<16)+((i&1)?0x8000:0x7fff)))*(i%3?-1.f:1.f);
  f.x[i]=bf(value);}
 if(name=="identical_rows")std::copy_n(f.x.begin(),K,f.x.begin()+K);
 if(name=="swapped_rows")for(unsigned i=0;i<K;++i)std::swap(f.x[i],f.x[K+i]);
 for(unsigned i=0;i<f.history.size();++i)f.history[i]=bf(float(int(i%29)-14)/128.f);
 for(unsigned i=0;i<S;++i)f.state[i]=bf(float(int((i*7)%61)-30)/(name=="nonzero_initial_state"?64.f:512.f));
 for(unsigned i=0;i<96;++i){f.a[i]=bf(float(int(i%9)-4)/16.f);f.b[i]=bf(float(int(i%13)-6)/16.f);}
 for(unsigned i=0;i<Q*4;++i)f.conv_weights[i]=float(int(i%11)-5)/32.f;
 for(unsigned i=0;i<48;++i){f.decay[i]=-.125f-float(i%5)/32.f;f.bias[i]=float(int(i%7)-3)/16.f;}return f;}
struct Controls {int32_t error=0,position=0,active=1;};
static ng::Args controls(Controls&c){ng::Args a;a.p[15]=&c.error;a.p[17]=&c.position;a.p[18]=&c.active;return a;}
static void conv_serial(const uint16_t*input,U16&history,U16&output,Fixture&f,Controls&c){ng::Shape s{ng::conv};s.width=Q;s.tokens=1;s.extra=1;s.flags=8;s.capacity=4096;
 auto a=controls(c);a.p[0]=const_cast<uint16_t*>(input);a.p[1]=history.data();a.p[2]=f.conv_weights.data();a.p[3]=output.data();a.p[4]=history.data();ng::cpu(s,a);}
// Row-major causal writes within each independent channel; trace after row0.
static void conv_pair(const U16&input,U16&history,U16&output,U16&row0,Fixture&f,Controls&c){
 if(!c.active||c.error)return;if(c.position<0||c.position>4094){c.error=1;return;}
 for(unsigned ch=0;ch<Q;++ch){float h[3];for(unsigned j=0;j<3;++j)h[j]=std::bit_cast<float>(uint32_t(history[ch*3+j])<<16);
  for(unsigned r=0;r<2;++r){float x=std::bit_cast<float>(uint32_t(input[r*Q+ch])<<16),acc=0;
   for(unsigned tap=0;tap<4;++tap)acc=acc+(tap==3?x:h[tap])*f.conv_weights[ch*4+tap];
   output[r*Q+ch]=bf(ng::silu(acc));h[0]=h[1];h[1]=h[2];h[2]=x;
   if(!r)for(unsigned j=0;j<3;++j)row0[ch*3+j]=bf(h[j]);
  }for(unsigned j=0;j<3;++j)history[ch*3+j]=bf(h[j]);
 }
}
static ng::Args recurrence_args(const uint16_t*input,const uint16_t*a,const uint16_t*b,U16&state,uint16_t*out,Fixture&f,Controls&c){
 auto args=controls(c);args.p[0]=const_cast<uint16_t*>(input);args.p[1]=const_cast<uint16_t*>(a);args.p[2]=const_cast<uint16_t*>(b);
 args.p[3]=f.decay.data();args.p[4]=f.bias.data();args.p[5]=state.data();args.p[6]=out;args.p[7]=state.data();return args;}
static void recurrent(const uint16_t*input,const uint16_t*a,const uint16_t*b,U16&state,uint16_t*out,Fixture&f,Controls&c,int tokens,uint16_t*row0=nullptr,bool reference=false){
 ng::Shape s{ng::gdn};s.tokens=tokens;s.capacity=4096;s.flags=14;auto args=recurrence_args(input,a,b,state,out,f,c);
 if(reference)round2::gdn_host(s,args);else p202_selected::recurrence_host_rows<4>(s,args,0,6144,row0);
}
struct Results {U16 qkv,z,conv,history0,history,output,state0,state;};
static Results serial(Fixture&f,const Weights&w){Results r;r.history=f.history;r.state=f.state;Controls c;
 for(unsigned row=0;row<2;++row){auto q=dense_serial(w.qkv,f.x.data()+row*K,Q,w.stride);auto z=dense_serial(w.z,f.x.data()+row*K,Z,w.stride);
  r.qkv.insert(r.qkv.end(),q.begin(),q.end());r.z.insert(r.z.end(),z.begin(),z.end());U16 conv(Q),out(Z);
  conv_serial(q.data(),r.history,conv,f,c);recurrent(conv.data(),f.a.data()+row*48,f.b.data()+row*48,r.state,out.data(),f,c,1);
  r.conv.insert(r.conv.end(),conv.begin(),conv.end());r.output.insert(r.output.end(),out.begin(),out.end());
  if(!row){r.history0=r.history;r.state0=r.state;}++c.position;
 }need(!c.error,"serial sticky error");return r;}
static Results chunk(Fixture&f,const Weights&w){Results r;r.history=f.history;r.state=f.state;r.history0.resize(Q*3);r.state0.resize(S);
 r.qkv=dense_pair(w.qkv,f.x,Q,w.stride);r.z=dense_pair(w.z,f.x,Z,w.stride);r.conv.resize(2*Q);r.output.resize(2*Z);Controls c;
 conv_pair(r.qkv,r.history,r.conv,r.history0,f,c);recurrent(r.conv.data(),f.a.data(),f.b.data(),r.state,r.output.data(),f,c,2,r.state0.data());
 need(!c.error,"chunk sticky error");return r;}
static void compare(const char*stage,const U16&a,const U16&b,bool&first){if(!first)std::cout<<',';first=false;
 auto mismatch=std::mismatch(a.begin(),a.end(),b.begin(),b.end());size_t index=size_t(mismatch.first-a.begin());
 std::cout<<"{\"stage\":\""<<stage<<"\",\"serial_sha256\":\""<<hash(a)<<"\",\"chunk_sha256\":\""<<hash(b)<<"\",\"equal\":"<<(a==b?"true":"false")<<",\"bytes\":"<<a.size()*2<<",\"first_mismatch_element\":"<<(a==b?"null":std::to_string(index))<<'}';need(a==b,"differential byte mismatch");}
static void run_case(const std::string&name,const Weights&w){auto f=fixture(name);auto a=serial(f,w),b=chunk(f,w);U16 reference_state=f.state,reference_out(2*Z);Controls c;
 recurrent(b.conv.data(),f.a.data(),f.b.data(),reference_state,reference_out.data(),f,c,2,nullptr,true);
 U16 bad=f.state,badout(Z);Controls second;second.position=1;
 recurrent(b.conv.data()+Q,f.a.data()+48,f.b.data()+48,bad,badout.data(),f,second,1);
 bool negative=bad!=b.state;need(negative,"independent-state negative control did not discriminate");
 bool changed=b.state!=f.state,different=!std::equal(b.output.begin(),b.output.begin()+Z,b.output.begin()+Z);
 std::cout<<"{\"name\":\""<<name<<"\",\"passed\":true,\"active_state_changed\":"<<(changed?"true":"false")<<",\"row0_row1_outputs_differ\":"<<(different?"true":"false")<<",\"comparisons\":[";bool first=true;
 compare("qkv",a.qkv,b.qkv,first);compare("z",a.z,b.z,first);compare("conv_output",a.conv,b.conv,first);
 compare("conv_history_after_row0",a.history0,b.history0,first);compare("conv_history_final",a.history,b.history,first);
 compare("gdn_output",a.output,b.output,first);compare("state_after_row0",a.state0,b.state0,first);compare("state_final",a.state,b.state,first);
 compare("round2_reference_output",reference_out,b.output,first);compare("round2_reference_state",reference_state,b.state,first);
 std::cout<<"],\"negative_controls\":{\"independent_state_differs\":true,\"wrong_state_sha256\":\""<<hash(bad)<<"\"},\"inputs\":{\"activation_sha256\":\""<<hash(f.x)<<"\",\"initial_state_sha256\":\""<<hash(f.state)<<"\",\"initial_history_sha256\":\""<<hash(f.history)<<"\"}}";
}
static void binding_checks(){using p202::Region;std::map<std::string,bool> checks;
 auto rejects=[&](std::initializer_list<Region> regions){try{p202::validate_bindings(std::span(regions.begin(),regions.size()));return false;}catch(const std::invalid_argument&){return true;}};
 checks["partial_write_alias_refused"]=rejects({{1000,16,8,true},{1004,16,8,true}});
 checks["read_write_alias_refused"]=rejects({{1000,16,8,false},{1004,16,8,true}});
 checks["readonly_alias_allowed"]=!rejects({{1000,16,8,false},{1004,16,8,false}});
 checks["adjacent_allowed"]=!rejects({{1000,16,8,true},{1016,16,8,true}});
 checks["short_extent_refused"]=rejects({{1000,7,8,true}});checks["null_refused"]=rejects({{0,16,8,true}});
 checks["zero_required_refused"]=rejects({{1000,16,0,true}});checks["overflow_refused"]=rejects({{UINTPTR_MAX-3,8,8,true}});
 Fixture f=fixture("distinct_rows");U16 input(2*Q,bf(.5f)),out(2*Z,0x1234),state=f.state,snapshot(S,0x1234);
 for(auto mode:{"inactive_unchanged","sticky_error_unchanged","invalid_position_unchanged"}){Controls c;if(std::string(mode)=="inactive_unchanged")c.active=0;else if(std::string(mode)=="sticky_error_unchanged")c.error=1;else c.position=4095;
  recurrent(input.data(),f.a.data(),f.b.data(),state,out.data(),f,c,2,snapshot.data());checks[mode]=state==f.state&&std::all_of(out.begin(),out.end(),[](auto v){return v==0x1234;})&&std::all_of(snapshot.begin(),snapshot.end(),[](auto v){return v==0x1234;});}
 std::cout<<"{\"passed\":true,\"checks\":{";bool first=true;for(auto [k,v]:checks){need(v,"binding/control check failed");if(!first)std::cout<<',';first=false;std::cout<<'"'<<k<<"\":true";}std::cout<<"}}\n";
}
int main(int argc,char**argv){try{
 if(argc==6&&std::string(argv[1])=="--plan"){auto p=p202::make_plan(number(argv[2]),number(argv[3]),number(argv[4]),number(argv[5]));std::cout<<"{\"spans\":[";bool first=true;for(auto s:p.spans){if(!first)std::cout<<',';first=false;std::cout<<"{\"start\":"<<s.start<<",\"count\":"<<s.count<<",\"final\":false}";}std::cout<<"],\"final_position\":"<<p.final_position<<"}\n";return 0;}
 if(argc==2&&std::string(argv[1])=="--binding-check"){binding_checks();return 0;}
 const std::vector<std::string> all{"distinct_rows","identical_rows","swapped_rows","bf16_rounding","nonzero_initial_state"};std::vector<std::string> names;
 if(argc==2&&std::string(argv[1])=="--all")names=all;else if(argc==3&&std::string(argv[1])=="--case"&&std::find(all.begin(),all.end(),argv[2])!=all.end())names={argv[2]};else throw std::invalid_argument("use --plan START INPUT_COUNT CONTEXT WIDTH, --binding-check, --all or --case NAME");
 auto w=make_weights();std::cout<<"{\"passed\":true,\"device_executed\":false,\"scope\":\"synthetic Q6 projections and causal conv/GDN branch core; not full layer or device proof\",\"variant\":6,\"split\":1,\"expanded_row_bytes\":"<<w.stride<<",\"synthetic_qkv_sha256\":\""<<hash(w.qkv)<<"\",\"synthetic_z_sha256\":\""<<hash(w.z)<<"\",\"packed_qkv_sha256\":\""<<w.raw_qkv<<"\",\"packed_z_sha256\":\""<<w.raw_z<<"\",\"cases\":[";
 bool first=true;for(auto name:names){if(!first)std::cout<<',';first=false;run_case(name,w);}std::cout<<"]}\n";return 0;
 }catch(const std::exception&e){std::cerr<<"REFUSED: "<<e.what()<<'\n';return 1;}}
