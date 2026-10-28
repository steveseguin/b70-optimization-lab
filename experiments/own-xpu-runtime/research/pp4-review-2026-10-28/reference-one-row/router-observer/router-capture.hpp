// Observer only; no graph/node/math edits. Every observation returns true.
struct RouterCapture {
 std::string out; int position=243,batch_start=0,batch_tokens=0;
 std::vector<int> output_positions; std::set<std::string> seen; bool failed=false;
};
static bool capture_router(ggml_tensor*t,bool ask,void*opaque){
 auto&c=*static_cast<RouterCapture*>(opaque);int layer=-1;std::string field;
 const char* names[]={"ffn_moe_logits","ffn_moe_probs","ffn_moe_topk","ffn_moe_weights_norm"};
 for(const char*n:names){std::string prefix=std::string(n)+"-";if(std::string(t->name).rfind(prefix,0)==0){
  char tail=0;if(std::sscanf(t->name+prefix.size(),"%d%c",&layer,&tail)!=1)layer=-1;else field=n;break;}}
 bool selected=layer>=0&&layer<48&&c.position>=c.batch_start&&c.position<c.batch_start+c.batch_tokens;
 if(ask)return selected; // pure ASK, including repeated asks
 if(!selected)return true;
 auto bad=[&]{c.failed=true;return true;};
 if(!c.seen.insert(std::to_string(layer)+":"+field).second)return bad();
 int row=c.position-c.batch_start,rows=c.batch_tokens;
 if(layer==47&&t->ne[1]!=rows){
  auto it=std::find(c.output_positions.begin(),c.output_positions.end(),c.position);
  if(it==c.output_positions.end()||t->ne[1]!=int64_t(c.output_positions.size()))return bad();
  row=int(it-c.output_positions.begin());rows=int(c.output_positions.size());
 }
 bool ids=field=="ffn_moe_topk";int width=ids||field=="ffn_moe_weights_norm"?10:512;
 if(t->type!=(ids?GGML_TYPE_I32:GGML_TYPE_F32)||t->ne[0]!=width||t->ne[1]!=rows||t->ne[2]!=1||t->ne[3]!=1||t->nb[0]!=4||t->nb[1]<size_t(width)*4||row<0||row>=rows)return bad();
 if((field=="ffn_moe_logits"&&t->op!=GGML_OP_MUL_MAT)||(field=="ffn_moe_probs"&&t->op!=GGML_OP_SOFT_MAX)||(ids&&t->op!=GGML_OP_VIEW)||(field=="ffn_moe_weights_norm"&&t->op!=GGML_OP_DIV))return bad();
 auto save=[&](ggml_tensor*q,int n,const std::string&label){
  std::vector<char>v(size_t(n)*4);ggml_backend_tensor_get(q,v.data(),size_t(row)*q->nb[1],v.size());
  char name[128];std::snprintf(name,sizeof name,"/layer-%02d-%s.%s",layer,label.c_str(),label=="ids"?"i32":"f32");
  std::ofstream f(c.out+name,std::ios::binary);f.write(v.data(),v.size());
  std::ofstream m(c.out+"/router-layouts.jsonl",std::ios::app);
  m<<"{\"layer\":"<<layer<<",\"field\":\""<<label<<"\",\"op\":"<<int(q->op)<<",\"row\":"<<row<<",\"ne\":["<<q->ne[0]<<","<<q->ne[1]<<","<<q->ne[2]<<","<<q->ne[3]<<"],\"nb\":["<<q->nb[0]<<","<<q->nb[1]<<","<<q->nb[2]<<","<<q->nb[3]<<"]}\n";
  return bool(f)&&bool(m);
 };
 if(field=="ffn_moe_logits"){
  auto*x=t->src[1];auto*w=t->src[0];
  if(!x||!w||x->type!=GGML_TYPE_F32||x->ne[0]!=2560||x->ne[1]!=rows||x->ne[2]!=1||x->ne[3]!=1||x->nb[0]!=4||x->nb[1]<10240||w->ne[0]!=2560||w->ne[1]!=512)return bad();
  if(!save(x,2560,"input"))return bad();
 }
 if(!save(t,width,ids?"ids":field=="ffn_moe_logits"?"logits":field=="ffn_moe_probs"?"probabilities":"weights"))return bad();
 return true;
}
