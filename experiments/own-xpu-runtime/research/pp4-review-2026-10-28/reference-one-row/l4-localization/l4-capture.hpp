// Pure observer; selected raw tensors only. All observations continue graph execution.
#include <map>
struct L4Capture {std::string out;int position=243,batch_start=0,batch_tokens=0;std::vector<int>output_positions;std::map<std::string,int>seen;bool failed=false;};
static bool capture_l4(ggml_tensor*t,bool ask,void*opaque){
 auto&c=*static_cast<L4Capture*>(opaque);
 const std::set<std::string> names={"hc_norm-4","hc_mixed-4","linear_attn_qkv_mixed-4","z-4","alpha-4","beta-4","beta_sigmoid-4","gate-4","conv_state_at-4","state_predelta-4","conv_output_raw-4","conv_output_silu-4","q_conv_predelta-4","k_conv_predelta-4","v_conv_predelta-4","norm-4","final_output-4","linear_attn_out-4"};
 bool selected=names.count(t->name)&&c.position>=c.batch_start&&c.position<c.batch_start+c.batch_tokens;
 if(ask)return selected;
 if(!selected)return true;
 auto bad=[&]{c.failed=true;return true;};
 if(c.batch_start!=0||c.batch_tokens!=244||c.position!=243)return bad();
 std::string name=t->name;int occurrence=++c.seen[name];bool hc=name=="hc_norm-4"||name=="hc_mixed-4";
 if(occurrence>(hc?2:1))return bad();
 auto shape=[](ggml_tensor*q,int64_t a,int64_t b,int64_t e,int64_t d){return q&&q->type==GGML_TYPE_F32&&q->ne[0]==a&&q->ne[1]==b&&q->ne[2]==e&&q->ne[3]==d&&q->nb[0]==4;};
 // Copy explicit canonical logical order, honoring every native stride. No padding bytes.
 auto save=[&](ggml_tensor*q,const std::string&label,int axis,bool full){
  if(!q||q->type!=GGML_TYPE_F32||q->nb[0]!=4)return false;
  for(int i=0;i<4;++i)if(q->ne[i]<1||q->nb[i]<4)return false;
  size_t count=1;for(int i=0;i<4;++i)count*=size_t(i==axis&&!full?1:q->ne[i]);
  if(count>8*1024*1024)return false;
  std::vector<char>v(count*4);size_t dest=0;
  for(int64_t j3=0;j3<q->ne[3];++j3)for(int64_t j2=0;j2<q->ne[2];++j2)for(int64_t j1=0;j1<q->ne[1];++j1){
   int64_t ix[]={0,j1,j2,j3};if(axis>0&&!full&&ix[axis]!=243)continue;
   size_t offset=j1*q->nb[1]+j2*q->nb[2]+j3*q->nb[3];size_t n=size_t(q->ne[0])*4;
   ggml_backend_tensor_get(q,v.data()+dest,offset,n);dest+=n;
  }
  if(dest!=v.size())return false;
  std::ofstream f(c.out+"/"+label+".f32",std::ios::binary);f.write(v.data(),v.size());
  std::ofstream m(c.out+"/layouts.jsonl",std::ios::app);m<<"{\"name\":\""<<label<<"\",\"op\":"<<int(q->op)<<",\"axis\":"<<axis<<",\"full\":"<<(full?"true":"false")<<",\"bytes\":"<<v.size()<<",\"ne\":["<<q->ne[0]<<","<<q->ne[1]<<","<<q->ne[2]<<","<<q->ne[3]<<"],\"nb\":["<<q->nb[0]<<","<<q->nb[1]<<","<<q->nb[2]<<","<<q->nb[3]<<"]}\n";
  return bool(f)&&bool(m);
 };
 int axis=1;bool full=false,valid=false;
 if(name=="hc_norm-4"){
  valid=shape(t,10240,244,1,1)&&t->op==GGML_OP_RESHAPE;
  auto*m=t->src[0];auto*r=m?m->src[0]:nullptr;auto*x=r?r->src[0]:nullptr;
  if(!valid||!m||m->op!=GGML_OP_MUL||!r||r->op!=GGML_OP_RMS_NORM||!shape(x,2560,4,244,1))return bad();
  if(!save(x,"hc-input-"+std::to_string(occurrence),2,false))return bad();
 }else if(name=="hc_mixed-4"||name=="linear_attn_out-4")valid=shape(t,2560,244,1,1);
 else if(name=="linear_attn_qkv_mixed-4")valid=shape(t,10240,244,1,1)&&t->op==GGML_OP_RESHAPE;
 else if(name=="z-4")valid=shape(t,6144,244,1,1);
 else if(name=="alpha-4")valid=shape(t,48,244,1,1)&&t->op==GGML_OP_RESHAPE;
 else if(name=="gate-4"){full=true;valid=shape(t,48,244,1,1)&&t->op==GGML_OP_MUL;}
 else if(name=="beta-4"||name=="beta_sigmoid-4"){
  axis=2;full=name!="beta-4";valid=shape(t,1,48,244,1);
 }else if(name=="conv_state_at-4"){axis=-1;full=true;valid=shape(t,3,10240,1,1)&&t->op==GGML_OP_RESHAPE;}
 else if(name=="state_predelta-4"){axis=-1;full=true;valid=shape(t,128,128,48,1)&&t->op==GGML_OP_RESHAPE;}
 else if(name=="conv_output_raw-4"||name=="conv_output_silu-4")valid=shape(t,10240,244,1,1);
 else if(name=="q_conv_predelta-4"||name=="k_conv_predelta-4"||name=="v_conv_predelta-4"){
  axis=2;full=true;
  // q/k remain16 heads with fused GDN, or repeat48 in unfused graph. v always48.
  valid=shape(t,128,48,244,1)||(name!="v_conv_predelta-4"&&shape(t,128,16,244,1));
 }else if(name=="norm-4"){
  axis=2;valid=shape(t,128,48,244,1)&&t->op==GGML_OP_RMS_NORM;
  if(!valid||!shape(t->src[0],128,48,244,1)||!save(t->src[0],"recurrent-output",2,false))return bad();
 }else if(name=="final_output-4")valid=shape(t,6144,244,1,1)&&t->op==GGML_OP_RESHAPE;
 if(name=="hc_mixed-4")valid=valid&&(t->op==GGML_OP_SCALE||t->op==GGML_OP_DSV4_HC_PRE);
 if(name=="z-4"||name=="linear_attn_out-4")valid=valid&&t->op==GGML_OP_MUL_MAT;
 if(name=="beta-4")valid=valid&&t->op==GGML_OP_RESHAPE;
 if(name=="beta_sigmoid-4")valid=valid&&t->op==GGML_OP_UNARY&&ggml_get_unary_op(t)==GGML_UNARY_OP_SIGMOID;
 if(name=="conv_output_raw-4")valid=valid&&t->op==GGML_OP_SSM_CONV;
 if(name=="conv_output_silu-4")valid=valid&&t->op==GGML_OP_UNARY&&ggml_get_unary_op(t)==GGML_UNARY_OP_SILU;
 if(name=="q_conv_predelta-4"||name=="k_conv_predelta-4")valid=valid&&(t->op==GGML_OP_SCALE||t->op==GGML_OP_REPEAT);
 if(name=="v_conv_predelta-4")valid=valid&&t->op==GGML_OP_VIEW;
 if(!valid||!save(t,name+(hc?"-"+std::to_string(occurrence):""),axis,full))return bad();
 return true;
}
static bool l4_complete(const L4Capture&c){
 if(c.failed||c.seen.size()!=18)return false;
 for(auto&p:c.seen)if(p.second!=((p.first=="hc_norm-4"||p.first=="hc_mixed-4")?2:1))return false;
 return true;
}
