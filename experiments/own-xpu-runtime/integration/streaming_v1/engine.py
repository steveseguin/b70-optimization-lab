"""Pinned checkpoint engine with token-time observation, preserving disposition.

Observers are trusted bounded callbacks (local decode/put_nowait or explicitly
bounded nonblocking sends), never blocking I/O. Their first exception disables
observation but does not interrupt the
native reader or skip SAVE/RELEASE. This is not an async callback scheduler.
"""
from __future__ import annotations
import copy
import hashlib
from pathlib import Path
import checkpoint_engine as parent

PARENT=Path(__file__).resolve().parents[1]/'checkpoint_engine.py'
PARENT_SHA='5bee78743a8c98c3dd24af0703de429cf0e1ede0b0fb9a772bb3c624be581295'

def verify_parent():
    parent.require(Path(parent.__file__).resolve()==PARENT and
                   hashlib.sha256(PARENT.read_bytes()).hexdigest()==PARENT_SHA,
                   'streaming engine requires exact canonical checkpoint engine')

class _Observation:
    def __init__(self,callback,maximum):
        self.callback,self.maximum=callback,maximum
        self.tokens=[];self.delivered=0;self.error=None;self.overflow=False

    def emit(self,token):
        # NativeFront has already validated this token and its sequence index.
        if len(self.tokens)>=self.maximum:
            self.overflow=True;return
        self.tokens.append(token)
        if self.callback is not None and self.error is None:
            try:self.callback(token)
            except BaseException as error:self.error=error
            else:self.delivered+=1

    def receipt(self):
        row=dict(enabled=self.callback is not None,observed_tokens=len(self.tokens),
                 callback_calls_completed=self.delivered,observer_failed=self.error is not None)
        if self.error is not None:
            try:message=str(self.error)[:2048]
            except BaseException:message='<exception message unavailable>'
            row['error']=dict(type=type(self.error).__name__,message=message)
        return row

class StreamingCheckpointEngine(parent.CheckpointEngine):
    """Same canonical front/store objects; no wrapping or new native methods.

run_turn returns an `observation` receipt only after normal policy disposition.
    The caller must not publish successful streamed completion if observer_failed.
last_observer_error retains the original object. Native/storage/policy failures
keep canonical halt/retention semantics; an observer cannot authorize a retry.
"""
    def __init__(self,*args,**kwargs):
        verify_parent();super().__init__(*args,**kwargs)
        self._observation=None

    @property
    def last_observer_error(self):
        return self._observation.error if self._observation is not None else None

    def generate(self,tokens,max_new,*,request_id,on_token=None):
        # Narrow copy+delta of the pinned parent: only optional observation.
        with self._operation_guard():
            parent.require(on_token is None or callable(on_token),'token observer must be callable')
            parent.valid_id(request_id)
            request=self._tokens(tokens)
            parent.require(type(max_new) is int and 1<=max_new<=512 and len(request)+max_new<=self.context,
                           'generation cap/context admission failed')
            parent.require(self.front.state=='ready' and self._visible is None,'pending reply must be disposed before RUN')
            checkpoint=None
            if self._append is not None:
                plan=self._append
                parent.require(plan.tokens==request,'RUN tokens differ from pending append plan')
                found=self._snapshot(plan.checkpoint_id)
                parent.require(found is not None and found[0].manifest_sha256==plan.manifest_sha256,
                               'pending append checkpoint changed or disappeared')
                found[0].plan_append(request,max_new=max_new)
                checkpoint=plan.checkpoint_id
            self._append=None
            observation=_Observation(on_token,max_new);self._observation=observation
            kwargs=dict(restore=checkpoint)
            if on_token is not None:kwargs['on_token']=observation.emit
            response=self.front.request(request_id,list(request),max_new,**kwargs)
            generated=self._tokens(response['tokens'])
            parent.require(len(generated)<=max_new,'native response exceeds cap')
            if on_token is not None:
                parent.require(not observation.overflow and observation.tokens==list(generated),
                               'observed token frames differ from native completion')
            self._visible,self._request_id=request+generated,request_id
            self._pending()
            parent.require(self.front.pending['visible_tokens']==len(self._visible) and
                           self.front.pending['pending_token']==generated[-1],'native pending descriptor differs')
            return response

    def run_turn(self,parking,session,messages,*,request_id,max_new,on_token=None):
        with self._operation_guard():
            parent.require(parking.engine is self,'parking policy belongs to another engine')
            parent.require(self._append is None,'unconsumed explicit restore plan before run_turn')
            parent.require(self.front.state=='ready' and self._visible is None,
                           'previous pending reply must be disposed before policy lookup')
            view=copy.deepcopy(messages)
            decision=parking.before_request(session,view)
            tokens=parking.prefix(view)
            if decision.action=='restore':self.restore(decision.checkpoint_id,tokens)
            else:parent.require(decision.action=='prefill','unknown parking decision')
            response=self.generate(tokens,max_new,request_id=request_id,on_token=on_token)
            parked=parking.park(session,view,response['tokens'])
            disposition=None
            if self._visible is not None:disposition=self.release()
            parent.require(self.front.state in ('ready','draining') and self.front.pending is None,
                           'turn finished without disposition')
            return dict(response=response,decision=decision,parked=parked,release=disposition,
                        observation=self._observation.receipt())
