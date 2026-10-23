"""Streaming successor to the pinned serial lifecycle; no owner startup.

RunAdmission is the unchanged canonical class. Construct the streaming engine
with admission.front, then the streaming service and this lifecycle. Only this
version's exact StreamingServer is accepted. Physical drain, store guards and
launch provenance remain the external coordinator's responsibility.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import threading

import session_lifecycle as parent
from chat_service import ChatRequestError
from streaming_v1 import http as H, service as S

HERE = Path(__file__).resolve().parent
PINS = (
    (parent, HERE.parent/'session_lifecycle.py', '0956d849c5a529eeed0afb285c4983d1992ab509a1a3871c9b5029265f8e2c24'),
    (H, HERE/'http.py', 'e163f24fa87460362408f9a474a8e68480403c73487b57ea7d82365c46226dcb'),
    (S, HERE/'service.py', 'd03511e9fa83345f3369d071ae2a4f4a496c4e4add3306b8f6291af8dfccc632'),
)
RunAdmission = parent.RunAdmission
LifecycleError = parent.LifecycleError
IntakeClosed = parent.IntakeClosed


def verify_dependencies():
    for module, path, digest in PINS:
        parent.require(Path(module.__file__).resolve() == path and
                       hashlib.sha256(path.read_bytes()).hexdigest() == digest,
                       'streaming lifecycle dependency changed')


class _StreamingServiceProxy:
    def __init__(self, lifecycle):
        self._lifecycle = lifecycle

    def __getattr__(self, name):
        return getattr(self._lifecycle._service, name)

    def complete(self, *args, **kwargs):
        return self._invoke('complete', args, kwargs)

    def stream(self, *args, **kwargs):
        return self._invoke('stream', args, kwargs)

    def _invoke(self, method, args, kwargs):
        # Same boundary/error gates as the pinned _ServiceProxy.complete;
        # streaming adds only explicit method dispatch, never a front bypass.
        life = self._lifecycle
        entered = False
        try:
            parent.require(life._thread == threading.get_ident() and life._in_handler,
                           'service outside lifecycle handler')
            reason = life._boundary_reason()
            if reason is not None:
                life._normal_reason = reason
                raise IntakeClosed('chat intake closed')
            entered = life._in_service = True
            result = getattr(life._service, method)(*args, **kwargs)
            # Preserve serialization errors before HTTP replaces them with a
            # generic failure. A disposed observer-failed result is still normal.
            json.dumps(result, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8')
            return result
        except IntakeClosed:
            raise
        except BaseException as error:
            if not (isinstance(error, ChatRequestError) and life._service.halted_reason is None):
                life.admission._fail(error)
            raise
        finally:
            if entered:
                life._in_service = False


class StreamingSessionLifecycle(parent.SessionLifecycle):
    """Single-use, one serial handler and one normal close, including SSE.

request_close only latches. An admitted stream finishes native disposition and
its bounded delivery phase before any normal close. Delivery failure alone is
not a native incident. Runtime/decode/admission errors retain the original error
and never trigger a normal close, retry, signal or owner replacement.
"""
    def __init__(self, service, admission, *, poll_seconds=.1, close_timeout=120):
        verify_dependencies()
        parent.require(type(service) is S.StreamingChatService,
                       'exact streaming chat service required')
        parent.require(type(admission) is RunAdmission, 'exact canonical RunAdmission required')
        super().__init__(service, admission, poll_seconds=poll_seconds, close_timeout=close_timeout)
        self.service = _StreamingServiceProxy(self)

    def serve(self, server):
        # Narrow copy of the pinned parent: exact streaming server gate/scope
        # plus non-masking cleanup diagnostics. Close ordering is unchanged.
        parent.require(not self._used, 'lifecycle is single use')
        parent.require(type(server) is H.StreamingServer and server.service is self.service,
                       'exact serial streaming HTTP server attached to lifecycle service required')
        self._used = True
        self._thread = threading.get_ident()
        self.state = 'serving'
        try:
            server.timeout = self.poll_seconds
            while True:
                reason = self._boundary_reason()
                if reason is not None:
                    break
                self._in_handler = True
                try:
                    server.handle_request()
                finally:
                    self._in_handler = False
                if self.admission.failure is not None:
                    raise self.admission.failure
                parent.require(not server.intake_halted or self._normal_reason is not None,
                               'HTTP intake halted without a captured service error')
            self.state = 'closing'
            server.intake_halted = True
            server.server_close()
            parent.require(not self._in_service and self.admission._raw.pending is None,
                           'normal close requires completed disposition')
            self.admission.guard()
            self._close_called = True
            stopped = self.admission._raw.close(timeout=self.close_timeout)
            expected = dict(event='stopped', safe_to_exit=True,
                completed_requests=self.admission._raw.completed,
                completed_controls=self.admission._raw.completed_controls,
                discarded_pending=False, pending_request_id='')
            parent.require(all(type(stopped.get(k)) is type(v) and stopped[k] == v for k, v in expected.items()) and
                           stopped.get('reason') in ('quit','eof','request-limit','idle-timeout','deadline','signal') and
                           self.admission._raw.process.poll() == 0, 'native clean shutdown proof mismatch')
            self.admission.guard()
            self.state = 'closed'
            return dict(passed=True, reason=reason, native_stopped=stopped,
                        completed_requests=stopped['completed_requests'], close_calls=1,
                        scope='attached streaming owner lifecycle; physical drain remains outer-coordinator responsibility')
        except BaseException as error:
            self.admission._fail(error)
            primary = self.admission.failure
            self.state = 'incident'
            server.intake_halted = True
            try:
                server.server_close()
            except BaseException as cleanup_error:
                try:
                    primary.add_note('listener cleanup failed: ' + S.error_view(cleanup_error)['message'][:1024])
                except BaseException:
                    pass  # Even an unusual exception formatter cannot replace primary.
            raise primary
        finally:
            self._in_handler = self._in_service = False
            self._thread = None
