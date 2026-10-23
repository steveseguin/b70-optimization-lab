// Additive synthetic GDN branch completion; immutable p202 fixture reused.
#define main p202_fixture_entry_not_called
#include "../packet202-prefill-chunk-prep/layer0_host_probe.cpp"
#undef main
#include "selected_reference.hpp"
constexpr unsigned OUT=2560,IK=6144;
constexpr float sentinel=-123456.75f;
static std::vector<uint8_t> output_weights(){std::vector<uint8_t> raw(OUT*5040);
 for(unsigned r=0;r<OUT;++r)for(unsigned block=0;block<24;++block){auto b=raw.data()+r*5040+block*210;
  for(unsigned j=0;j<192;++j)b[j]=uint8_t(r*29+block*17+j*31+(j>>2));
  for(unsigned j=0;j<16;++j)b[192+j]=uint8_t(int((r+block+j)%7)-3);
  b[208]=0;b[209]=0x20; // finite 2^-7 FP16 scale
 }auto expanded=iq3::expanded::expand(iq3::Type::Q6_K,raw.data(),raw.size(),IK);
 need(iq3::expanded::row_bytes(iq3::Type::Q6_K,IK)==8112&&expanded.size()==20766720,"output resident layout");return expanded;}
static void norm(const U16&gdn,const U16&z,const std::vector<float>&gain,U16&out,Controls&c,bool paired){
 ng::Shape s{ng::gated_norm};s.tokens=paired?2:1;s.capacity=4096;s.flags=8;s.heads=48;s.width=128;
 for(unsigned row=0;row<(paired?1u:2u);++row){Controls local=c;local.position+=int(row);auto a=controls(local);a.p[0]=const_cast<uint16_t*>(gdn.data()+row*Z);a.p[1]=const_cast<uint16_t*>(z.data()+row*Z);a.p[2]=const_cast<float*>(gain.data());a.p[3]=out.data()+row*Z;
  if(paired)ng::cpu(s,a);
  else{std::vector<float> scratch(ng::local_floats(s));for(int g=0;g<48;++g)p203_selected::norm_group(s,a,g,ng::HostTeam{scratch.data()});}
  if(local.error)c.error=local.error;
 }
}
struct Tail {U16 normed,projected,streams;std::vector<float> partials;};
static Tail initial_tail(){Tail t;t.normed.resize(2*Z,0x1234);t.projected.resize(2*OUT,0x2345);t.partials.resize(2*OUT*8,sentinel);t.streams.resize(2*4*OUT);
 for(unsigned i=0;i<t.streams.size();++i)t.streams[i]=bf(float(int((i*17)%43)-21)/16.f);return t;}
static U16 injection(){U16 x(8);for(unsigned i=0;i<8;++i)x[i]=bf(float(int(i)-4)/2.f);return x;}
static std::vector<float> gain(){std::vector<float>x(128);for(unsigned i=0;i<128;++i)x[i]=.75f+float(i%11)/32.f;return x;}
static bool enter(Controls&c){if(!c.active||c.error)return false;if(c.position<0||c.position>4094){c.error=1;return false;}return true;}
static void validate_tail(const U16&input,const U16&z,const std::vector<float>&gain,const std::vector<uint8_t>&w,const U16&inject,const Tail&t){
 need(input.size()==2*Z&&z.size()==2*Z&&gain.size()==128&&w.size()==20766720&&inject.size()==8&&t.normed.size()==2*Z&&t.projected.size()==2*OUT&&t.streams.size()==2*4*OUT&&t.partials.size()==2*OUT*8,"tail exact extents");
 std::vector<p202::Region> regions;
 auto add=[&]<class T>(const std::vector<T>&v,bool write){regions.push_back({uintptr_t(v.data()),v.size()*sizeof(T),v.size()*sizeof(T),write});};
 add(input,false);add(z,false);add(gain,false);add(w,false);add(inject,false);add(t.normed,true);add(t.projected,true);add(t.streams,true);add(t.partials,true);p202::validate_bindings(regions);
}
static void project_serial(const std::vector<uint8_t>&w,const U16&inject,Tail&t,Controls&c){
 for(unsigned token=0;token<2;++token){auto x=t.normed.data()+token*IK;
  // Independent per-split authority, exposing the live partials that HOST
  // DenseKernel computes privately. Unused partial slots remain sentinels.
  for(unsigned row=0;row<OUT;++row)for(unsigned part=0;part<4;++part){auto bound=iq3::kopt2::bounds(IK,part,4);float lanes[32];
   for(unsigned lane=0;lane<32;++lane)lanes[lane]=p49c::dense_lane<iq3::Type::Q6_K,IK>(w.data()+row*8112,x,bound.first,bound.second,lane);
   t.partials[(token*OUT+row)*8+part]=iq3::tree32(lanes);}
  p49c::DenseKernel<iq3::Type::Q6_K,IK,4,p39::Kind::attention_combine> op;op.shape.rows=OUT;op.shape.rb=8112;op.shape.capacity=4096;
  std::array<void*,19> bindings{};bindings[0]=const_cast<uint8_t*>(w.data());bindings[2]=x;bindings[3]=t.projected.data()+token*OUT;
  bindings[8]=t.partials.data()+token*OUT*8;bindings[11]=t.streams.data()+token*4*OUT;bindings[12]=const_cast<uint16_t*>(inject.data()+token*4);bindings[16]=&c.error;bindings[17]=&c.active;bindings[18]=&c.position;op.run(bindings);
 }
}
static void project_pair(const std::vector<uint8_t>&w,const U16&inject,Tail&t,Controls&c,bool skip_rounding=false){
 for(unsigned row=0;row<OUT;++row)for(unsigned part=0;part<4;++part){auto bound=iq3::kopt2::bounds(IK,part,4);float lanes[2][32]{};auto weights=w.data()+row*8112;
  for(unsigned lane=0;lane<32;++lane)for(unsigned k=bound.first+lane*8;k<bound.second;k+=256){
   float scale=iq3::bits_float(p49c::load32(weights+IK+4*(k/16)));uint32_t lo=p49c::load32(weights+k),hi=p49c::load32(weights+k+4);
   for(unsigned j=0;j<8;++j){float value=scale*float(iq3::signed8(uint8_t(((j<4?lo:hi)>>(8*(j%4)))&255)));
    for(unsigned token=0;token<2;++token){float product=value*iq3::bits_float(uint32_t(t.normed[token*IK+k+j])<<16);lanes[token][lane]=lanes[token][lane]+product;}}
  }
  for(unsigned token=0;token<2;++token)t.partials[(token*OUT+row)*8+part]=iq3::tree32(lanes[token]);
 }
 for(unsigned token=0;token<2;++token){float factor[4];for(unsigned stream=0;stream<4;++stream)factor[stream]=2.f*ng::sigmoid(p39::widen(inject[token*4+stream])/4.f);
  for(unsigned row=0;row<OUT;++row){auto v=t.partials.data()+(token*OUT+row)*8;float value=(v[0]+v[1])+(v[2]+v[3]);auto y=iq3::bf16_bits(value);t.projected[token*OUT+row]=y;
   if(c.active&&!c.error)for(unsigned stream=0;stream<4;++stream){auto i=(token*4+stream)*OUT+row;
    t.streams[i]=iq3::bf16_bits(p39::widen(t.streams[i])+(skip_rounding?value:p39::widen(y))*factor[stream]);}
  }
 }
}
static void finish_branch(const Results&core,const std::vector<uint8_t>&w,const U16&inject,Tail&t,Controls&c,bool paired){
 if(!enter(c))return;auto gains=gain();validate_tail(core.output,core.z,gains,w,inject,t);
 norm(core.output,core.z,gains,t.normed,c,paired);if(c.error)return;
 if(paired)project_pair(w,inject,t,c);else project_serial(w,inject,t,c);
}
static void compare_float(const char*stage,const std::vector<float>&a,const std::vector<float>&b,bool&first){if(!first)std::cout<<',';first=false;bool same=a.size()==b.size()&&!std::memcmp(a.data(),b.data(),a.size()*4);
 std::cout<<"{\"stage\":\""<<stage<<"\",\"serial_sha256\":\""<<hash(a)<<"\",\"chunk_sha256\":\""<<hash(b)<<"\",\"bytes\":"<<a.size()*4<<",\"equal\":"<<(same?"true":"false")<<'}';need(same,"split partial bytes differ");}
static bool unused(const Tail&t){for(unsigned i=0;i<2*OUT;++i)for(unsigned j=4;j<8;++j)if(t.partials[i*8+j]!=sentinel)return false;return true;}
static void branch_case(const std::string&name,const Weights&weights,const std::vector<uint8_t>&w){auto f=fixture(name);auto serial_core=serial(f,weights),chunk_core=chunk(f,weights);auto inject=injection();auto a=initial_tail(),b=initial_tail();Controls ca,cb;
 finish_branch(serial_core,w,inject,a,ca,false);finish_branch(chunk_core,w,inject,b,cb,true);need(!ca.error&&!cb.error,"tail sticky error");
 auto bad_core=chunk_core;std::fill(bad_core.z.begin(),bad_core.z.end(),0);auto badz=initial_tail();Controls bz;finish_branch(bad_core,w,inject,badz,bz,true);
 bool z_changed=badz.normed!=b.normed&&badz.streams!=b.streams,streams_changed=initial_tail().streams!=b.streams;need(z_changed&&streams_changed,"negative z/injection fixture vacuous");
 auto badround=initial_tail();badround.normed=b.normed;project_pair(w,inject,badround,cb,true);bool round_changed=badround.streams!=b.streams;need(round_changed,"pre-BF16 injection fixture did not discriminate");
 need(unused(a)&&unused(b),"unused partial slots changed");
 std::cout<<"{\"name\":\""<<name<<"\",\"passed\":true,\"partial_sentinel_slots_unchanged\":true,\"comparisons\":[";bool first=true;
 compare("upstream_qkv",serial_core.qkv,chunk_core.qkv,first);compare("upstream_z",serial_core.z,chunk_core.z,first);compare("upstream_conv",serial_core.conv,chunk_core.conv,first);compare("upstream_gdn",serial_core.output,chunk_core.output,first);compare("upstream_state",serial_core.state,chunk_core.state,first);
 compare("gated_norm",a.normed,b.normed,first);compare_float("split_partials",a.partials,b.partials,first);compare("output_projection",a.projected,b.projected,first);compare("stream_injection",a.streams,b.streams,first);
 std::cout<<"],\"negative_controls\":{\"z_ignored_differs\":true,\"stream_injection_ignored_differs\":true,\"pre_bf16_injection_differs\":true,\"wrong_z_streams_sha256\":\""<<hash(badz.streams)<<"\",\"pre_round_streams_sha256\":\""<<hash(badround.streams)<<"\"}}";
}
static void guard_checks(){Results core;core.output.resize(2*Z,bf(.5f));core.z.resize(2*Z,bf(.25f));std::vector<uint8_t>w(20766720);auto inject=injection();std::map<std::string,bool> checks;
 for(auto mode:{"inactive_unchanged","sticky_error_unchanged","invalid_position_unchanged"})for(bool paired:{false,true}){auto t=initial_tail(),before=t;Controls c;if(std::string(mode)=="inactive_unchanged")c.active=0;else if(std::string(mode)=="sticky_error_unchanged")c.error=1;else c.position=4095;auto original=c;finish_branch(core,w,inject,t,c,paired);
 bool ok=t.normed==before.normed&&t.projected==before.projected&&t.partials==before.partials&&t.streams==before.streams&&c.active==original.active&&c.position==original.position&&c.error==(original.active?1:0);need(ok,"tail entry guards changed outputs/controls");checks[std::string(mode)+(paired?"_pair":"_serial")]=ok;}
 auto t=initial_tail();auto g=gain();bool short_refused=false,alias_refused=false;
 try{auto short_z=core.z;short_z.pop_back();validate_tail(core.output,short_z,g,w,inject,t);}catch(const std::runtime_error&){short_refused=true;}
 try{validate_tail(t.normed,core.z,g,w,inject,t);}catch(const std::invalid_argument&){alias_refused=true;}
 checks["short_extent_refused"]=short_refused;checks["actual_output_input_alias_refused"]=alias_refused;need(short_refused&&alias_refused,"tail binding refusals missing");
 std::cout<<"{\"passed\":true,\"checks\":{";bool first=true;for(auto[k,v]:checks){if(!first)std::cout<<',';first=false;std::cout<<'"'<<k<<"\":true";}std::cout<<"}}\n";
}
int main(int argc,char**argv){try{
 if(argc==2&&std::string(argv[1])=="--binding-check"){guard_checks();return 0;}
 const std::vector<std::string>all{"distinct_rows","identical_rows","swapped_rows","bf16_rounding","nonzero_initial_state"};std::vector<std::string>names;
 if(argc==2&&std::string(argv[1])=="--all")names=all;else if(argc==3&&std::string(argv[1])=="--case"&&std::find(all.begin(),all.end(),argv[2])!=all.end())names={argv[2]};else throw std::invalid_argument("use --all, --case NAME or --binding-check");
 auto weights=make_weights();auto output=output_weights();std::cout<<"{\"passed\":true,\"device_executed\":false,\"scope\":\"synthetic GDN branch from attention input to streams; no HC/FFN/QSA/device\",\"variant\":7,\"split\":4,\"expanded_row_bytes\":8112,\"output_weight_sha256\":\""<<hash(output)<<"\",\"cases\":[";bool first=true;
 for(auto name:names){if(!first)std::cout<<',';first=false;branch_case(name,weights,output);}std::cout<<"]}\n";return 0;
 }catch(const std::exception&e){std::cerr<<"REFUSED: "<<e.what()<<'\n';return 1;}}
