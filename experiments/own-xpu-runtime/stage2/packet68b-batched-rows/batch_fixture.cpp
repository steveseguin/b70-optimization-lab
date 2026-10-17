#include "batched_hc.hpp"
#include "batched_experts.hpp"
#include <fstream>
#include <iostream>
#include <random>
using iq3::Type;
std::ofstream expected,actual;unsigned checks=0;
void same(const void*a,const void*b,size_t n,const std::string&name){expected.write((const char*)a,n);actual.write((const char*)b,n);if(std::memcmp(a,b,n))throw std::runtime_error("byte mismatch: "+name);++checks;}
uint32_t rng=12345;
uint32_t random32(){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;}
void inputs(std::vector<uint16_t>&x,int edge){for(auto&v:x)v=iq3::bf16_bits(float(int(random32()%2049)-1024)/512.f);if(edge==1){for(unsigned j=0;j<x.size();++j)x[j]=j%2?0x8000:0;}if(edge==2){x[0]=0x7f80;x[8]=0xff80;x[256]=0x0001;}if(edge==3){x[0]=0x7fc1;x[24]=0xffc2;x.back()=0x7f7f;}if(edge==4){for(unsigned j=0;j<x.size();++j)x[j]=j%2?0x3f80:0xbf80;}}
std::vector<uint8_t> weights(Type t,unsigned k,unsigned rows){size_t rb=t==Type::Q6_K||t==Type::Q8_0?iq3::expanded::row_bytes(t,k):k*(t==Type::F32?4:2);std::vector<uint8_t>w(rows*rb);for(unsigned r=0;r<rows;++r){auto p=w.data()+r*rb;if(t==Type::F32){for(unsigned j=0;j<k;++j){float v=float(int(random32()%1025)-512)/2048.f;std::memcpy(p+4*j,&v,4);}}else if(t==Type::BF16){for(unsigned j=0;j<k;++j){uint16_t v=iq3::bf16_bits(float(int(random32()%1025)-512)/2048.f);std::memcpy(p+2*j,&v,2);}}else {for(unsigned j=0;j<k;++j)p[j]=uint8_t(random32());unsigned group=t==Type::Q6_K?16:32;for(unsigned j=0;j<k/group;++j){float v=float(int(random32()%65)-32)/1024.f;std::memcpy(p+k+4*j,&v,4);}}}return w;}
template<Type T,unsigned K>void dense_cases(){
 auto w=weights(T,K,7);size_t rb=w.size()/7;std::vector<uint16_t>a(K),b(K);std::vector<uint16_t>y0(7),y1(7),reference0(7),reference1(7);
 for(unsigned split:{1u,4u}){if(split==4&&K%256)continue;
  for(int edge=0;edge<5;++edge){inputs(a,edge);inputs(b,edge==0?4:0);
   p68b::DenseKernel op;op.count=1;op.shapes[0]={7,K,split,unsigned(rb),T};std::array<void*,5>ptr{w.data(),a.data(),b.data(),y0.data(),y1.data()};op.run(ptr);
   for(unsigned row=0;row<7;++row){reference0[row]=iq3::bf16_bits(p28::dense_row<T,K>(w.data()+row*rb,a.data(),split));reference1[row]=iq3::bf16_bits(p28::dense_row<T,K>(w.data()+row*rb,b.data(),split));}
   same(reference0.data(),y0.data(),14,"dense row0 "+std::to_string(K)+" edge "+std::to_string(edge));same(reference1.data(),y1.data(),14,"dense row1");
   if constexpr(T!=Type::BF16){for(unsigned row=0;row<7;++row){auto x=w.data()+row*rb;float parts[4]{};for(unsigned p=0;p<split;++p){auto bounds=iq3::kopt2::bounds(K,p,split);float lanes[32];for(unsigned l=0;l<32;++l)lanes[l]=p49c::dense_lane<T,K>(x,a.data(),bounds.first,bounds.second,l);parts[p]=iq3::tree32(lanes);}auto y=iq3::bf16_bits(split==1?parts[0]:(parts[0]+parts[1])+(parts[2]+parts[3]));same(&y,&y0[row],2,"production vector dense");}}
  }
 }
}
struct HCData {
 std::vector<uint16_t>x,norm,low,act,gate,mix,inject;std::vector<float>scratch,workspace;uint32_t error=0,active=1,position=33;
 HCData():x(p60::K),norm(p60::K,0x1234),low(p60::L,0x1234),act(p60::L,0x1234),gate(p60::K,0x1234),mix(p60::H,0x1234),inject(4,0x1234),scratch(320,-7.f),workspace(32,-7.f){inputs(x,0);}
 std::array<void*,16> bind(std::vector<float>&gain,std::vector<uint8_t>&lw,std::vector<uint8_t>&gw,std::vector<uint8_t>&iw){return {x.data(),gain.data(),lw.data(),gw.data(),iw.data(),norm.data(),low.data(),act.data(),gate.data(),mix.data(),inject.data(),scratch.data(),workspace.data(),&error,&active,&position};}
 void compare(const HCData&b){for(auto pair:{std::pair{&norm,&b.norm},{&low,&b.low},{&act,&b.act},{&gate,&b.gate},{&mix,&b.mix},{&inject,&b.inject}})same(pair.first->data(),pair.second->data(),pair.first->size()*2,"HC BF16");same(scratch.data(),b.scratch.data(),scratch.size()*4,"HC scratch");same(workspace.data(),b.workspace.data(),workspace.size()*4,"HC workspace");same(&error,&b.error,4,"HC error");}
};
void hc_cases(){auto lw=weights(Type::Q8_0,p60::K,p60::L),gw=weights(Type::Q8_0,p60::L,p60::K),iw=weights(Type::F32,p60::K,4);std::vector<float>gain(p60::K);for(auto&v:gain)v=float(random32()%256)/128.f;
 for(unsigned mode=0;mode<4;++mode){HCData a,b;if(mode==1)a.active=0;if(mode==2)a.error=1;if(mode==3)a.position=4096;auto ca=a,cb=b;auto ap=a.bind(gain,lw,gw,iw),bp=b.bind(gain,lw,gw,iw),cap=ca.bind(gain,lw,gw,iw),cbp=cb.bind(gain,lw,gw,iw);std::array<void*,32>p;std::copy(cap.begin(),cap.end(),p.begin());std::copy(cbp.begin(),cbp.end(),p.begin()+16);
  auto ba=p68b::hc_bind(ap,0,4096),bb=p68b::hc_bind(bp,0,4096);p60::host_norm(ba);p60::host_norm(bb);p68b::HCKernel<0>n;n.run(p);a.compare(ca);b.compare(cb);
  p60::host_low_inject(ba);p60::host_low_inject(bb);p68b::HCKernel<1>l;l.run(p);a.compare(ca);b.compare(cb);
  p60::host_gate_mix(ba);p60::host_gate_mix(bb);p68b::HCKernel<2>g;g.run(p);a.compare(ca);b.compare(cb);
 }
}
template<Type T>void expert_cases(){
 constexpr bool gate=T==Type::IQ2_S;constexpr unsigned k=gate?2560:640,rows=19,count=4,experts=3;
 auto source_bytes=p49bgemv::source_row_bytes(T,k),rb=p49bgemv::layout(T,k).row_bytes;auto fmt=iq3::layout(T);
 std::vector<uint8_t>w(experts*rows*rb),peer(w.size()),source(source_bytes);
 for(auto*dest:{&w,&peer})for(unsigned row=0;row<experts*rows;++row){for(auto&v:source)v=uint8_t(random32());for(unsigned block=0;block<k/fmt.elements;++block){uint16_t scale=uint16_t(0x2400+random32()%1024);std::memcpy(source.data()+block*fmt.bytes,&scale,2);}p49bgemv::repack_row(T,k,source.data(),dest->data()+row*rb);}
 for(unsigned mode=0;mode<6;++mode){
  std::vector<uint16_t>x0(k*(gate?1:count)),x1(x0.size());inputs(x0,mode==4?3:0);inputs(x1,mode==4?2:4);
  std::array<iq3::Route,count>r0{{{0,0,rows},{1,0,rows},{2,1,rows-2},{2,1,rows-2}}},r1=r0;
  if(mode==1)r1={{{2,0,rows},{0,0,rows},{1,2,rows-3},{1,0,rows}}};
  if(mode==2)r1={{{2,0,rows},{2,0,rows},{2,0,rows},{2,0,rows}}};
  if(mode==3){r0[1]={experts,0,rows};r1[2]={1,rows,1};r1[3]={1,0,0};}
  std::array<std::vector<uint16_t>,4>expected_y,actual_y;for(auto&v:expected_y)v.assign(rows*count,0x1234);actual_y=expected_y;
  std::array<std::array<uint32_t,count>,4>expected_s{},actual_s{};
  uint32_t expected_error[2]={mode==5?1u:0u,0},actual_error[2]={expected_error[0],0},active[2]={mode==5?0u:1u,1},pos=0;
  for(unsigned row=0;row<2;++row){auto x=row?x1.data():x0.data();auto routes=row?r1.data():r0.data();std::array<void*,19>p{w.data(),peer.data(),x,expected_y[row].data(),expected_y[row+2].data(),routes,expected_s[row].data(),expected_s[row+2].data(),x,x,x,x,x,x,x,x,&expected_error[row],&active[row],&pos};
   p49dvirtual::Kernel<T,k,gate?2:3>op;op.rows=rows;op.count=count;op.experts=experts;op.run(p);
  }
  std::array<void*,18>p{w.data(),peer.data(),x0.data(),x1.data(),actual_y[0].data(),actual_y[1].data(),actual_y[2].data(),actual_y[3].data(),r0.data(),r1.data(),actual_s[0].data(),actual_s[1].data(),actual_s[2].data(),actual_s[3].data(),&actual_error[0],&actual_error[1],&active[0],&active[1]};p68b::ExpertKernel<T>op;op.rows=rows;op.count=count;op.experts=experts;op.run(p);
  for(unsigned j=0;j<(gate?4u:2u);++j){same(expected_y[j].data(),actual_y[j].data(),rows*count*2,"expert union row output");same(expected_s[j].data(),actual_s[j].data(),count*4,"expert union status");}same(expected_error,actual_error,8,"expert union errors");
  unsigned visits[2][count]{};for(unsigned u=0;u<2*count;++u){auto slots=p68b::union_slot(r0.data(),r1.data(),u,count);if(slots.a>=0)++visits[0][slots.a];if(slots.b>=0)++visits[1][slots.b];}unsigned ones[2][count];for(auto&v:ones)for(auto&z:v)z=1;same(ones,visits,sizeof ones,"union exactly one writer per slot");
 }
}
void tail_cases(){
 for(auto kind:{p39::Kind::silu_div4,p39::Kind::attention_combine,p39::Kind::shared_act})for(unsigned mode=0;mode<4;++mode){
  std::array<std::vector<uint16_t>,2>y,other,expect,out;uint32_t error[2]={mode==2?1u:0u,0},candidate_error[2]={error[0],0},active[2]={mode==1?0u:1u,1},pos[2]={mode==3?4096u:32u,31};std::array<void*,14>args;
  for(unsigned r=0;r<2;++r){y[r].resize(320);other[r].resize(320);expect[r].resize(1280);inputs(y[r],r?4:0);inputs(other[r],0);inputs(expect[r],0);out[r]=expect[r];p39::Bound b{};b.rows=320;b.capacity=4096;b.y=y[r].data();b.out=expect[r].data();b.streams=b.out;b.other=other[r].data();b.inject=b.other;b.error=&error[r];b.active=&active[r];b.position=&pos[r];
   if(kind==p39::Kind::silu_div4)p39::host_tail<p39::Kind::silu_div4>(b);else if(kind==p39::Kind::attention_combine)p39::host_tail<p39::Kind::attention_combine>(b);else p39::host_tail<p39::Kind::shared_act>(b);
   std::array<void*,7>a{y[r].data(),out[r].data(),other[r].data(),&candidate_error[r],&active[r],&pos[r],y[r].data()};std::copy(a.begin(),a.end(),args.begin()+7*r);
  }p68b::Tail op;op.kind=kind;op.rows=320;op.capacity=4096;op.run(args);for(unsigned r=0;r<2;++r)same(expect[r].data(),out[r].data(),2560,"paired epilogue");same(error,candidate_error,8,"epilogue error");
 }
}
int main(int argc,char**argv){try{if(argc!=2)throw std::runtime_error("output prefix required");expected.open(std::string(argv[1])+"-expected.bin",std::ios::binary);actual.open(std::string(argv[1])+"-actual.bin",std::ios::binary);
#define CASE(T,K) dense_cases<Type::T,K>()
 CASE(Q6_K,2560);CASE(Q6_K,6144);CASE(Q6_K,10240);CASE(Q8_0,320);CASE(Q8_0,640);CASE(Q8_0,2560);CASE(Q8_0,6144);CASE(Q8_0,10240);CASE(F32,320);CASE(F32,640);CASE(F32,2560);CASE(F32,10240);CASE(BF16,2560);CASE(BF16,6144);CASE(BF16,10240);
#undef CASE
 hc_cases();expert_cases<Type::IQ2_S>();expert_cases<Type::IQ4_NL>();tail_cases();std::cout<<"{\"passed\":true,\"byte_checks\":"<<checks<<",\"model_executed\":false,\"device_executed\":false}\n";return 0;
 }catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
