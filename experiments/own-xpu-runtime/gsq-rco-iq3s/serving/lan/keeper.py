"""ctxkeeper's long-context policy inside the SC117 LAN service (opt-in: SC117_KEEPER=1).

Requests for the model id `<MODEL_ID>-keeper` go through ctxkeeper's Keeper, loaded as a library from SC117_KEEPER_LIB
(default: the ctxkeeper copy next to serving/ in a lab, else the repo's tools/ctxkeeper). The model sees a bounded view,
[system + memory note][first user][NOTES][recent turns]; cut turns go verbatim to an archive under SC117_KEEPER_DIR, the
model writes its NOTES in place, the RULES are repeated after a user message, and `recall` searches are answered here
and never reach the client. Every model call the keeper makes runs in this process (CHAT.parse -> Engine.generate ->
CHAT.completion) under the engine lock the HTTP handler holds, so they are serial. The plain model id is untouched.

Engine checkpoints carry the cost, all through Engine.generate's continuation and parked sessions:
  HEAD    Per conversation, the engine state after the opening messages (the system block with the tools, `recall` and
          the memory note; the first user message) is parked once and pinned in the session store. A split read makes
          it: the head with one output token, park (the token must be the view's next one, <|im_start|>), then the
          request continues from there as an ordinary continuation. After a cut, [head][NOTES'][recent] restores the
          head and reads only NOTES' and the recent turns.
  NOTES   In-place notes run right after the reply that makes them due (ctxkeeper's notes_async="wait" job), before
          the engine lock is released, as an exact extension of the live state: the request just answered, its reply,
          then ctxkeeper's notes request with one sentence added (that reply stays in view). The next request applies
          them under ctxkeeper's freshness rules. When the live state cannot be extended that way (the reply followed
          archive searches), the notes wait for the next reply that allows it; the ordinary cut still runs when the
          window fills.
  RECALL  Each search round extends the round before it (the ordinary continuation).
Faults: any exception from the engine halts the service as it would for a client request. KeeperHalt is a
BaseException, so ctxkeeper's `except Exception` around its notes calls cannot absorb it.
"""
import collections, copy, importlib.util, json, os, re, shutil, threading, time
from pathlib import Path

P = Path(__file__).resolve().parent
REPO_LIB = Path('/home/steve/llm-optimizations/tools/ctxkeeper')


def library_path():
    if os.environ.get('SC117_KEEPER_LIB'):
        return Path(os.environ['SC117_KEEPER_LIB'])
    lab = P.parents[1] / 'ctxkeeper'                  # a lab copy keeps ctxkeeper/ next to serving/
    return lab if (lab / 'ctxkeeper.py').is_file() else REPO_LIB


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


LIB = library_path()
ck = _load(LIB / 'ctxkeeper.py', 'sc117_ctxkeeper')

SUFFIX = '-keeper'
DIR = Path(os.environ.get('SC117_KEEPER_DIR', '/dev/shm/sc117-keeper'))
INPLACE_TOKENS = int(os.environ.get('SC117_KEEPER_INPLACE_TOKENS', '15000'))   # ctxkeeper's qwen recipe
RESERVE = int(os.environ.get('SC117_KEEPER_RESERVE', '512'))       # tokens kept free beside the client's max_tokens
PINS = int(os.environ.get('SC117_KEEPER_PINS', '4'))               # head checkpoints pinned at once (newest conversations)
MAX_RECALLS = int(os.environ.get('SC117_KEEPER_MAX_RECALLS', '16'))
MAX_BYTES = int(float(os.environ.get('SC117_KEEPER_MAX_GB', '2')) * 1024**3)   # cap of the state directory (text only)
KEEPALIVE_SECONDS = 10.0
OVERFLOW_TRIES = 3            # cuts tried when a view plus the client's reply does not fit the context
NOTES_MIN_NEW = 256           # a notes call with less room fails (ctxkeeper then leaves the turns to the ordinary cut)
# The notes request extends the live state, so the reply just given stands above it; the one sentence that says so.
TAIL_NOTE = (' One exception: your own last reply above, just before this message, stays in view and is not among those '
             'turns, so leave it out now.')
LAYOUT_MARK = ' Use exactly this layout;'
# Messages the keeper shows for one call only (a later request's history does not hold them).
INJECTED = ('[[RULES in force', '[[Message from the context keeper', '[[You have made the same tool call',
            '[[That was the last archive search', '[[There is no room left', '[[A check of your last reply')
for _text, _prefix in ((ck.RECITE_HEAD, 0), (ck.INPLACE_REQUEST, 1), (ck.CARRY_HEAD, 1), (ck.CARRY_OPEN_HEAD, 1),
                       (ck.REPEAT_NOTE, 2), (ck.RECALL_LIMIT_NOTE, 3), (ck.RECALL_ROOM_NOTE, 4), (ck.SUM_NOTE, 5),
                       (ck.BARE_NOTE, 5)):
    if not _text.startswith(INJECTED[_prefix]):
        raise RuntimeError('ctxkeeper library wording differs from what keeper.py recognises: ' + _text[:40])
if LAYOUT_MARK not in ck.INPLACE_REQUEST:
    raise RuntimeError('ctxkeeper INPLACE_REQUEST layout sentence not found')
STATE_KEYS = ('cut', 'cuts', 'inplace_cuts', 'inplace_failed', 'notes_failed', 'recalls', 'requests', 'restarts',
              'async_applied', 'async_discarded', 'sc117_notes_deferred', 'largest_turn', 'ratio')


class KeeperHalt(BaseException):
    """An engine fault inside a keeper call. state.fault() has already been called (the service halts); this unwinds
    through ctxkeeper, whose `except Exception` around notes calls must not turn it into a failed note."""


class ViewOverflow(Exception):
    """The view plus the client's max_tokens is over the context: the keeper cuts the view further (never the reply)."""

    def __init__(self, over, prompt_tokens):
        super().__init__(f'view of {prompt_tokens} tokens plus the reply is {over} tokens over the context')
        self.over, self.prompt_tokens = over, prompt_tokens


class RequestTooLarge(ValueError):
    """No view of this conversation leaves room for the reply the client asked for (HTTP 400, nothing truncated)."""


def keeper_note(m):
    c = m.get('content')
    return m.get('role') == 'user' and isinstance(c, str) and c.startswith(INJECTED)


def recall_call(m):
    return m.get('role') == 'assistant' and any(isinstance(c, dict) and (c.get('function') or {}).get('name') == 'recall'
                                                for c in m.get('tool_calls') or [])


def recital(m):
    return keeper_note(m) and m['content'].startswith(ck.RECITE_HEAD)


def extendable(messages):
    """True when a later request's view can continue this prompt: no archive search and no keeper notice other than
    the RULES recital (which stays in later views, see KeeperService.with_recitals); the others are shown for one call
    and are not in the next request's history."""
    return not any(recall_call(m) or (keeper_note(m) and not recital(m)) for m in messages)


class ServiceKeeper(ck.Keeper):
    """ctxkeeper's Keeper with the model in process. The overrides only schedule and shape calls for the engine's
    continuation; the view, notes, checks, archive and recall are ctxkeeper's. One visible difference: the RULES
    recital after a user message stays in view after that request (where the model read it), instead of being shown
    once, so that the next request extends the live state."""

    def __init__(self, service, ask, state_dir, **settings):
        self.service = service
        super().__init__(ask, state_dir, **settings)

    def upstream(self, body, s=None, kind='main'):
        if kind == 'notes' and 'tools' not in body and s is not None and s.__dict__.get('sc117_tools'):
            # ctxkeeper's full-rewrite notes call has no tools; with the conversation's own (and none to be called, as
            # its in-place call does) its system block is the head checkpoint's, which it then restores
            body = dict(body, tools=s.sc117_tools, tool_choice='none')
        ctx = self.service.ctx
        saved = getattr(ctx, 'call', None)
        ctx.call = (s, kind)
        try:
            return super().upstream(body, s, kind)
        finally:
            ctx.call = saved

    def keep(self, s, model, messages, body=None):
        s.sc117_history = messages                   # this request's client history, as ctxkeeper processed it
        s.sc117_tools = list((body or {}).get('tools') or []) + [self.recall_tool]   # the main calls' tool list
        return super().keep(s, model, messages, body)

    def view(self, s, messages):
        return self.service.with_recitals(s, messages, super().view(s, messages), len(messages))

    def inplace_request(self, s, messages, h, noted, client):
        req, tools = super().inplace_request(s, messages, h, noted, client)
        if self.ask_notes is None:
            req = self.service.with_recitals(s, messages, req[:-1], h + s.state['cut'] + len(noted)) + req[-1:]
        live = self.service.extension(s, req)
        if live is None:
            s.log_event({'event': 'sc117: notes request is not an extension of the live state; read from the head'})
            return req, tools
        return live, tools

    def async_start(self, s, model, history, client):
        if s.pending is None and not self.service.live_ok(s):
            if self.inplace_plan(s, history, ck.head_length(history)):
                s.state['sc117_notes_deferred'] = s.state.get('sc117_notes_deferred', 0) + 1
                s.log_event({'event': 'sc117: in-place notes wait for a reply that the notes request can extend'})
            return
        super().async_start(s, model, history, client)

    def keep_inplace(self, s, model, messages, h, client):
        # In-place notes run only right after a reply (async_start), where they extend the live state. The ordinary
        # cut still runs at the start of a request when the window has filled.
        return False


def sse(resp, include_usage):
    """A finished keeper response as server-sent events: role (and thinking), content, tool calls, finish, usage."""
    base = {'id': resp.get('id'), 'object': 'chat.completion.chunk', 'created': resp.get('created'), 'model': resp.get('model')}
    choice = resp['choices'][0]
    msg = choice['message']
    out = []

    def chunk(delta, finish=None, **extra):
        out.append(b'data: ' + json.dumps(dict(base, choices=[{'index': 0, 'delta': delta, 'finish_reason': finish}], **extra)).encode() + b'\n\n')
    first = {'role': 'assistant'}
    if msg.get('reasoning_content'):
        first['reasoning_content'] = msg['reasoning_content']
    chunk(first)
    if msg.get('content'):
        chunk({'content': msg['content']})
    if msg.get('tool_calls'):
        chunk({'tool_calls': [dict(c, index=i) for i, c in enumerate(msg['tool_calls'])]})
    chunk({}, choice['finish_reason'], ownrt=(resp.get('ownrt') or {}).get('keeper'))
    if include_usage:
        out.append(b'data: ' + json.dumps(dict(base, choices=[], usage=resp['usage'])).encode() + b'\n\n')
    out.append(b'data: [DONE]\n\n')
    return out


class KeeperService:
    """The keeper model of the LAN service: ctxkeeper policy, in-process engine calls, head checkpoints."""

    Halt, TooLarge, KEEPALIVE_SECONDS, sse = KeeperHalt, RequestTooLarge, KEEPALIVE_SECONDS, staticmethod(sse)

    def __init__(self, engine, chat_module, chat, state, root=DIR, context=None, floors=(), meminfo=None, mem_floor=0,
                 ram=False, reserve=RESERVE, pins=PINS, max_bytes=MAX_BYTES, min_free=1024**3, **policy):
        self.engine, self.C, self.chat, self.state = engine, chat_module, chat, state
        self.context = context or chat_module.CONTEXT
        self.model_id = chat_module.MODEL_ID + SUFFIX
        self.root = Path(root)
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        st = self.root.stat()
        if st.st_uid != os.getuid() or st.st_mode & 0o077:
            raise RuntimeError(f'keeper directory {self.root} must be private and owned')
        self.floors, self.meminfo, self.mem_floor, self.ram = list(floors), meminfo, mem_floor, ram
        self.reserve, self.max_pins, self.max_bytes, self.min_free = reserve, pins, max_bytes, min_free
        self.ctx = threading.local()
        self.pins = collections.OrderedDict()           # pinned head ids, least recently used first
        self.calls_lock = threading.Lock()
        # ctxkeeper's qwen recipe (thinking off for notes, reasoning_effort medium on every call so the system block is
        # the same with thinking on or off), with the window of this engine: the context is the budget and the client's
        # max_tokens (plus a reserve) the reply reserve, set per request; inplace_fit because that leaves about 24K.
        settings = dict(budget=self.context, reply_reserve=reserve + chat_module.DEFAULT_MAX_TOKENS, headroom=1024,
                        target_ratio=0.6, notes_mode='inplace', inplace_tokens=INPLACE_TOKENS, inplace_fit=True,
                        notes_thinking=False, effort='medium', max_recalls=MAX_RECALLS, notes_async='wait')
        settings.update(policy)
        self.keeper = ServiceKeeper(self, self.ask, self.root, **settings)
        checks = getattr(engine, 'storage_checks', None)
        if checks is not None:
            checks.append(self.storage_ok)

    # ---------------------------------------------------------------- one client request
    def serve(self, body, header=None):
        """One request for the keeper model; the caller holds the engine lock. Returns (response, ctxkeeper session).
        A notes job that the reply made due may still be running on its own thread (post_reply)."""
        self.alive(True)
        requested = self.C.requested_tokens(body) or self.C.DEFAULT_MAX_TOKENS
        if requested + self.reserve >= self.context:
            raise RequestTooLarge(f'max_tokens {requested} leaves no room for a view in the {self.context}-token context')
        s = self.keeper.session(body, header)
        job = s.pending
        if job is not None and job.get('thread') is not None and job['thread'].is_alive():
            job['thread'].join()                       # the last reply's notes (the HTTP path has waited for them already)
        with self.calls_lock:
            before = s.__dict__.get('sc117_post') or []
            s.sc117_post, s.sc117_calls = [], []
        began, squeeze = time.monotonic(), 0
        for _ in range(OVERFLOW_TRIES):
            self.keeper.reply_reserve = requested + self.reserve + squeeze
            try:
                resp = self.keeper.complete(body, header)
                break
            except ViewOverflow as over:
                squeeze += over.over + 256
                s.log_event({'event': 'sc117: view and reply over the context; cutting further', 'over': over.over,
                             'prompt_tokens': over.prompt_tokens})
        else:
            raise RequestTooLarge(f'no view of this conversation leaves room for max_tokens={requested} in the '
                                  f'{self.context}-token context: the newest messages alone are too large')
        with self.calls_lock:
            calls, s.sc117_calls = s.sc117_calls, []
        resp['ownrt'] = dict(resp.get('ownrt') or {}, keeper=dict(
            session=s.dir.name, calls=calls, previous_post_reply=before, notes_due=s.pending is not None,
            head=s.__dict__.get('sc117_head'), state={k: s.state.get(k) for k in STATE_KEYS},
            wall_s=round(time.monotonic() - began, 3)))
        return resp, s

    def post_reply(self):
        """The thread of a notes job started by the last reply, if it is still running."""
        for s in list(self.keeper.sessions.values()):
            job = s.pending
            if job is not None and job.get('thread') is not None and job['thread'].is_alive():
                return job['thread']
        return None

    @staticmethod
    def finish_post_reply(thread, lock):
        """Hold the engine lock (taken over from the handler) until the notes job is done: no other request can RESET
        between the reply and its notes call."""
        try:
            thread.join()
        finally:
            lock.release()

    # ---------------------------------------------------------------- the in-process model
    def ask(self, body):
        """ctxkeeper's upstream call, made on the engine."""
        s, kind = getattr(self.ctx, 'call', None) or (None, 'main')
        main = kind == 'main'
        self.alive(main)
        requested = self.C.requested_tokens(body) or self.C.DEFAULT_MAX_TOKENS
        try:
            req = self.C.parse(body, self.chat)
        except self.C.RequestError as error:
            m = re.match(r'prompt is (\d+) tokens', str(error))
            if m and main:
                self.overflow(s, body, int(m.group(1)), requested)
            raise
        prompt = req['prompt_ids']
        room = self.context - len(prompt)
        if main:
            if requested > room:                       # never shorten the client's reply: the view is cut instead
                self.overflow(s, body, len(prompt), requested)
            max_new = requested
        else:
            max_new = min(requested, room)
            if max_new < min(NOTES_MIN_NEW, requested):
                raise ValueError(f'no room in the context for a {kind} reply ({room} tokens left)')
        reuse = req['reuse']                           # sc117_reuse=false: this call reads its prompt fresh (diagnostics)
        head = self.ensure_head(s, body, prompt) if reuse else None
        tokens, summary = self.generate(prompt, max_new, f'keeper-{kind}', main and extendable(body['messages']), reuse)
        full = self.C.completion(req, tokens, summary, self.chat)
        full['model'] = self.model_id
        message = full['choices'][0]['message']
        if recall_call(message):
            self.engine.convo_parkable = False         # an archive search is never in a later request's history
        self.record(s, kind, summary, head)
        if main and s is not None:
            self.note_recital(s, body['messages'])
            s.sc117_live = dict(messages=copy.deepcopy(body['messages']), reply=copy.deepcopy(message),
                                count=self.engine.count)
        return full

    def overflow(self, s, body, prompt_tokens, requested):
        """The exact count replaces ctxkeeper's size estimate (characters per token) before serve() cuts again."""
        if s is not None:
            s.state['ratio'] = round(min(max(ck.chars_of(body['messages']) / prompt_tokens, 2.5), 6.0), 4)
        raise ViewOverflow(prompt_tokens + requested - self.context, prompt_tokens)

    def alive(self, main):
        phase = self.state.phase
        if phase == 'halted':
            raise KeeperHalt('service halted: ' + str(getattr(self.state, 'detail', '')))
        if not main and phase != 'ready':
            raise ValueError(f'service {phase}: no keeper notes now')

    def generate(self, prompt, max_new, label, parkable, reuse=True):
        try:
            out = self.engine.generate(prompt, max_new, label, continue_ok=reuse, parkable=parkable)
        except BaseException as error:                 # exactly the client path: any engine exception halts
            self.state.fault(error)
            raise KeeperHalt(repr(error)) from error
        if self.state.phase == 'halted':
            raise KeeperHalt('service halted during a keeper call')
        return out

    # ---------------------------------------------------------------- head checkpoint
    def ensure_head(self, s, body, prompt):
        """Before a call that does not continue the live state: make sure this conversation's head is parked and pinned
        (split read on first need). Returns what happened, for the request summary, or None."""
        eng = self.engine
        store = getattr(eng, 'sessions', None)
        if s is None or store is None or not getattr(eng, 'continuation', False) or eng.continuation_start(prompt, 'mtp'):
            return None
        h = ck.head_length(body['messages'])
        if not h:
            return None
        try:
            head = self.C.prefix_ids(body, self.chat, h)
        except Exception:
            return None
        n = len(head)
        if n < store.min_tokens or n > store.max_tokens or len(prompt) < n + 2 or prompt[:n] != head:
            return None
        sid = store.ops.session_id(head)
        info = dict(id=sid, tokens=n)
        self.use_head(s, sid)
        if sid in store.index:
            self.pin(sid)
            return dict(info, event='pinned')
        if s.__dict__.get('sc117_head_refused') == sid:
            return dict(info, event='unavailable')
        best = store.match(prompt, eng.session_identity)
        if best is not None and len(best['tokens']) >= n:   # a longer parked state serves this prompt; the head waits
            return dict(info, event='deferred', restore=len(best['tokens']))
        tokens, summary = self.generate(head, 1, 'keeper-head', False)
        self.record(s, 'head', summary, None)
        if tokens[0] != prompt[n]:
            s.sc117_head_refused = sid                 # the next request reads this head again from the start
            return dict(info, event='next-token-differs', predicted=tokens[0], wanted=prompt[n])
        try:
            parked = store.park(eng.t, head, tokens[0], eng.session_identity)
        except BaseException as error:                 # refusals return None; anything else is an engine fault
            self.state.fault(error)
            raise KeeperHalt(repr(error)) from error
        if parked is None:
            return dict(info, event='park-skipped')
        self.pin(parked)
        return dict(info, event='parked')

    def use_head(self, s, sid):
        old = s.__dict__.get('sc117_head')
        s.sc117_head = sid
        if old and old != sid and not any(x.__dict__.get('sc117_head') == old for x in list(self.keeper.sessions.values())):
            self.unpin(old)

    def pin(self, sid):
        store = self.engine.sessions
        for gone in [x for x in self.pins if x not in store.index]:   # dropped by the store (a refused restore)
            self.pins.pop(gone)
        if not store.pin(sid):
            return False
        self.pins.pop(sid, None)
        self.pins[sid] = None
        while len(self.pins) > self.max_pins:
            old, _ = self.pins.popitem(last=False)
            store.unpin(old)
        return True

    def unpin(self, sid):
        self.pins.pop(sid, None)
        self.engine.sessions.unpin(sid)

    # ---------------------------------------------------------------- notes as an extension of the live state
    def live_ok(self, s):
        """The last engine call was this conversation's main call, and its prompt holds nothing a notes request would
        have to leave out (archive searches, keeper notices other than the RULES recital)."""
        live = s.__dict__.get('sc117_live')
        return (live is not None and live['count'] == self.engine.count and not recall_call(live['reply'])
                and extendable(live['messages']))

    def extension(self, s, req):
        """ctxkeeper's notes request `req` = fixed + noted + [request], made to continue the live state: the main call's
        messages (which start with fixed + noted), its reply, then the request with TAIL_NOTE. None if it cannot."""
        if not self.live_ok(s):
            return None
        live, head, ask = s.sc117_live, req[:-1], req[-1]
        if live['messages'][:len(head)] != head or not all(recital(m) for m in live['messages'][len(head):]):
            return None
        text = str(ask.get('content') or '')
        if LAYOUT_MARK not in text:
            return None
        return live['messages'] + [live['reply'], dict(ask, content=text.replace(LAYOUT_MARK, TAIL_NOTE + LAYOUT_MARK, 1))]

    # ---------------------------------------------------------------- the RULES recital stays where it was read
    def note_recital(self, s, messages):
        """After a main call: a recital ctxkeeper appended after the newest client message (a user message) is kept,
        anchored to that message, so later views show it at the same place."""
        history = s.__dict__.get('sc117_history')
        if not history:
            return
        newest = history[-1]
        for i in range(len(messages) - 1):
            if messages[i] is newest and recital(messages[i + 1]):  # the view holds the history's own message objects
                kept = s.__dict__.setdefault('sc117_recitals', {})
                kept[len(history) - 1] = (ck.fingerprint([newest]), copy.deepcopy(messages[i + 1]), s.state.get('restarts', 0))
                return

    def with_recitals(self, s, messages, view, end):
        """`view` ends with the client messages messages[h + cut:end]; insert each kept recital after its message
        (not after the newest client message: ctxkeeper appends that one itself)."""
        kept = s.__dict__.get('sc117_recitals')
        if not kept:
            return view
        start = ck.head_length(messages) + s.state['cut']
        places = []
        for i in sorted(kept):
            fp, msg, restarts = kept[i]
            if i < start or restarts != s.state.get('restarts', 0):
                del kept[i]                              # cut (or the conversation started over): its place is gone
            elif i < end and i < len(messages) - 1 and ck.fingerprint([messages[i]]) == fp:
                places.append((len(view) - (end - i), msg))   # positions in the view as given
        for at, msg in sorted(places, key=lambda p: p[0], reverse=True):   # rightmost first: the others stay put
            view = view[:at + 1] + [msg] + view[at + 1:]
        return view

    # ---------------------------------------------------------------- bookkeeping
    def record(self, s, kind, summary, head):
        row = dict(kind=kind, request=summary.get('request'), prompt_tokens=summary.get('prompt_tokens'),
                   cached_tokens=int(summary.get('continued_from') or 0), output_tokens=summary.get('output_tokens'),
                   prompt_wall_ms=summary.get('prompt_wall_ms'), decode_wall_ms=summary.get('decode_wall_ms'),
                   reset_ms=summary.get('reset_ms'), wall_s=summary.get('wall_s'))
        row['read_tokens'] = (row['prompt_tokens'] or 0) - row['cached_tokens']
        if summary.get('session'):
            row['session'] = {k: v for k, v in summary['session'].items() if k in ('parked', 'restored', 'refused', 'park_ms', 'restore_ms')}
        if head:
            row['head'] = head
        if s is None:
            return
        name = 'sc117_post' if threading.current_thread().name == 'ctxkeeper-notes' else 'sc117_calls'
        with self.calls_lock:
            s.__dict__.setdefault(name, []).append(row)

    def storage_ok(self):
        """The keeper's state directory in the service's storage checks: its own cap, the floor of the filesystem it
        is on, and on a RAM filesystem the service's MemAvailable floor."""
        used = 0
        try:
            for f in self.root.rglob('*'):
                try:
                    if f.is_file():
                        used += f.stat().st_size
                except OSError:
                    pass
            free = shutil.disk_usage(self.root).free
            dev = self.root.stat().st_dev
            floor = max([f for p, f in self.floors if Path(p).exists() and Path(p).stat().st_dev == dev] + [self.min_free])
        except OSError as error:
            return 'keeper store check failed: ' + repr(error)
        if used > self.max_bytes:
            return f'keeper state directory holds {used} bytes, over its cap {self.max_bytes} (SC117_KEEPER_MAX_GB)'
        if free < floor:
            return f'keeper state directory free {free} is below {floor}'
        if self.ram and self.meminfo is not None and self.meminfo() < self.mem_floor:
            return f'MemAvailable is below {self.mem_floor} (the keeper store is on a RAM filesystem)'
        return None

    def health(self):
        return dict(model=self.model_id, conversations=len(self.keeper.sessions), pinned_heads=len(self.pins),
                    checkpoints=getattr(self.engine, 'sessions', None) is not None, directory=str(self.root), library=str(LIB))

    def status(self):
        return {key: dict({k: s.state.get(k) for k in STATE_KEYS}, notes_chars=len(s.state.get('notes') or ''),
                          head=s.__dict__.get('sc117_head'), notes_due=s.pending is not None)
                for key, s in list(self.keeper.sessions.items())}
