#pragma once
// Names are compiled from hash-admitted graph/census. No data-dependent selection.
static constexpr std::array<std::pair<const char*,const char*>,48> attention_q8_sites{{
{"blk.0.attention","blk.0.ssm_out.weight"},
{"blk.1.attention","blk.1.ssm_out.weight"},
{"blk.2.attention","blk.2.ssm_out.weight"},
{"blk.3.attention","blk.3.attn_output.weight"},
{"blk.4.attention","blk.4.ssm_out.weight"},
{"blk.5.attention","blk.5.ssm_out.weight"},
{"blk.6.attention","blk.6.ssm_out.weight"},
{"blk.7.attention","blk.7.attn_output.weight"},
{"blk.8.attention","blk.8.ssm_out.weight"},
{"blk.9.attention","blk.9.ssm_out.weight"},
{"blk.10.attention","blk.10.ssm_out.weight"},
{"blk.11.attention","blk.11.attn_output.weight"},
{"blk.12.attention","blk.12.ssm_out.weight"},
{"blk.13.attention","blk.13.ssm_out.weight"},
{"blk.14.attention","blk.14.ssm_out.weight"},
{"blk.15.attention","blk.15.attn_output.weight"},
{"blk.16.attention","blk.16.ssm_out.weight"},
{"blk.17.attention","blk.17.ssm_out.weight"},
{"blk.18.attention","blk.18.ssm_out.weight"},
{"blk.19.attention","blk.19.attn_output.weight"},
{"blk.20.attention","blk.20.ssm_out.weight"},
{"blk.21.attention","blk.21.ssm_out.weight"},
{"blk.22.attention","blk.22.ssm_out.weight"},
{"blk.23.attention","blk.23.attn_output.weight"},
{"blk.24.attention","blk.24.ssm_out.weight"},
{"blk.25.attention","blk.25.ssm_out.weight"},
{"blk.26.attention","blk.26.ssm_out.weight"},
{"blk.27.attention","blk.27.attn_output.weight"},
{"blk.28.attention","blk.28.ssm_out.weight"},
{"blk.29.attention","blk.29.ssm_out.weight"},
{"blk.30.attention","blk.30.ssm_out.weight"},
{"blk.31.attention","blk.31.attn_output.weight"},
{"blk.32.attention","blk.32.ssm_out.weight"},
{"blk.33.attention","blk.33.ssm_out.weight"},
{"blk.34.attention","blk.34.ssm_out.weight"},
{"blk.35.attention","blk.35.attn_output.weight"},
{"blk.36.attention","blk.36.ssm_out.weight"},
{"blk.37.attention","blk.37.ssm_out.weight"},
{"blk.38.attention","blk.38.ssm_out.weight"},
{"blk.39.attention","blk.39.attn_output.weight"},
{"blk.40.attention","blk.40.ssm_out.weight"},
{"blk.41.attention","blk.41.ssm_out.weight"},
{"blk.42.attention","blk.42.ssm_out.weight"},
{"blk.43.attention","blk.43.attn_output.weight"},
{"blk.44.attention","blk.44.ssm_out.weight"},
{"blk.45.attention","blk.45.ssm_out.weight"},
{"blk.46.attention","blk.46.ssm_out.weight"},
{"blk.47.attention","blk.47.attn_output.weight"}
}};
static bool attention_q8_weight(const Weights&w,const Options&a,const std::string&name){
 if(!a.attention_q8_p33)return false;
 for(auto [label,weight]:attention_q8_sites)if(name==weight){
  const auto&t=w.directory.at(name);
  require(a.gsq_packed&&!a.mini&&flash::grid_type(t.grid)==iq3::Type::Q8_0&&t.shape==std::vector<int>({2560,6144})&&t.bytes==16711680,"attention Q8 exact tensor");return true;
 }return false;
}
static bool attention_q8_site(const Weights&w,const Options&a,const flash::Launch&l){
 if(!a.attention_q8_p33)return false;
 for(auto [label,weight]:attention_q8_sites)if(l.label==label||std::find(l.weights.begin(),l.weights.end(),weight)!=l.weights.end()){
  require(l.label==label&&l.op=="gemv"&&l.weights==std::vector<std::string>{weight}&&l.shape==std::vector<int>({1,2560,6144}),"attention Q8 exact site");
  return attention_q8_weight(w,a,weight);
 }return false;
}
static void attention_q8_admit(const Weights&w,const Options&a,const flash::Plan&p){
 if(!a.attention_q8_p33)return;
 std::set<std::string> seen;for(const auto&l:p.launches)if(attention_q8_site(w,a,l))require(seen.insert(l.label).second,"duplicate attention site");
 require(seen.size()==48,"complete attention Q8 plan");
}

// Additive fixed Q6 subset. All other QKV formats retain their existing path.
static constexpr std::array<std::pair<const char*,const char*>,22> qkv_q6_sites{{
{"blk.0.gdn.qkv","blk.0.attn_qkv.weight"},
{"blk.2.gdn.qkv","blk.2.attn_qkv.weight"},
{"blk.4.gdn.qkv","blk.4.attn_qkv.weight"},
{"blk.5.gdn.qkv","blk.5.attn_qkv.weight"},
{"blk.6.gdn.qkv","blk.6.attn_qkv.weight"},
{"blk.8.gdn.qkv","blk.8.attn_qkv.weight"},
{"blk.9.gdn.qkv","blk.9.attn_qkv.weight"},
{"blk.14.gdn.qkv","blk.14.attn_qkv.weight"},
{"blk.16.gdn.qkv","blk.16.attn_qkv.weight"},
{"blk.17.gdn.qkv","blk.17.attn_qkv.weight"},
{"blk.18.gdn.qkv","blk.18.attn_qkv.weight"},
{"blk.20.gdn.qkv","blk.20.attn_qkv.weight"},
{"blk.21.gdn.qkv","blk.21.attn_qkv.weight"},
{"blk.22.gdn.qkv","blk.22.attn_qkv.weight"},
{"blk.24.gdn.qkv","blk.24.attn_qkv.weight"},
{"blk.25.gdn.qkv","blk.25.attn_qkv.weight"},
{"blk.28.gdn.qkv","blk.28.attn_qkv.weight"},
{"blk.30.gdn.qkv","blk.30.attn_qkv.weight"},
{"blk.32.gdn.qkv","blk.32.attn_qkv.weight"},
{"blk.36.gdn.qkv","blk.36.attn_qkv.weight"},
{"blk.37.gdn.qkv","blk.37.attn_qkv.weight"},
{"blk.40.gdn.qkv","blk.40.attn_qkv.weight"}
}};
static bool qkv_q6_weight(const Weights&w,const Options&a,const std::string&name){
 if(!a.qkv_q6_p33)return false;
 for(auto [label,weight]:qkv_q6_sites)if(name==weight){
  const auto&t=w.directory.at(name);
  require(a.attention_q8_p33&&a.gsq_packed&&!a.mini&&flash::grid_type(t.grid)==iq3::Type::Q6_K&&t.shape==std::vector<int>({10240,2560})&&t.bytes==21504000,"QKV Q6 exact tensor");return true;
 }return false;
}
static bool qkv_q6_site(const Weights&w,const Options&a,const flash::Launch&l){
 if(!a.qkv_q6_p33)return false;
 for(auto [label,weight]:qkv_q6_sites)if(l.label==label||std::find(l.weights.begin(),l.weights.end(),weight)!=l.weights.end()){
  require(l.label==label&&l.op=="gemv"&&l.weights==std::vector<std::string>{weight}&&l.shape==std::vector<int>({1,10240,2560}),"QKV Q6 exact site");
  return qkv_q6_weight(w,a,weight);
 }return false;
}
static bool combined_site(const Weights&w,const Options&a,const flash::Launch&l){return attention_q8_site(w,a,l)||qkv_q6_site(w,a,l);}
static bool combined_weight(const Weights&w,const Options&a,const std::string&n){return attention_q8_weight(w,a,n)||qkv_q6_weight(w,a,n);}
static void combined_admit(const Weights&w,const Options&a,const flash::Plan&p){
 attention_q8_admit(w,a,p);if(!a.qkv_q6_p33)return;
 std::set<std::string> seen;for(const auto&l:p.launches)if(qkv_q6_site(w,a,l))require(seen.insert(l.label).second,"duplicate QKV Q6 site");
 require(seen.size()==22,"complete QKV Q6 plan");
}
