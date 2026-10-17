#pragma once
// Included after the packet64 snapshot and wire types. Mutable row allocations
// belong to Engine; canonical buffers never receive speculative suffix writes.
namespace pipeline::depth71 {
using Commands=std::vector<ownrt::PreparedCompute>;
struct Copy {Allocation dst,src;size_t bytes,offset=0;};
struct Rows {
 Engine&e;
 struct Row {
  decltype(e.buffers) buffers;
  std::vector<Allocation> scratch,workspace,controls,scores,probabilities,mixture,fp32;
  std::vector<Commands> commands;
  decltype(e.matrices) matrices;
  int extent=0;int64_t h0=0,h1=0;
  decltype(e.lookup_ids) lookup;
 } rows[2];
 Allocation table=0;size_t allocated=0;
 bool pending=false;int position=0,fixture=0;std::array<int,2> tokens{},outputs{};
 std::map<std::string,bool> cache;std::set<std::string> temporal;
 std::ofstream log;
 struct Scope {
  Engine&e;Row&r;decltype(e.buffers) buffers;decltype(e.prepared) prepared;decltype(e.matrices) matrices;
  decltype(e.state_spares) spares;decltype(e.lookup_ids) lookup;
  std::vector<Allocation>scratch,workspace,controls,scores,probabilities,mixture,fp32,sources;
  std::vector<size_t>extents;int extent;int64_t h0,h1;
  Scope(Engine&v,Row&row,int bound):e(v),r(row),buffers(e.buffers),prepared(std::move(e.prepared)),matrices(std::move(e.matrices)),spares(e.state_spares),lookup(e.lookup_ids),scratch(e.scratch),workspace(e.workspace),controls(e.controls),scores(e.scores),probabilities(e.probabilities),mixture(e.mixture_out),fp32(e.fp32_inputs),sources(e.fp32_sources),extents(e.fp32_extents),extent(e.context_extent),h0(e.history0),h1(e.history1){
   e.buffers=r.buffers;e.state_spares.clear();e.scratch=r.scratch;e.workspace=r.workspace;e.controls=r.controls;e.scores=r.scores;e.probabilities=r.probabilities;e.mixture_out=r.mixture;e.fp32_inputs=r.fp32;
   std::fill(e.fp32_sources.begin(),e.fp32_sources.end(),0);e.context_extent=bound;e.prepared.clear();e.matrices.clear();e.history0=r.h0;e.history1=r.h1;e.prepare_plan();
  }
  ~Scope(){r.h0=e.history0;r.h1=e.history1;r.lookup=e.lookup_ids;e.buffers=std::move(buffers);e.prepared=std::move(prepared);e.matrices=std::move(matrices);e.state_spares=std::move(spares);e.lookup_ids=std::move(lookup);e.scratch=scratch;e.workspace=workspace;e.controls=controls;e.scores=scores;e.probabilities=probabilities;e.mixture_out=mixture;e.fp32_inputs=fp32;e.fp32_sources=sources;e.fp32_extents=extents;e.context_extent=extent;e.history0=h0;e.history1=h1;}
 };
 Allocation clone(Allocation id,const std::string&name){
  size_t n=e.dev(0).arena.row(id).bytes;
  if(id==e.scratch[0])n=std::max(size_t(8*1024*1024),SnapshotWriteSet::scratch(e.p,n,true));
  allocated+=n;require(allocated<=512ull*1024*1024,"depth71 row allocation budget");
  return e.allocate(0,"depth71:"+name,n,Category::runtime_overhead,Lifetime::process);
 }
 explicit Rows(Engine&owner):e(owner),log(e.a.output/"depth2-rows.jsonl"){
  require(e.resident&&!e.miss_banks(),"depth71 requires resident two-bank parent");
  for(auto&l:e.p.launches){if(l.op=="gdn"||l.op=="conv")temporal.insert(l.outputs.at(1));
   if(l.op=="qsa_append_pool")for(auto&n:l.outputs)cache[n]=ends(n,".pooled");}
  for(unsigned r=0;r<2;++r){auto&row=rows[r];row.buffers=e.buffers;
   for(auto&[name,b]:row.buffers[0])b.id=clone(b.id,std::to_string(r)+":"+name);
   auto clone_list=[&](const auto&source,auto&dest,const std::string&name){for(auto id:source)dest.push_back(clone(id,std::to_string(r)+":"+name));};
   clone_list(e.scratch,row.scratch,"scratch");clone_list(e.workspace,row.workspace,"workspace");clone_list(e.controls,row.controls,"controls");clone_list(e.scores,row.scores,"scores");clone_list(e.probabilities,row.probabilities,"probabilities");clone_list(e.mixture_out,row.mixture,"mixture");clone_list(e.fp32_inputs,row.fp32,"fp32");
  }
  table=e.allocate(0,"depth71:copy-table",4096*sizeof(SnapshotFlat::Item),Category::runtime_overhead,Lifetime::process);
 }
 void copies(const std::vector<Copy>& list){
  if(list.empty())return;e.drain();ownrt::CopyEngine copy(e.dev(0));Commands checked;std::vector<size_t>lengths;
  e.dev(0).begin_capture(checked);
  try{for(auto x:list)for(size_t off=0;off<x.bytes;off+=SnapshotBatch::limit){size_t n=std::min(x.bytes-off,SnapshotBatch::limit);copy.copy(x.dst,x.offset+off,x.src,x.offset+off,n,{});lengths.push_back(n);}e.dev(0).end_capture();}catch(...){e.dev(0).end_capture();throw;}
  require(checked.size()==lengths.size()&&checked.size()<=4096,"depth71 checked copy cardinality");
  std::vector<SnapshotFlat::Item>items;std::vector<Allocation>ids{table};size_t tiles=0;
  for(size_t i=0;i<checked.size();++i){const auto&c=checked[i];require(c.ids.size()==2&&c.pointers.size()==2,"depth71 copy descriptor");tiles+=(lengths[i]+4095)/4096;items.push_back({(uint8_t*)c.pointers[0],(const uint8_t*)c.pointers[1],lengths[i],tiles});ids.insert(ids.end(),c.ids.begin(),c.ids.end());}
  if(items.empty())return;e.upload(0,table,0,items.data(),items.size()*sizeof(items[0]));SnapshotFlat op;op.count=items.size();op.tiles=tiles;e.tail=e.dev(0).compute(op,ids,{});e.drain();
 }
 void capture(unsigned r,int pos){auto&row=rows[r];int extent=std::min(e.p.g.context,((pos+32)/32)*32);
  if(row.extent==extent)return;
  Scope scope(e,row,extent);row.commands.clear();row.commands.resize(e.p.launches.size());
  for(size_t i=0;i<e.p.launches.size();++i){e.preparing_commands=true;e.dev(0).begin_capture(row.commands[i]);try{e.execute_site(e.p.launches[i]);e.dev(0).end_capture();e.preparing_commands=false;}catch(...){e.dev(0).end_capture();e.preparing_commands=false;throw;}}
  row.matrices=e.matrices;row.extent=extent;
 }
 void initialize_row(unsigned r,int pos,int token,const uint8_t*stream){auto&row=rows[r];std::vector<Copy>list;
  for(auto&[name,b]:row.buffers[0]){auto src=e.buffers[0].at(name);list.push_back({b.id,src.id,b.n*flash::scalar_bytes(b.type)});}
  copies(list);
  e.upload(0,row.buffers[0].at("position").id,0,&pos,4);e.upload(0,row.buffers[0].at("token").id,0,&token,4);
  if(e.a.rank==1){require(stream,"depth71 rank1 streams absent");e.upload(0,row.buffers[0].at("streams").id,0,stream,4*e.p.g.h*2);}
  else {Scope scope(e,row,std::min(e.p.g.context,((pos+32)/32)*32));e.prepare_token(token);e.drain();}
  capture(r,pos);
 }
 void issue(const Commands&commands){for(auto&cmd:commands){e.tail=e.dev(0).issue(cmd);}pipeline_cancel_check();}
 // Replaced by the copied production M2 table in the integration milestone.
 bool paired(size_t){return false;}
 Reply run(const Request&r,uint8_t*shared){
  require(!pending&&r.position>=0&&r.position+1<e.p.g.context,"depth71 pair ownership/capacity");
  position=r.position;fixture=r.fixture;tokens={r.token,r.reserved[0]};outputs={-1,-1};
  for(int t:tokens)require(t>=0&&t<e.p.g.vocab,"depth71 pair token bounds");
  require(e.integer(0,"position")==position,"depth71 canonical position");e.drain();
  auto start=std::chrono::steady_clock::now();rows[0].h0=e.history0;rows[0].h1=e.history1;
  initialize_row(0,position,tokens[0],e.a.rank?shared+slot_bytes:nullptr);
  rows[1].h0=rows[0].h0;rows[1].h1=rows[0].h1;
  initialize_row(1,position+1,tokens[1],e.a.rank?shared+slot_bytes+4*e.p.g.h*2:nullptr);
  pending=true;
  for(size_t i=0;i<e.p.launches.size();++i){auto&l=e.p.launches[i];if(paired(i))continue;
   issue(rows[0].commands[i]);
   std::vector<Copy>forward;
   if(l.op=="gdn"||l.op=="conv"||l.op=="ple_hash"||l.op=="qsa_append_pool")for(auto&name:l.outputs){
    if(!temporal.count(name)&&!cache.count(name)&&name!="token_history")continue;
    auto a=rows[0].buffers[0].at(name),b=rows[1].buffers[0].at(name);size_t bytes=a.n*flash::scalar_bytes(a.type),offset=0;
    if(cache.count(name)){size_t n=cache.at(name)?(e.p.g.context+3)/4:e.p.g.context;bytes/=n;offset=size_t(cache.at(name)?position/4:position)*bytes;}
    forward.push_back({b.id,a.id,bytes,offset});
   }
   copies(forward);issue(rows[1].commands[i]);
  }
  e.drain();size_t n=4*e.p.g.h*2;
  for(unsigned row=0;row<2;++row){auto readint=[&](const std::string&name){auto raw=e.readback(0,rows[row].buffers[0].at(name).id,4);int v;std::memcpy(&v,raw.data(),4);return v;};
   require(!readint("error"),"depth71 sticky row error");require(readint("position")==position+int(row)+1,"depth71 row did not commit");
   if(e.a.rank==0){auto raw=e.readback(0,hidden(row),n);std::memcpy(shared+row*n,raw.data(),n);}else outputs[row]=readint("next_token");
  }
  log<<"{\"position\":"<<position<<",\"dependent\":true,\"kernels\":"<<ownrt::quote(e.a.depth2_kernels)<<",\"pair_ms\":"<<Engine::ms(start)<<"}\n";log.flush();
  Reply reply{};reply.rank=e.a.rank;reply.sequence=r.sequence;reply.token=outputs[0];reply.reserved[0]=outputs[1];reply.bytes=e.a.rank?0:int(n*2);reply.busy_ms=Engine::ms(start);return reply;
 }
 Allocation hidden(unsigned row)const{return rows[row].buffers[0].at("streams").id;}
 void select(unsigned prefix){
  require(pending&&prefix<=2,"depth71 prefix selection");e.drain();
  for(auto&r:rows){auto raw=e.readback(0,r.buffers[0].at("error").id,4);int error;std::memcpy(&error,raw.data(),4);require(!error,"depth71 cannot erase sticky row error");}
  if(prefix){unsigned r=prefix-1;
   if(e.a.rank==0&&prefix==1)e.swap_state_banks();
   std::vector<Copy>list;
   for(auto&[name,b]:e.buffers[0]){auto src=rows[r].buffers[0].at(name);size_t bytes=b.n*flash::scalar_bytes(b.type),offset=0;
    if(cache.count(name)){size_t n=cache.at(name)?(e.p.g.context+3)/4:e.p.g.context;size_t stride=bytes/n;size_t first=cache.at(name)?position/4:position;size_t last=cache.at(name)?(position+prefix-1)/4:position+prefix-1;offset=first*stride;bytes=(last-first+1)*stride;}
    list.push_back({b.id,src.id,bytes,offset});
   }
   if(e.a.rank==0&&prefix==2)for(auto&[name,id]:e.state_spares){auto src=rows[0].buffers[0].at(name);list.push_back({id,src.id,src.n*flash::scalar_bytes(src.type)});}
   copies(list);e.history0=rows[r].h0;e.history1=rows[r].h1;e.lookup_ids=rows[r].lookup;e.fp32_sources[0]=0;e.fp32_extents[0]=0;e.admit_position(position+prefix-1);
  }
  log<<"{\"position\":"<<position<<",\"accepted_prefix\":"<<prefix<<"}\n";log.flush();pending=false;
 }
};
}
