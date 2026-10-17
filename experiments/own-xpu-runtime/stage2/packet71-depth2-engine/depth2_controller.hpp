#pragma once
namespace pipeline::native38 {
// The first screen deliberately drains between tiles. Rank0's two proposed
// rows overlap the current rank1 half; corrections never use unverified logits.
inline Result run_depth2(Backend&b,const Config&c,const std::string&forced){
 require(c.draft_rank==1&&(c.mode==2||c.mode==3),"depth71 native draft mode");
 Result out;out.start=clock_now();const int length=c.prompt.size();
 auto fixture=[&](int pos){return std::max(0,pos-length+2);};
 auto ordinary=[&](int rank,int token,int pos){return b.call(rank,half,token,pos,fixture(pos));};
 auto emit=[&](int token){require(token>=0&&token<c.vocab,"depth71 verified token bounds");out.tokens.push_back(token);out.rows.push_back({token,clock_now()});if(out.rows.size()==1)out.prompt_ms=(out.rows.back().stamp-out.start)*1000;return int(out.tokens.size())>=c.count||std::find(c.eos.begin(),c.eos.end(),token)!=c.eos.end();};
 bool done=false;
 for(int pos=0;pos<length;++pos){ordinary(0,c.prompt[pos],pos);b.call(0,accept);b.handover();
  if(c.mode==3&&pos)b.call(1,draft,c.prompt[pos],pos,0);
  auto result=ordinary(1,c.prompt[pos],pos);b.call(1,accept);
  if(pos+1==length)done=emit(result.token);
 }
 int pos=length;
 while(!done){double cycle=clock_now();int token=out.tokens.back();int d1=-1,d2=-1;
  bool pair=c.count-int(out.tokens.size())>=3;
  if(c.mode==3){b.start(1,16,token,pos,pair?1:0);ordinary(0,token,pos);b.call(0,accept);auto d=b.wait(1);d1=d.token;d2=d.reserved[0];}
  else {ordinary(0,token,pos);b.call(0,accept);size_t i=out.tokens.size();if(i<c.script.size())d1=c.script[i];if(i+1<c.script.size())d2=c.script[i+1];}
  pair=pair&&d1>=0&&d1<c.vocab&&d2>=0&&d2<c.vocab;
  if(pair&&forced=="first")d1=(d1+1)%c.vocab;
  if(pair&&forced=="second")d2=(d2+1)%c.vocab;
  b.handover();b.start(1,half,token,pos,fixture(pos));
  if(pair)b.start(0,14,d1,pos+1,fixture(pos+1),0,d2);
  auto first=b.wait(1);b.call(1,accept);done=emit(first.token);
  if(!pair){++pos;continue;}
  b.wait(0);++out.guesses_count;out.guess_sequence.push_back(d1);
  bool hit1=d1==first.token;out.guesses.push_back({pos+1,d1,first.token,hit1,(clock_now()-cycle)*1000});
  if(done||!hit1){b.call(0,15,0);if(!hit1)++out.misses;else ++out.hits;++pos;continue;}
  ++out.hits;
  // Commit only the confirmed draft input. Its hidden source is the target x.
  if(c.mode==3)b.call(1,draft,d1,pos+1,0);
  b.handover();auto pair_result=b.call(1,14,d1,pos+1,fixture(pos+1),0,d2);
  done=emit(pair_result.token);bool hit2=d2==pair_result.token;
  ++out.guesses_count;out.guess_sequence.push_back(d2);out.guesses.push_back({pos+2,d2,pair_result.token,hit2,(clock_now()-cycle)*1000});
  if(done||!hit2){b.call(1,15,1);b.call(0,15,1);if(hit2)++out.hits;else ++out.misses;pos+=2;continue;}
  ++out.hits;
  if(c.mode==3)b.call(1,17,d2,pos+2,0);
  b.call(1,15,2);b.call(0,15,2);done=emit(pair_result.reserved[0]);pos+=3;
 }
 if(c.dumps){b.call(0,dump,0,pos);b.call(1,dump,0,pos);}
 out.end=clock_now();b.call(1,0);return out;
}
}
