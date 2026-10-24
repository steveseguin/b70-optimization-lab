#pragma once
static constexpr std::array<std::pair<const char*,const char*>,34> iq3_block_sites{{
{"blk.0.expsgate","blk.0.ffn_gate_exps.weight"},
{"blk.0.expsup","blk.0.ffn_up_exps.weight"},
{"blk.7.expsgate","blk.7.ffn_gate_exps.weight"},
{"blk.7.expsup","blk.7.ffn_up_exps.weight"},
{"blk.12.expsgate","blk.12.ffn_gate_exps.weight"},
{"blk.12.expsup","blk.12.ffn_up_exps.weight"},
{"blk.14.expsgate","blk.14.ffn_gate_exps.weight"},
{"blk.14.expsup","blk.14.ffn_up_exps.weight"},
{"blk.16.expsgate","blk.16.ffn_gate_exps.weight"},
{"blk.16.expsup","blk.16.ffn_up_exps.weight"},
{"blk.18.expsgate","blk.18.ffn_gate_exps.weight"},
{"blk.18.expsup","blk.18.ffn_up_exps.weight"},
{"blk.20.expsgate","blk.20.ffn_gate_exps.weight"},
{"blk.20.expsup","blk.20.ffn_up_exps.weight"},
{"blk.22.expsgate","blk.22.ffn_gate_exps.weight"},
{"blk.22.expsup","blk.22.ffn_up_exps.weight"},
{"blk.30.expsgate","blk.30.ffn_gate_exps.weight"},
{"blk.30.expsup","blk.30.ffn_up_exps.weight"},
{"blk.31.expsgate","blk.31.ffn_gate_exps.weight"},
{"blk.31.expsup","blk.31.ffn_up_exps.weight"},
{"blk.33.expsgate","blk.33.ffn_gate_exps.weight"},
{"blk.33.expsup","blk.33.ffn_up_exps.weight"},
{"blk.37.expsgate","blk.37.ffn_gate_exps.weight"},
{"blk.37.expsup","blk.37.ffn_up_exps.weight"},
{"blk.38.expsgate","blk.38.ffn_gate_exps.weight"},
{"blk.38.expsup","blk.38.ffn_up_exps.weight"},
{"blk.41.expsgate","blk.41.ffn_gate_exps.weight"},
{"blk.41.expsup","blk.41.ffn_up_exps.weight"},
{"blk.42.expsgate","blk.42.ffn_gate_exps.weight"},
{"blk.42.expsup","blk.42.ffn_up_exps.weight"},
{"blk.43.expsgate","blk.43.ffn_gate_exps.weight"},
{"blk.43.expsup","blk.43.ffn_up_exps.weight"},
{"blk.46.expsgate","blk.46.ffn_gate_exps.weight"},
{"blk.46.expsup","blk.46.ffn_up_exps.weight"}
}};
static bool iq3_block_site(const Weights&w,const Options&a,const flash::Launch&l){
 if(!a.expert_iq3xxs_block)return false;
 for(auto [label,weight]:iq3_block_sites)if(l.label==label||std::find(l.weights.begin(),l.weights.end(),weight)!=l.weights.end()){
  require(a.gsq_packed&&a.attention_q8_p33&&a.qkv_q6_p33&&!a.mini,"IQ3 block combined mode");
  require(l.label==label&&l.op=="routed_gemv"&&l.weights==std::vector<std::string>{weight}&&l.shape==std::vector<int>({10,640,2560})&&iq3block::selected(label,weight),"IQ3 block exact site");
  const auto&t=w.directory.at(weight);
  require(unsigned(flash::grid_type(t.grid))==18&&t.shape==std::vector<int>({512,640,2560})&&t.bytes==321126400,"IQ3 block exact packed tensor");
  const auto prefix=l.label.substr(0,l.label.rfind('.'));
  require(l.inputs==std::vector<std::string>{prefix+".expert_input",prefix+".routes","active","error"}&&l.outputs==std::vector<std::string>{l.label,l.label+".status"},"IQ3 block unchanged gathered wiring");return true;
 }return false;
}
static void iq3_block_admit(const Weights&w,const Options&a,const flash::Plan&p){
 if(!a.expert_iq3xxs_block)return;
 std::set<std::string>seen;for(const auto&l:p.launches)if(iq3_block_site(w,a,l))require(seen.insert(l.label).second,"duplicate IQ3 block site");
 require(seen.size()==34,"complete IQ3 block plan");
}
