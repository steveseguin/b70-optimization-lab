// CPU only; include the patched translation unit to test its internal guards.
#include "patched/packet16-decode/adapter.cpp"
#include <iostream>
#include <limits>
#include <cstring>

static int cases=0;
static void check(bool good,const char* message){if(!good)throw std::runtime_error(message);}
struct Tiny {
 integrated::Spec spec;
 std::array<std::vector<float>,20> data;
 std::vector<float> scratch=std::vector<float>(8192);
 uint32_t error=0,position=0,active=1;
 Tiny(integrated::Op op,std::initializer_list<size_t> input,std::initializer_list<size_t> output){
  spec.g=integrated::Geometry::tiny();spec.op=op;spec.ni=input.size();spec.no=output.size();
  size_t j=0;for(auto n:input){spec.sizes[j]=n;spec.types[j]=integrated::Scalar::f32;data[j++].assign(n,.125f);}
  for(auto n:output){spec.sizes[j]=n;spec.types[j]=integrated::Scalar::f32;data[j++].assign(n,123.f);}
 }
 packet16::Bound bound(){packet16::Bound b{spec,{}};
  for(int j=0;j<spec.ni+spec.no;++j)b.p[j]=data[j].data();
  b.p[b.tail()]=scratch.data();b.p[b.tail()+1]=&error;b.p[b.tail()+2]=&position;b.p[b.tail()+3]=&active;return b;
 }
 void tiny(int group=0){packet16::tiny(bound(),group,ng::HostTeam{scratch.data()});}
 void simple(){packet16::simple(bound(),0,ng::HostTeam{scratch.data()});}
};
struct Native {
 ng::Shape shape{};ng::Args args{};std::array<std::vector<uint32_t>,16> memory;
 std::vector<float> scratch;
 explicit Native(int op){shape.op=op;shape.capacity=8;shape.budget=8;
  auto sizes=ng::required_bytes(shape);for(int j=0;j<16;++j){memory[j].assign((sizes[j]+3)/4,0);args.p[j]=memory[j].data();}
  args.i(15)[1]=1;scratch.resize(ng::local_floats(shape));
  std::fill_n(args.i(4),11,-1);
 }
 void run(){ng::group(shape,args,0,ng::HostTeam{scratch.data()});}
};
int main(){
 for(float bad:{std::numeric_limits<float>::quiet_NaN(),std::numeric_limits<float>::infinity(),1e30f,-2.f,.5f,8.f,1.f}){
  Tiny t(integrated::Op::qsa_attention,{16,16,32,32,11},{16});
  std::fill(t.data[4].begin(),t.data[4].end(),-1.f);t.data[4][0]=bad;t.tiny();
  check(t.error==1,"tiny attention must reject invalid/future id before cast/address");++cases;
 }
 {Tiny t(integrated::Op::qsa_attention,{16,16,32,32,11},{16});
  std::fill(t.data[4].begin(),t.data[4].end(),-1.f);t.data[4][0]=0;t.tiny();
  check(!t.error,"valid tiny attention id rejected");++cases;}
 {Tiny t(integrated::Op::qsa_select,{16,8},{11});t.position=UINT32_MAX;t.tiny();
  check(t.error==1&&t.data[2][0]==0&&t.data[2][1]==-1,"tiny select position must clamp safely");++cases;}
 {Tiny t(integrated::Op::qsa_select,{16,8},{11});t.position=3;
  std::fill(t.data[0].begin(),t.data[0].end(),std::numeric_limits<float>::infinity());t.tiny();
  check(t.error==1&&t.data[2][0]==-1,"tiny select nonfinite rank rejected");++cases;}
 for(float bad:{std::numeric_limits<float>::quiet_NaN(),std::numeric_limits<float>::infinity(),1e30f,-1.f,.5f,16.f}){
  Tiny t(integrated::Op::expert_gather,{10,16},{30,30,160});
  for(int j=0;j<10;++j)t.data[0][j]=j;t.data[0][0]=bad;t.simple();
  check(t.error==1&&t.data[2][0]==0&&t.data[3][0]==0,"bad route must become safe expert zero");
  check(t.data[4][0]==t.data[1][0],"bad route must still initialize downstream input");++cases;
 }
 for(int32_t bad:{INT32_MAX,INT32_MIN,-2,8,1}){
  Native t(ng::attention_value);t.args.i(4)[0]=bad;t.args.f(7)[0]=1;t.run();
  check(t.args.i(15)[2]==1,"standalone attention value must clamp invalid id");++cases;
 }
 {Native t(ng::attention_value);t.args.i(4)[0]=0;t.args.f(7)[0]=1;t.run();
  check(!t.args.i(15)[2],"valid native attention id rejected");++cases;}
 for(int op:{ng::attention_value,ng::attention_softmax}){
  Native t(op);std::fill_n(t.args.i(4),11,0);t.run();
  check(t.args.i(15)[2]==1,"oversized unsentinel list must not read unwritten score/probability slots");++cases;
 }
 for(int op:{ng::attention_value,ng::attention_softmax}){
  Native t(op);t.run();check(!t.args.i(15)[2],"empty -1 sentinel list is safe");++cases;
 }
 {Native t(ng::attention_score);t.args.i(4)[0]=-2;t.run();check(t.args.i(15)[2]==1,"negative non-sentinel id rejected");++cases;}
 std::cout<<"{\"cpu_only\":true,\"malformed_and_valid_index_cases\":"<<cases<<",\"passed\":true}\n";
}
