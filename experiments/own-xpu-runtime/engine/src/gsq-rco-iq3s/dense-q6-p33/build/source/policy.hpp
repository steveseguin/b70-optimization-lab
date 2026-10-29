#pragma once
struct DenseQ6Site {const char*label;const char*weight;unsigned rows;};
static constexpr std::array<DenseQ6Site,19> dense_q6_sites{{
{"blk.1.gdn.z","blk.1.attn_gate.weight",6144},
{"blk.4.gdn.z","blk.4.attn_gate.weight",6144},
{"blk.10.gdn.z","blk.10.attn_gate.weight",6144},
{"blk.17.gdn.z","blk.17.attn_gate.weight",6144},
{"blk.20.gdn.z","blk.20.attn_gate.weight",6144},
{"blk.21.gdn.z","blk.21.attn_gate.weight",6144},
{"blk.24.gdn.z","blk.24.attn_gate.weight",6144},
{"blk.25.gdn.z","blk.25.attn_gate.weight",6144},
{"blk.26.gdn.z","blk.26.attn_gate.weight",6144},
{"blk.28.gdn.z","blk.28.attn_gate.weight",6144},
{"blk.29.gdn.z","blk.29.attn_gate.weight",6144},
{"blk.31.qsa.qgate","blk.31.attn_q.weight",12288},
{"blk.33.gdn.z","blk.33.attn_gate.weight",6144},
{"blk.35.qsa.qgate","blk.35.attn_q.weight",12288},
{"blk.39.qsa.qgate","blk.39.attn_q.weight",12288},
{"blk.40.gdn.z","blk.40.attn_gate.weight",6144},
{"blk.43.qsa.qgate","blk.43.attn_q.weight",12288},
{"blk.45.gdn.z","blk.45.attn_gate.weight",6144},
{"blk.47.qsa.qgate","blk.47.attn_q.weight",12288}
}};
static bool dense_q6_weight(const Weights&w,const Options&a,const std::string&name){
 if(!a.dense_q6_p33)return false;
 for(auto s:dense_q6_sites)if(name==s.weight){
  require(a.gsq_packed&&a.attention_q8_p33&&a.qkv_q6_p33&&a.expert_iq3xxs_block&&!a.mini,"dense Q6 combined mode");
  const auto&t=w.directory.at(name);
  require(flash::grid_type(t.grid)==iq3::Type::Q6_K&&t.shape==std::vector<int>({int(s.rows),2560})&&t.bytes==size_t(s.rows)*2100,"dense Q6 exact tensor");return true;
 }return false;
}
static bool dense_q6_site(const Weights&w,const Options&a,const flash::Launch&l){
 if(!a.dense_q6_p33)return false;
 for(auto s:dense_q6_sites)if(l.label==s.label||std::find(l.weights.begin(),l.weights.end(),s.weight)!=l.weights.end()){
  require(l.label==s.label&&l.op=="gemv"&&l.weights==std::vector<std::string>{s.weight}&&l.shape==std::vector<int>({1,int(s.rows),2560}),"dense Q6 exact site");return dense_q6_weight(w,a,s.weight);
 }return false;
}
template<class Matrix>static void dense_q6_matrix(const Matrix&m,const flash::Launch&l,unsigned variant,size_t bytes){
 // l.row_count: a TP card's whole rows of the site (row split or head split), same per-row arithmetic.
 require(m.type==iq3::Type::Q6_K&&l.shape.size()==3&&(l.shape[1]==6144||l.shape[1]==12288)&&m.rows==(l.row_count?unsigned(l.row_count):unsigned(l.shape[1]))&&m.columns==2560&&variant==6&&((m.activation==iq3::Type::BF16&&m.output_type==iq3::Type::BF16)||(m.activation==iq3::Type::F32&&m.output_type==iq3::Type::F32))&&!m.fp32&&!m.routes&&!m.status&&m.count==1&&m.experts==1&&(m.span==0||m.span==m.rows)&&bytes==size_t(m.rows)*(m.raw?2100:3380),"dense Q6 variant6 exact matrix");
}
static void dense_q6_admit(const Weights&w,const Options&a,const flash::Plan&p){
 if(!a.dense_q6_p33)return;
 std::set<std::string>seen;for(const auto&l:p.launches)if(dense_q6_site(w,a,l))require(seen.insert(l.label).second,"duplicate dense Q6 site");
 require(seen.size()==19,"complete dense Q6 plan");
}
