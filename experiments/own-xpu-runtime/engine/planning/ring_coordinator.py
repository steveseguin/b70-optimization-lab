"""Isolated CPU depth-two coordinator. Not imported by a live controller.

At most three global live rows, two completed tentative slots per early stage,
and one outstanding command per owner. Proposal callbacks model already-restored
canonical draft publications, not GPU timing or simultaneous queue submission.
"""
from dataclasses import dataclass, field
from hashlib import sha256

from ring_contract import Proposals, ProposalBatch, append_prefix, need

ROW, ACCEPT, ABORT_SUFFIX, RESET = 24, 25, 26, 11


@dataclass(frozen=True)
class Row:
    epoch: int
    identity: int
    parent: int
    position: int
    token: int
    fixture: int
    request: bytes
    before: bytes
    after: bytes


@dataclass(frozen=True)
class Publication:
    row: Row
    stage: int
    ticket: int
    data: bytes
    digest: bytes


@dataclass(frozen=True)
class ResetSpec:
    epoch: int
    request: bytes
    prompt: tuple
    max_new: int


@dataclass(frozen=True)
class Command:
    stage: int
    op: int
    sequence: int
    row: Row | None
    tentative: bool = False
    row_ticket: int = 0
    source: Publication | None = None
    reset: ResetSpec | None = None


@dataclass(frozen=True)
class Ack:
    epoch: int
    stage: int
    sequence: int
    row_id: int
    row_ticket: int
    physical: int
    committed: int
    pending: int
    discarded: tuple = ()
    stream: bytes | None = None
    token: int | None = None
    sticky_error: int = 0


@dataclass
class Work:
    row: Row
    verified: bool
    cancelled: bool = False
    streams: dict = field(default_factory=dict)
    accepted: set = field(default_factory=set)
    target_output: int | None = None


@dataclass
class Pending:
    command: Command


@dataclass
class Stage:
    physical: int = 0
    committed: int = 0
    sequence: int = 0
    busy: Command | None = None
    pending: list = field(default_factory=list)


class Coordinator:
    def __init__(self, *, stages, request, epoch, prompt, max_new, vocab, eos_token_ids,
                 proposal_callback=None, context=4096, initial_sequences=None, stream_bytes=16):
        need(type(stages)is int and stages>=2,'at least two stage owners')
        need(type(context)is int and context>=1,'context bound')
        need(type(max_new)is int and 1<=max_new<=512 and len(prompt)+max_new-1<=context,'request capacity')
        need(isinstance(eos_token_ids,(list,tuple)) and eos_token_ids and len(set(eos_token_ids))==len(eos_token_ids)
             and all(type(t)is int and 0<=t<vocab for t in eos_token_ids),'EOS set')
        self.stages=[Stage() for _ in range(stages)]
        if initial_sequences is not None:
            need(len(initial_sequences)==stages and all(type(s)is int and 0<=s<2**31-100000 for s in initial_sequences),'initial wire sequences')
            for stage,value in zip(self.stages,initial_sequences):stage.sequence=value
        need(type(stream_bytes)is int and 0<stream_bytes<=65536 and stream_bytes%4==0,'negotiated F32 stream extent')
        self.stream_bytes=stream_bytes
        self.context,self.vocab,self.eos=context,vocab,frozenset(eos_token_ids)
        self.proposal_callback=proposal_callback
        self.next_id=0;self.events=[];self.reset_pending=None;self.reset_acks=set();self.failed=None
        self._request(request,epoch,prompt,max_new)

    def _request(self,request,epoch,prompt,max_new):
        self.proposals=Proposals(request=request,epoch=epoch,prompt=prompt,vocab=self.vocab)
        self.request,self.epoch,self.prompt,self.max_new=request,epoch,tuple(prompt),max_new
        self.limit=len(prompt)+max_new-1
        self.frontier=0;self.rows={};self.emitted=[]
        self.phase=None;self.cut=None;self.stop_reason=None;self.done=False

    def _live_count(self):
        return sum(not w.cancelled and len(w.accepted)<len(self.stages) for w in self.rows.values())

    def _new_row(self,position,token,verified,proposal=None):
        need(position not in self.rows and self._live_count()<3 and position<self.frontier+3,'three global positions')
        parent=self.rows.get(position-1)
        need(position==0 or parent is not None,'global parent row exists')
        before=self.proposals.hashes[0] if position==0 else parent.row.after
        need(self.next_id<2**64-1,'bounded global row identity')
        self.next_id+=1
        row=Row(self.epoch,self.next_id,0 if parent is None else parent.row.identity,
                position,token,max(0,position-len(self.prompt)+2),self.request,before,append_prefix(before,position,token))
        if proposal is not None:
            self.proposals.issue(row.identity,row.parent,proposal)
        elif position==len(self.proposals.verified)-1 and self.proposals.seed_parent_row_id is None:
            self.proposals.register_verified_row(position,row.identity,row.after)
        self.rows[position]=Work(row,verified)
        self.events.append(dict(event='row-created',epoch=self.epoch,row=row.identity,parent=row.parent,position=position,token=token,verified=verified))
        return self.rows[position]

    def _ensure_known(self):
        end=min(self.limit,self.frontier+3,len(self.proposals.verified))
        if self.stop_reason is not None:end=min(end,self.cut)
        for position in range(self.frontier,end):
            if position not in self.rows:
                if self._live_count()>=3:break
                self._new_row(position,self.proposals.verified[position],True)

    def publish(self,batch):
        need(self.phase is None and not self.done and self.stop_reason is None,'proposal publication during drain/reset')
        stage=self.stages[0]
        need(stage.busy is None and all(p.command.tentative for p in stage.pending),'proposal borrower requires drained tentative owner')
        need(batch.seed_length>=2 and self.frontier>=batch.seed_length-1,'canonical true-pair parent not yet committed')
        self.proposals.publish(batch)
        self.events.append(dict(event='proposal',ticket=batch.ticket,seed=batch.seed_length,tokens=batch.tokens))

    def _poll_proposals(self):
        if self.proposal_callback is None or self.phase is not None or self.stop_reason is not None:return
        stage=self.stages[0]
        if stage.busy is not None or any(not p.command.tentative for p in stage.pending):return
        if self.proposals.seed_parent_row_id is None or len(self.proposals.verified)<2:return
        if self.frontier<len(self.proposals.verified)-1:return
        batches=self.proposal_callback(self)
        need(isinstance(batches,(tuple,list)) and len(batches)<=4,'bounded explicit proposal callback')
        for batch in batches:self.publish(batch)

    def _reserve(self,index,op,row=None,*,tentative=False,row_ticket=0,source=None,reset=None):
        stage=self.stages[index]
        need(stage.busy is None and stage.sequence<2**31-1,'one command per owner and bounded wire sequence')
        stage.sequence+=1
        command=Command(index,op,stage.sequence,row,tentative,row_ticket,source,reset)
        stage.busy=command
        self.events.append(dict(event='send',op=op,stage=index,sequence=command.sequence,row=None if row is None else row.identity,
                                position=None if row is None else row.position,phase=self.phase))
        return command

    def _accepts(self):
        result=[]
        for index in reversed(range(len(self.stages))):
            stage=self.stages[index]
            if stage.busy is not None or not stage.pending:continue
            pending=stage.pending[0].command;work=self.rows[pending.row.position]
            if not work.verified or work.cancelled:continue
            if self.cut is not None and pending.row.position>=self.cut:continue
            result.append(self._reserve(index,ACCEPT,pending.row,row_ticket=pending.sequence,tentative=pending.tentative))
        return result

    def _row_commands(self):
        result=[]
        for index in reversed(range(len(self.stages))):
            stage=self.stages[index];final=index==len(self.stages)-1
            if stage.busy is not None:continue
            capacity=1 if final else 2
            if len(stage.pending)>=capacity or any(not p.command.tentative for p in stage.pending):continue
            position=stage.physical
            if position>=self.limit or position>=self.frontier+3:continue
            if self.stop_reason is not None and position>=self.cut:continue
            work=self.rows.get(position)
            if work is None and index==0 and self.stop_reason is None and self._live_count()<3:
                parent=self.rows.get(position-1)
                if parent is not None:
                    proposal=self.proposals.choose(position,parent.row.after)
                    if proposal is not None:work=self._new_row(position,proposal.token,False,proposal)
            if work is None or work.cancelled:continue
            tentative=not work.verified
            if final and tentative:continue
            if stage.pending and not tentative:continue
            source=None if index==0 else work.streams.get(index-1)
            if index and source is None:continue
            if source is not None:
                need(source.row==work.row and source.stage==index-1 and source.digest==sha256(source.data).digest(),'immutable upstream publication identity')
            result.append(self._reserve(index,ROW,work.row,tentative=tentative,source=source))
        return result

    def _cancel_suffix(self,cut,reason):
        need(self.phase is None,'one rejection/drain generation at a time')
        self.cut=cut;self.phase='drain'
        if reason!='miss':self.stop_reason=reason
        for position,work in self.rows.items():
            if position>=cut:work.cancelled=True
        self.events.append(dict(event='freeze',cut=cut,reason=reason))

    def request_stop(self,reason='reset'):
        need(reason in ('reset','cancel') and not self.done and self.reset_pending is None,'explicit stop at live branch')
        if self.phase in ('drain','abort'):
            self.stop_reason=reason
            self.events.append(dict(event='stop-requested',cut=self.cut,reason=reason))
            return
        need(self.phase is None,'stop already draining verified prefix')
        # Verified ROWs have no checkpoint: finish already-issued known prefix
        # across all stages before aborting the tentative suffix. Admit no new
        # stage-zero rows beyond that frozen cutoff.
        issued_verified=[p.command.row.position for s in self.stages for p in s.pending if not p.command.tentative]
        issued_verified += [s.busy.row.position for s in self.stages if s.busy is not None and s.busy.op==ROW and not s.busy.tentative]
        cut=max([self.frontier]+[p+1 for p in issued_verified])
        self.stop_reason=reason;self.cut=cut;self.phase='stop-prefix'
        for pos,work in self.rows.items():
            if pos>=cut:work.cancelled=True
        self.events.append(dict(event='stop-requested',cut=cut,reason=reason))

    def _drain_commands(self):
        # Before issuing any suffix abort, every outstanding command must have
        # replied. Pending verified prefix acceptance then drains the same way.
        if any(s.busy is not None for s in self.stages):return []
        accepted=self._accepts()
        if accepted:return accepted
        need(all(not s.pending or s.pending[0].command.row.position>=self.cut for s in self.stages),'unresolved earlier prefix')
        result=[]
        for index,stage in enumerate(self.stages):
            if stage.pending:
                oldest=stage.pending[0].command
                need(all(p.command.tentative and p.command.row.position>=self.cut for p in stage.pending),'only tentative suffix can abort')
                result.append(self._reserve(index,ABORT_SUFFIX,oldest.row,row_ticket=oldest.sequence,tentative=oldest.tentative))
        if result:self.phase='abort';return result
        self._drained()
        return []

    def _drained(self):
        need(all(s.busy is None and not s.pending and s.physical==s.committed==self.cut for s in self.stages),'all-stage abort acknowledgments before corrected row')
        self.rows={p:w for p,w in self.rows.items() if p<self.cut}
        self.events.append(dict(event='drained',cut=self.cut,reason=self.stop_reason or 'miss'))
        if self.stop_reason is not None:
            self.proposals.issued.clear();self.proposals.batches.clear()
            self.done=True;self.phase=None
        else:self.phase=None;self.cut=None

    def commands(self):
        need(self.failed is None,'coordinator sticky failure forbids further work')
        if self.reset_pending is not None:
            return [self._reserve(i,RESET,reset=self.reset_pending) for i,s in enumerate(self.stages)
                    if s.busy is None and i not in self.reset_acks]
        if self.done:return []
        if self.phase=='abort':
            if any(s.busy is not None for s in self.stages):return []
            self._drained()
            return [] if self.done else self.commands()
        if self.phase=='drain':
            commands=self._drain_commands()
            return self.commands() if not commands and self.phase is None and not self.done else commands
        if self.phase=='stop-prefix' and self.frontier==self.cut:
            self.phase='drain';return self._drain_commands()
        self._ensure_known()
        result=self._accepts()
        self._poll_proposals()
        result+=self._row_commands()
        self.invariants()
        return result

    def complete(self,command,ack):
        need(isinstance(ack,Ack) and 0<=command.stage<len(self.stages),'typed reply')
        stage=self.stages[command.stage]
        need(stage.busy is command,'stale duplicate or wrong-stage completion')
        need(self.failed is None,'coordinator sticky failure forbids completion')
        if ack.sticky_error:
            self.failed='native sticky failure'
            raise ValueError(self.failed)
        epoch=command.reset.epoch if command.op==RESET else self.epoch
        row_id=0 if command.row is None else command.row.identity
        ticket=command.sequence if command.op==ROW else command.row_ticket
        need((ack.epoch,ack.stage,ack.sequence,ack.row_id,ack.row_ticket)==(epoch,command.stage,command.sequence,row_id,ticket),'reply epoch/row/wire identity')
        if command.op==RESET:
            need((ack.physical,ack.committed,ack.pending)==(0,0,0) and not ack.discarded and ack.stream is None and ack.token is None,'cold reset acknowledgment')
            self.events.append(dict(event='reply',op=command.op,stage=command.stage,sequence=command.sequence,row=0))
            stage.busy=None;stage.physical=stage.committed=0;self.reset_acks.add(command.stage)
            if len(self.reset_acks)==len(self.stages):
                spec=self.reset_pending;self.reset_pending=None;self.reset_acks=set()
                self._request(spec.request,spec.epoch,spec.prompt,spec.max_new)
            return
        work=self.rows[command.row.position]
        need(work.row==command.row,'immutable row lineage')
        if command.op==ROW:
            need((ack.physical,ack.committed,ack.pending)==(stage.physical+1,stage.committed,len(stage.pending)+1) and not ack.discarded,'ROW physical/logical acknowledgment')
            final=command.stage==len(self.stages)-1
            if final:
                need(work.verified and not command.tentative and ack.stream is None,'final verified-only ownership')
                need((type(ack.token)is int and 0<=ack.token<self.vocab) if command.row.fixture else ack.token is None,'final output token')
            else:need(isinstance(ack.stream,(bytes,bytearray)) and len(ack.stream)==self.stream_bytes and ack.token is None,'complete owned F32 stream')
            stage.physical+=1;stage.pending.append(Pending(command))
            if final:work.target_output=ack.token
            else:
                data=bytes(ack.stream)
                work.streams[command.stage]=Publication(work.row,command.stage,command.sequence,data,sha256(data).digest())
        elif command.op==ACCEPT:
            need(stage.pending and stage.pending[0].command.sequence==command.row_ticket and work.verified and not work.cancelled,'oldest verified ACCEPT only')
            need((ack.physical,ack.committed,ack.pending)==(stage.physical,stage.committed+1,len(stage.pending)-1) and not ack.discarded and ack.stream is None and ack.token is None,'ACCEPT must never rewind physical state')
            stage.pending.pop(0);stage.committed+=1;work.accepted.add(command.stage)
            if command.stage==len(self.stages)-1:self._verified(work,command.sequence)
            # Every downstream ROW has completed before all owners can ACCEPT.
            # Keep lineage metadata, but never retain the request's old tensors.
            if len(work.accepted)==len(self.stages):work.streams.clear()
        elif command.op==ABORT_SUFFIX:
            expected=tuple(p.command.row.identity for p in stage.pending)
            need(self.phase=='abort' and expected and expected[0]==row_id and stage.pending[0].command.sequence==command.row_ticket,'exact oldest suffix abort')
            need((ack.physical,ack.committed,ack.pending)==(stage.committed,stage.committed,0) and ack.discarded==expected and ack.stream is None and ack.token is None,'complete suffix restoration acknowledgment')
            stage.pending.clear();stage.physical=stage.committed
            for row in self.rows.values():row.streams.pop(command.stage,None) if row.cancelled else None
            self.events.append(dict(event='abort-ack',stage=command.stage,discarded=expected,cut=self.cut))
        else:raise ValueError('unknown ring command')
        self.events.append(dict(event='reply',op=command.op,stage=command.stage,sequence=command.sequence,row=row_id))
        stage.busy=None
        self.invariants()

    def _verified(self,work,commit_ticket):
        need(work.row.position==self.frontier,'final acceptance in prefix order')
        self.frontier+=1
        if self.stop_reason in ('reset','cancel'):return
        if not work.row.fixture:return
        token=work.target_output;self.emitted.append(token)
        self.events.append(dict(event='verified-output',position=work.row.position,token=token,row=work.row.identity))
        if len(self.emitted)==self.max_new or token in self.eos:
            self._cancel_suffix(self.frontier,'eos' if token in self.eos else 'cap')
            return
        verdict=self.proposals.verify(token,commit_ticket=commit_ticket)
        existing=self.rows.get(verdict['position'])
        if verdict['discard_row_ids']:
            self._cancel_suffix(verdict['position'],'miss')
        elif existing:
            need(existing.row.token==token,'matching issued row is immutable')
            existing.verified=True

    def reset(self,*,request,epoch,prompt,max_new):
        need(self.failed is None,'reset cannot erase coordinator sticky failure')
        need(self.done and self.reset_pending is None and epoch==self.epoch+1,'reset only at drained request epoch boundary')
        need(all(s.busy is None and not s.pending and s.physical==s.committed for s in self.stages),'cold reset cannot hide pending suffix')
        need(isinstance(request,bytes) and len(request)==32 and prompt and all(type(t)is int and 0<=t<self.vocab for t in prompt)
             and type(max_new)is int and 1<=max_new<=512 and len(prompt)+max_new-1<=self.context,'new request bounds')
        self.reset_pending=ResetSpec(epoch,request,tuple(prompt),max_new)

    def invariants(self):
        need(self._live_count()<=3,'bounded global live rows')
        for index,stage in enumerate(self.stages):
            need(stage.physical==stage.committed+len(stage.pending),'physical/logical pending extent')
            need(len(stage.pending)<=(1 if index==len(self.stages)-1 else 2),'bounded stage slots')
            for offset,pending in enumerate(stage.pending):
                need(pending.command.row.position==stage.committed+offset,'contiguous unresolved stage suffix')
                if index==len(self.stages)-1:need(not pending.command.tentative,'final stage cannot speculate')
