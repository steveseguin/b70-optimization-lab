#include "gemv_batch.hpp"
#include <algorithm>
#include <array>
#include <cstring>
#ifndef OWN_RT_HOST_ONLY
#include "sycl_operation.hpp"
#endif
namespace packet21 {
namespace {
constexpr unsigned absent=~0u;
struct Desc {
 iq3::Type type,peer_type;
 size_t first,groups,rows,k,rb,peer_rb;
 unsigned variant,peer_variant,count,experts,input_rows;
 unsigned w,x,y,route,status,peer_w,peer_y,peer_status,aux,materialized,other,destination,route_prob,route_top;
 InputTransform input;OutputTransform output;
 bool routed,shared,paired;float scale;
};
float bfvalue(uint16_t x){return iq3::bits_float(uint32_t(x)<<16);}
float sigmoid(float x){return 1.f/(1.f+detmath::exp(-x));}
float silu(float x){return x*sigmoid(x);}
uint16_t transformed(const Desc& d,const uint16_t* x,const uint16_t* aux,size_t col){
 if(d.input==InputTransform::silu_div4)return iq3::bf16_bits(silu(bfvalue(x[col])/4.f));
 float v=0;for(unsigned i=0;i<4;++i)v=v+sigmoid(bfvalue(aux[i*d.k+col]))*bfvalue(x[i*d.k+col]);
 return iq3::bf16_bits(v/4.f);
}
void normalize(const Desc& d,void* const* p){
 if(d.route_prob==absent)return;auto prob=static_cast<float*>(p[d.route_prob]);float sum[32]{};for(unsigned i=0;i<d.route_top;++i)sum[i]=prob[i];
 unsigned n=d.route_top;while(n>1){if(n%2)sum[n++]=0;for(unsigned i=0;i<n/2;++i)sum[i]=sum[2*i]+sum[2*i+1];n/=2;}
 for(unsigned i=0;i<d.route_top;++i)prob[i]=prob[i]/sum[0];
}
void stores(const Desc& d,void* const* p,size_t index,float first,float second){
 auto a=iq3::bf16_bits(first);static_cast<uint16_t*>(p[d.y])[index]=a;
 if(d.paired){auto b=iq3::bf16_bits(second);static_cast<uint16_t*>(p[d.peer_y])[index]=b;
  static_cast<uint16_t*>(p[d.other])[index]=iq3::bf16_bits(silu(bfvalue(a))*bfvalue(b));
 }else if(d.output==OutputTransform::residual)
  static_cast<uint16_t*>(p[d.destination])[index]=iq3::bf16_bits(bfvalue(static_cast<const uint16_t*>(p[d.other])[index])+bfvalue(a));
 else if(d.output==OutputTransform::hc_residual){
  for(unsigned stream=0;stream<4;++stream){size_t at=stream*d.rows+index;
   auto source=static_cast<const uint16_t*>(p[d.other]);auto inject=static_cast<const uint16_t*>(p[d.aux]);
   static_cast<uint16_t*>(p[d.destination])[at]=iq3::bf16_bits(bfvalue(source[at])+bfvalue(a)*(2.f*sigmoid(bfvalue(inject[stream])/4.f)));}
 }
 else if(d.output==OutputTransform::scale)
  static_cast<uint16_t*>(p[d.destination])[index]=iq3::bf16_bits(bfvalue(a)*d.scale);
}
#ifdef OWN_RT_HOST_ONLY
struct Batch final:integrated::HostOperation {
 unsigned count;size_t groups;std::vector<unsigned> batch_access;
 void run(std::span<void* const> pointers)const override {
  auto p=pointers.data()+1;auto ds=static_cast<const Desc*>(pointers[0]);
  for(unsigned di=0;di<count;++di){auto d=ds[di];normalize(d,p);
   // CPU emulation evaluates each pure BF16 prologue once per distinct input
   // in this submission. Device rows recompute the identical expression. No
   // state or result survives this operation, and aliases are rejected before
   // submission, so all output rows observe the same unchanged source bytes.
   std::vector<uint16_t> prepared;
   if(d.input!=InputTransform::none){size_t inputs=size_t(d.input_rows)*(d.shared?1:d.count);prepared.resize(inputs*d.k);
    for(size_t xi=0;xi<inputs;++xi){auto source=static_cast<const uint16_t*>(p[d.x])+xi*d.k*(d.input==InputTransform::hc_mix?4:1);
     auto aux=d.aux==absent?nullptr:static_cast<const uint16_t*>(p[d.aux])+xi*d.k*4;
     for(size_t c=0;c<d.k;++c)prepared[xi*d.k+c]=transformed(d,source,aux,c);
    }
    if(d.materialized!=absent)std::memcpy(p[d.materialized],prepared.data(),size_t(d.input_rows)*d.k*2);
   }
   #pragma omp parallel for schedule(static) num_threads(2)
   for(size_t logical=0;logical<d.rows*d.count*d.input_rows;++logical){
    size_t row=logical%d.rows,slot=(logical/d.rows)%d.count,mi=logical/(d.rows*d.count);
    iq3::Route route{0,0,uint32_t(d.rows)};
    if(d.routed)route=static_cast<const iq3::Route*>(p[d.route])[slot];
    bool valid=iq3::valid_route(route,d.experts,d.rows,d.rows);
    if(d.routed && row==0 && mi==0){static_cast<uint32_t*>(p[d.status])[slot]=valid?0:1;if(d.paired)static_cast<uint32_t*>(p[d.peer_status])[slot]=valid?0:1;}
    size_t xi=mi*(d.shared?1:d.count)+(d.shared?0:slot);
    auto x=static_cast<const uint16_t*>(p[d.x])+xi*d.k*(d.input==InputTransform::hc_mix?4:1);
    if(d.input!=InputTransform::none)x=prepared.data()+xi*d.k;
    float a=iq3::bits_float(0x7fc00000),b=a;
    if(valid && row<route.row_count){size_t wi=size_t(route.expert_id)*d.rows+route.row_begin+row;
     a=integrated::arithmetic::row(d.type,static_cast<const uint8_t*>(p[d.w])+wi*d.rb,x,d.k,d.variant);
     if(d.paired)b=integrated::arithmetic::row(d.peer_type,static_cast<const uint8_t*>(p[d.peer_w])+wi*d.peer_rb,x,d.k,d.peer_variant);
    }
    stores(d,p,logical,a,b);
   }
  }
 }
};
#else
struct Share {
 sycl::sub_group sg;unsigned lane;
 template<class F> auto operator()(unsigned owner,F f)const {using R=decltype(f(owner));R v{};if(lane==owner)v=f(owner);return sycl::select_from_group(sg,v,owner);}
};
struct Tables:iq3::kopt3::ConstantTables {
 sycl::sub_group sg;explicit Tables(sycl::sub_group v):sg(v){}
 int iq4(unsigned i)const {unsigned l=sg.get_local_linear_id();int v=l<16?iq3::kopt3::iq4_levels[l]:0;return sycl::select_from_group(sg,v,i);}
};
float dot(iq3::Type t,const uint8_t* w,const uint16_t* x,size_t k,unsigned variant,unsigned part,unsigned lane,sycl::sub_group sg){
 auto bounds=iq3::kopt2::bounds(k,part,variant==1||variant==4||variant==7?4:1);
 if(variant>=6)return iq3::expanded::lane(t,w,x,iq3::Type::BF16,k,bounds.first,bounds.second,lane);
 if(variant<=1)return iq3::kopt2::lane(t,w,x,iq3::Type::BF16,bounds.first,bounds.second,lane);
 #define C(T) case iq3::Type::T:return iq3::kopt3::dot<iq3::Type::T>(w,x,iq3::Type::BF16,bounds.first,bounds.second,lane,Tables(sg),Share{sg,lane})
 switch(t){C(F32);C(F16);C(BF16);C(Q8_0);C(Q6_K);C(Q3_K);C(IQ3_XXS);C(IQ2_S);C(IQ3_S);C(IQ4_NL);}
 #undef C
 return iq3::bits_float(0x7fc00000);
}
struct Batch final:ownrt::SyclOperation {
 unsigned count,local_columns;size_t groups;
 sycl::event submit(sycl::queue& q,std::span<void* const> pointers,const std::vector<sycl::event>& dependencies)const override {
  if(pointers.size()>128)throw std::invalid_argument("batch pointer count");
  std::array<void*,128> ptr{};std::copy(pointers.begin()+1,pointers.end(),ptr.begin());
  auto ds=static_cast<const Desc*>(pointers[0]);auto n=count;auto ng=groups;auto cols=local_columns;
  return q.submit([&](sycl::handler& h){h.depends_on(dependencies);
   sycl::local_accessor<uint16_t,1> local(cols,h);sycl::local_accessor<float,1> partial(8,h);
   h.parallel_for(sycl::nd_range<1>(ng*128,128),[=](sycl::nd_item<1> it) [[sycl::reqd_sub_group_size(32)]] {
    size_t group=it.get_group_linear_id();unsigned which=0;for(unsigned i=1;i<n;++i)if(group>=ds[i].first)which=i;
    auto d=ds[which];size_t logical=group-d.first;if(logical==d.rows*d.count*d.input_rows){if(it.get_local_linear_id()==0)normalize(d,ptr.data());return;}
    size_t row=logical%d.rows,slot=(logical/d.rows)%d.count,mi=logical/(d.rows*d.count);
    auto sg=it.get_sub_group();unsigned lane=sg.get_local_linear_id(),sub=sg.get_group_linear_id(),wi=it.get_local_linear_id();
    iq3::Route route{0,0,uint32_t(d.rows)};if(d.routed)route=static_cast<const iq3::Route*>(ptr[d.route])[slot];
    bool valid=iq3::valid_route(route,d.experts,d.rows,d.rows),active=valid&&row<route.row_count;
    if(d.routed && row==0 && mi==0 && wi==0){static_cast<uint32_t*>(ptr[d.status])[slot]=valid?0:1;if(d.paired)static_cast<uint32_t*>(ptr[d.peer_status])[slot]=valid?0:1;}
    size_t xi=mi*(d.shared?1:d.count)+(d.shared?0:slot);
    auto x=static_cast<const uint16_t*>(ptr[d.x])+xi*d.k*(d.input==InputTransform::hc_mix?4:1);
    if(d.input!=InputTransform::none){auto aux=d.aux==absent?nullptr:static_cast<const uint16_t*>(ptr[d.aux])+xi*d.k*4;
     for(size_t c=wi;c<d.k;c+=128){auto value=transformed(d,x,aux,c);local[c]=value;
      if(d.materialized!=absent && row==0 && slot==0)static_cast<uint16_t*>(ptr[d.materialized])[mi*d.k+c]=value;}
     it.barrier(sycl::access::fence_space::local_space);x=local.template get_multi_ptr<sycl::access::decorated::no>().get();
    }
    for(unsigned peer=0;peer<(d.paired?2u:1u);++peer){unsigned v=peer?d.peer_variant:d.variant,split=v==1||v==4||v==7?4:1;
     float value=0;if(active && sub<split){auto w=static_cast<const uint8_t*>(ptr[peer?d.peer_w:d.w])+(size_t(route.expert_id)*d.rows+route.row_begin+row)*(peer?d.peer_rb:d.rb);
      value=dot(peer?d.peer_type:d.type,w,x,d.k,v,sub,lane,sg);}
     for(unsigned width=1;width<32;width*=2){float rhs=sycl::select_from_group(sg,value,(lane+width)%32);if(lane%(2*width)==0)value=value+rhs;}
     if(lane==0)partial[peer*4+sub]=value;
    }
    it.barrier(sycl::access::fence_space::local_space);
    if(wi==0){float values[2]{};for(unsigned peer=0;peer<(d.paired?2u:1u);++peer){unsigned v=peer?d.peer_variant:d.variant;
      values[peer]=v==1||v==4||v==7?(partial[peer*4]+partial[peer*4+1])+(partial[peer*4+2]+partial[peer*4+3]):partial[peer*4];
      if(!active)values[peer]=iq3::bits_float(0x7fc00000);}
     stores(d,ptr.data(),logical,values[0],values[1]);}
   });
  });
 }
};
#endif
}
PreparedBatch prepare_batch(ownrt::Device& device,const std::vector<BatchSpec>& specs,unsigned input_rows){
 if(specs.empty()||specs.size()>8||!input_rows)throw std::invalid_argument("batch geometry");
 PreparedBatch result;std::vector<Desc> desc;std::vector<std::pair<uint64_t,bool>> accesses;
 auto add=[&](ownrt::Allocation id,size_t bytes,bool write){auto r=device.arena.row(id);if(!r.live||r.memory!=ownrt::Memory::device||bytes>r.bytes)throw std::invalid_argument("batch extent");
  accesses.emplace_back(id,write);result.binding_access.push_back(write?2:1);result.bindings.push_back(id);return unsigned(result.bindings.size()-1);};
 for(const auto& spec:specs){const auto& m=spec.matrix;auto layout=iq3::layout(m.type);
  if(!layout.elements||!m.rows||m.rows>UINT32_MAX||!m.columns||m.columns>17408||m.columns%layout.elements||!m.count||!m.experts||(m.span&&m.span!=m.rows)||bool(m.routes)!=bool(m.status)||m.activation!=iq3::Type::BF16||m.output_type!=iq3::Type::BF16||m.fp32||spec.variant==3||spec.variant==5||spec.variant>7)throw std::invalid_argument("batch matrix class");
  if(!m.routes&&(m.experts!=1||m.count!=1))throw std::invalid_argument("batch route missing");
  if(spec.paired!=(spec.output==OutputTransform::silu_product))throw std::invalid_argument("paired activation contract");
  if(spec.materialized_input && (spec.input==InputTransform::none || (!spec.shared_input && m.count>1)))throw std::invalid_argument("materialized input contract");
  Desc d{};d.type=m.type;d.rows=m.rows;d.k=m.columns;d.rb=integrated::arithmetic::row_bytes(m.type,m.columns,spec.variant);d.first=result.groups;d.groups=m.rows*m.count*input_rows;
  d.variant=spec.variant;d.peer_variant=spec.peer_variant;d.count=m.count;d.experts=m.experts;d.input_rows=input_rows;d.routed=m.routes!=0;d.shared=spec.shared_input;d.paired=spec.paired;d.input=spec.input;d.output=spec.output;d.scale=spec.scale;
  d.route=d.status=d.peer_w=d.peer_y=d.peer_status=d.aux=d.materialized=d.other=d.destination=d.route_prob=absent;d.route_top=0;
  size_t nx=size_t(input_rows)*(d.shared?1:m.count)*m.columns;
  d.w=add(m.w,size_t(m.experts)*m.rows*d.rb,false);d.x=add(m.x,nx*2*(d.input==InputTransform::hc_mix?4:1),false);d.y=add(m.y,d.groups*2,true);
  if(d.routed){d.route=add(m.routes,m.count*sizeof(iq3::Route),false);result.binding_access.back()|=4;d.status=add(m.status,m.count*4,true);}
  if(d.input==InputTransform::hc_mix)d.aux=add(spec.auxiliary,nx*8,false);
  if(spec.materialized_input)d.materialized=add(spec.materialized_input,size_t(input_rows)*m.columns*2,true);
  if(d.input!=InputTransform::none)result.local_columns=std::max(result.local_columns,unsigned(m.columns));
  if(spec.paired){const auto& peer=spec.peer;auto peer_layout=iq3::layout(peer.type);
   if(!peer_layout.elements || peer.columns%peer_layout.elements || (peer.span&&peer.span!=peer.rows) || bool(peer.routes)!=bool(peer.status))throw std::invalid_argument("batch peer class/routes");
   if(peer.rows!=m.rows||peer.columns!=m.columns||peer.count!=m.count||peer.experts!=m.experts||peer.x!=m.x||peer.routes!=m.routes||peer.activation!=iq3::Type::BF16||peer.output_type!=iq3::Type::BF16||peer.fp32||spec.peer_variant==3||spec.peer_variant==5||spec.peer_variant>7)throw std::invalid_argument("batch peer mismatch");
   if(d.routed){if(!peer.status)throw std::invalid_argument("peer status missing");d.peer_status=peer.status==m.status?d.status:add(peer.status,m.count*4,true);}
   d.peer_type=peer.type;d.peer_rb=integrated::arithmetic::row_bytes(peer.type,peer.columns,spec.peer_variant);d.peer_w=add(peer.w,size_t(peer.experts)*peer.rows*d.peer_rb,false);d.peer_y=add(peer.y,d.groups*2,true);d.other=add(spec.other,d.groups*2,true);
  }else if(spec.output==OutputTransform::residual){d.other=add(spec.other,d.groups*2,false);d.destination=add(spec.destination,d.groups*2,true);}
  else if(spec.output==OutputTransform::scale)d.destination=add(spec.destination,d.groups*2,true);
  else if(spec.output==OutputTransform::hc_residual){
   if(spec.input!=InputTransform::none || input_rows!=1 || m.count!=1)throw std::invalid_argument("hc residual geometry");
   d.aux=add(spec.auxiliary,8,false);
   if(spec.other==spec.destination){d.other=d.destination=add(spec.other,m.rows*8,true);result.binding_access.back()=3;}
   else{d.other=add(spec.other,m.rows*8,false);d.destination=add(spec.destination,m.rows*8,true);}
  }
  if(spec.route_prob){if(!spec.route_top||spec.route_top>32)throw std::invalid_argument("route probability extent");d.route_prob=add(spec.route_prob,spec.route_top*4,true);result.binding_access.back()=3;d.route_top=spec.route_top;++d.groups;}
  result.groups+=d.groups;desc.push_back(d);
 }
 iq3::kopt3::validate_aliases(accesses);result.count=desc.size();result.descriptor_bytes.resize(desc.size()*sizeof(Desc));std::memcpy(result.descriptor_bytes.data(),desc.data(),result.descriptor_bytes.size());return result;
}
integrated::Launch gemv_batch(ownrt::Device& device,const PreparedBatch& plan,ownrt::Allocation table){
 auto r=device.arena.row(table);if(!r.live||r.memory!=ownrt::Memory::device||r.bytes<plan.descriptor_bytes.size())throw std::invalid_argument("batch table extent");
 if(std::find(plan.bindings.begin(),plan.bindings.end(),table)!=plan.bindings.end())throw std::invalid_argument("batch table alias");
 Batch op;op.count=plan.count;op.groups=plan.groups;
 #ifdef OWN_RT_HOST_ONLY
 op.batch_access=plan.binding_access;
 #endif
 #ifndef OWN_RT_HOST_ONLY
 op.local_columns=plan.local_columns;
 #endif
 auto ids=plan.bindings;ids.insert(ids.begin(),table);auto event=device.compute(op,ids,{});return {event,event,1};
}
}
