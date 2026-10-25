#pragma once
#include "pipeline/recursive_provider/peer.hpp"
namespace pipeline::recursive_provider {
struct Admission {ownrt::recursive_provider_next::Input input;ownrt::recursive_provider_next::ExpectedPair expected;};
inline Admission admit_batch(const Request& request,const ownrt::ring_next::wire::Context& context,const ownrt::ring_next::Row& seed,const Peer::Event& event,std::span<const uint8_t> metadata,std::span<const uint8_t> relay_header,std::span<const uint8_t> relay_hidden,uint64_t next_serial){
 namespace wire=ownrt::ring_next::wire;require(context.stage==0&&seed.position>0&&request.sequence>0&&next_serial>0,"ring recursive admission owner/serial");
 require(request.op==wire::batch_op&&request.token==seed.token&&request.position==seed.position&&request.fixture==int(seed.fixture>0)&&request.speculative==2&&request.reserved[0]==context.stage&&!request.reserved[1],"ring recursive command seed/head/depth");
 wire::RowMeta expected;expected.epoch=seed.epoch;expected.id=seed.id;expected.parent=seed.parent;expected.position=seed.position;expected.token=seed.token;expected.fixture=seed.fixture;expected.owner=context.stage;expected.final=0;expected.flags=seed.tentative?wire::tentative:0;expected.request=seed.request;expected.before=seed.before;expected.after=seed.after;expected.payload_sha=wire::digest({});
 const auto submitted=wire::read<wire::RowMeta>(metadata);require(!std::memcmp(&expected,&submitted,sizeof expected),"ring recursive metadata differs from owned accepted seed");
 require(seed.parent==event.record.row.id&&seed.before==event.record.row.after&&seed.position==event.record.row.position+1,"ring recursive independent final ancestry");
 Admission result;auto& input=result.input;input.seed=seed;input.sequence=request.sequence;input.head=request.fixture!=0;
 input.parent=wire::read<ownrt::live_draft::Handoff>(relay_header);input.hidden.assign(relay_hidden.begin(),relay_hidden.end());require(input.hidden==event.hidden,"ring recursive relay bytes differ from final owner");
 require(!std::memcmp(&input.parent,&event.record.hidden,sizeof(input.parent)),"ring recursive relay header differs from final owner");
 result.expected={seed,event.record.hidden,next_serial};return result;
}
}
