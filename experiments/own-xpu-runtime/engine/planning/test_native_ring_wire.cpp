#include "pipeline/ring/wire.hpp"
#include <cassert>
#include <iostream>
using namespace ownrt::ring_next;
namespace w=ownrt::ring_next::wire;
template<class F>void refusal(F f){bool failed=false;try{f();}catch(const std::exception&){failed=true;}assert(failed);}
int main(){
 w::Context c{2,{},1,4,16,97};c.request.fill('r');std::vector<uint8_t> input(16,7);
 w::RowMeta m;m.epoch=2;m.id=12;m.parent=11;m.position=2;m.token=7;m.fixture=1;m.owner=1;m.source=0;m.source_ticket=21;m.payload_bytes=16;m.flags=w::tentative;m.request=c.request;m.before=request_prefix(c.request,c.epoch);m.after=extend(m.before,m.position,m.token);m.payload_sha=w::digest(input);
 w::Command command{24,7,2,1,1,41,1,0};auto row=w::row(m,command,c,input);assert(row.id==12&&row.parent==11&&row.ticket==41&&row.tentative);
 auto bytes=std::array<uint8_t,sizeof(m)>{};w::write(std::span<uint8_t>(bytes),m);auto copy=w::read<w::RowMeta>(bytes);assert(copy.payload_sha==m.payload_sha);
 refusal([&]{w::read<w::RowMeta>({bytes.data(),bytes.size()-1});});
 for(int which=0;which<10;++which){auto bad=m;switch(which){case 0:bad.version=2;break;case 1:bad.flags|=2;break;case 2:bad.reserved[0]=1;break;case 3:bad.owner=2;break;case 4:bad.source_ticket=0;break;case 5:bad.payload_bytes=12;break;case 6:bad.payload_sha[0]^=1;break;case 7:bad.after[0]^=1;break;case 8:bad.epoch=1;break;case 9:bad.parent=bad.id;break;}refusal([&]{w::row(bad,command,c,input);});}
 auto output=std::vector<uint8_t>(16,9);auto publication=w::publication(m,41,output);assert(publication.flags==3&&publication.publication_ticket==41&&publication.payload_sha==w::digest(output));
 w::validate_publication(publication,m,41,c,output);auto badpub=publication;badpub.parent=10;refusal([&]{w::validate_publication(badpub,m,41,c,output);});badpub=publication;badpub.publication_ticket=40;refusal([&]{w::validate_publication(badpub,m,41,c,output);});
 auto resolution=m;resolution.source=-1;resolution.source_ticket=0;resolution.payload_bytes=0;resolution.payload_sha=w::digest({});
 w::Command accept{25,7,2,1,41,42,1,0};assert(w::resolution(resolution,accept,c)==row);
 auto bad=resolution;bad.source_ticket=21;refusal([&]{w::resolution(bad,accept,c);});accept.speculative=42;refusal([&]{w::resolution(resolution,accept,c);});accept.speculative=41;
 auto ack=w::acknowledgment(c,42,row,{4,3,1,{}},false);w::validate_ack(ack,c,42,row,{});assert(ack.physical==4&&ack.committed==3);auto wrongcursor=ack;wrongcursor.physical=5;refusal([&]{w::validate_ack(wrongcursor,c,42,row,{});});ack.flags=1;refusal([&]{w::validate_ack(ack,c,42,row,{});});
 auto aborted=w::acknowledgment(c,43,row,{2,2,0,{12,13}},true);w::validate_ack(aborted,c,43,row,{12,13});auto forged=aborted;forged.discarded1=14;refusal([&]{w::validate_ack(forged,c,43,row,{12,13});});forged=aborted;forged.physical=3;refusal([&]{w::validate_ack(forged,c,43,row,{12,13});});
 w::ProposalMeta batch;batch.epoch=2;batch.ticket=44;batch.seed_row=12;batch.parent_row=11;batch.final_commit=40;batch.provider_serial=2;batch.seed_position=batch.restored_position=2;batch.available_depth=2;batch.guess0=12;batch.guess1=13;batch.flags=3;batch.restored=1;batch.request=c.request;batch.seed_prefix=m.after;batch.hidden_sha=m.payload_sha;
 w::BatchIdentity identity{12,11,40,2};
 for(int which=0;which<4;++which){auto wrong=batch;switch(which){case 0:++wrong.seed_row;break;case 1:--wrong.parent_row;break;case 2:++wrong.final_commit;break;case 3:++wrong.provider_serial;break;}refusal([&]{w::validate_batch(wrong,c,44,2,m.after,m.payload_sha,identity);});}
 w::validate_batch(batch,c,44,2,m.after,m.payload_sha,identity);batch.available_depth=1;batch.guess1=-1;w::validate_batch(batch,c,44,2,m.after,m.payload_sha,identity);batch.restored=0;refusal([&]{w::validate_batch(batch,c,44,2,m.after,m.payload_sha,identity);});
 std::cout<<"PASS exact224/192/128B wire layout, SHA/prefix/stage/ticket/padding/extent checks, exact suffix ACKs and canonical restored batch contract; CPU only\n";
}
