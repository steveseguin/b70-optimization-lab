// Micro-only accessors. No production call site uses these entry points.
using MicroSnapshot=std::vector<std::pair<Allocation,std::vector<uint8_t>>>;
MicroSnapshot micro_snapshot(){e.drain();MicroSnapshot out;for(auto a:mutable_ids)out.emplace_back(a,e.readback(0,a,e.dev(0).arena.row(a).bytes));return out;}
void micro_restore(const MicroSnapshot& s,int pos){e.drain();for(const auto&[a,b]:s){require(mutable_ids.contains(a),"micro mutable ownership");e.upload(0,a,0,b.data(),b.size());}position=pos;disabled=false;admit_position();}
void micro_inputs(const std::vector<uint8_t>& hidden,int token){
 require(hidden.size()==size_t(4*p.g.h*2),"captured hidden extent");
 e.upload(0,id("merge.hidden"),0,hidden.data(),hidden.size());
 auto t=e.w.directory.at("token_embd.weight");auto type=flash::grid_type(t.grid);auto fmt=iq3::layout(type);size_t rb=p.g.h/fmt.elements*fmt.bytes;
 auto raw=e.w.read(t.name,size_t(token)*rb,rb);std::vector<uint16_t> emb(p.g.h);for(int k=0;k<p.g.h;++k)emb[k]=iq3::bf16_bits(iq3::element(type,raw.data(),k));e.upload(0,id("embedding"),0,emb.data(),emb.size()*2);e.drain();
}
void micro_issue(bool head){
 require(captured,"prepared draft required");e.draft_timing=true;
 for(const auto& site:issue_sites){if(!head&&site.head)continue;e.guard();e.current_cls=site.cls;for(const auto&cmd:site.commands){auto event=e.dev(0).issue(cmd);e.finish(0,{event,event,1},site.gemv);}}
 e.draft_timing=false;
}
void micro_prefill(const std::vector<uint8_t>& hidden,int token){micro_inputs(hidden,token);admit_position();micro_issue(false);e.drain();require(e.readback(0,id("error"),4)==std::vector<uint8_t>(4,0),"draft prefill status");++position;}
int micro_status(){auto v=e.readback(0,id("error"),4);int n;std::memcpy(&n,v.data(),4);return n;}
