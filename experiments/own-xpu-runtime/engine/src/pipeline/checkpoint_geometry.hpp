#pragma once
// Position-indexed QSA checkpoint geometry and bounded diagnostic readback.
namespace pipeline {
struct CheckpointQsa {
 size_t row_bytes=0;bool pooled=false;bool operator==(const CheckpointQsa&)const=default;
 size_t offset(int position,int context)const{
  require(position>=0&&position<context,"checkpoint QSA position");
  return size_t(pooled?position/4:position)*row_bytes;
 }
};
template<class Arena,class Qsa> void checkpoint_qsa_scope(const Arena& arena,const std::set<Allocation>& scope,const Qsa& qsa){
 for(auto id:scope){const auto& row=arena.row(id);if(row.category==Category::kv&&(ends(row.label,".keys")||ends(row.label,".values")||ends(row.label,".raw")||ends(row.label,".pooled")))require(qsa.count(id),"checkpoint unclassified QSA allocation");}
}
template<class Plan,class Buffers,class Arena>
std::map<Allocation,CheckpointQsa> checkpoint_qsa(const Plan& p,const Buffers& buffers,const Arena& arena,const std::set<Allocation>& scope,bool validate_scope=true){
 std::set<std::string> names;
 for(const auto& launch:p.launches)if(launch.op=="qsa_append_pool")for(const auto& name:launch.outputs){
  require(ends(name,".keys")||ends(name,".values")||ends(name,".raw")||ends(name,".pooled"),"checkpoint QSA output family");names.insert(name);
 }
 for(const auto& launch:p.launches)for(const auto& name:launch.outputs)if(names.count(name))require(launch.op=="qsa_append_pool","checkpoint QSA extra writer");
 std::map<Allocation,CheckpointQsa> out;
 for(const auto& name:names){
  const auto& slot=buffers.at(name);const auto& row=arena.row(slot.id);require(scope.count(slot.id)&&row.live&&row.memory==Memory::device&&row.category==Category::kv,"checkpoint QSA scope/category");
  const bool pooled=ends(name,".pooled");const size_t rows=pooled?size_t((p.g.context+3)/4):size_t(p.g.context);
  const auto plan=std::find_if(p.buffers.begin(),p.buffers.end(),[&](const auto& b){return b.name==name;});
  require(plan!=p.buffers.end()&&(plan->shape.size()==2||plan->shape.size()==3)&&plan->shape[0]==int(rows),"checkpoint QSA positional/raw-ring geometry");
  require(rows&&row.bytes%rows==0,"checkpoint QSA row divisibility");out.emplace(slot.id,CheckpointQsa{row.bytes/rows,pooled});
 }
 if(validate_scope)checkpoint_qsa_scope(arena,scope,out);
 return out;
}
template<class Owner> std::string checkpoint_allocation_sha(Owner& e,Allocation id,size_t bytes){
 EVP_MD_CTX* context=EVP_MD_CTX_new();require(context&&EVP_DigestInit_ex(context,EVP_sha256(),nullptr)==1,"checkpoint SHA init");
 for(size_t offset=0;offset<bytes;offset+=4ull*1024*1024){const size_t n=std::min(bytes-offset,size_t(4ull*1024*1024));const auto chunk=e.readback_range(0,id,offset,n);require(chunk.size()==n,"checkpoint bounded readback extent");require(EVP_DigestUpdate(context,chunk.data(),chunk.size())==1,"checkpoint SHA update");}
 std::array<unsigned char,32> digest{};unsigned size=0;require(EVP_DigestFinal_ex(context,digest.data(),&size)==1&&size==32,"checkpoint SHA finish");EVP_MD_CTX_free(context);
 std::string out;for(auto b:digest){out+="0123456789abcdef"[b>>4];out+="0123456789abcdef"[b&15];}return out;
}
template<class Owner> void checkpoint_copy_extent(Owner& e,ownrt::CopyEngine& copy,bool reverse,Allocation image,Allocation id,size_t source,size_t backup,size_t bytes){
 for(size_t offset=0;offset<bytes;offset+=SnapshotBatch::limit){const size_t n=std::min(bytes-offset,SnapshotBatch::limit);
  if(reverse)copy.copy(id,source+offset,image,backup+offset,n,{});else copy.copy(image,backup+offset,id,source+offset,n,{});
 }
}
} // namespace pipeline
