"""Text encode with optional encode-ahead.

`original` is the native CLIPTextEncode, called inline, exactly as the control
recipe does. `pipeline` computes every clip's conditioning with the same native
call, but starts the NEXT clip's encode on a worker thread as soon as this
clip's conditioning has been handed over, so it runs on xpu:2 while the sampler
works on xpu:0 and xpu:1.

The next clip's text comes from the next clip's own request: the node looks
the queued prompt with `clip_index == index + 1` up in ComfyUI's prompt queue
and encodes THAT text. If no such prompt is queued yet, nothing runs ahead. A
job is tagged with the SHA-256 of the text it encoded, and a prompt whose text
differs from its queued job's tag discards the job and encodes inline
(`speculation_miss` in the receipt). Nothing is guessed and nothing is cached:
each conditioning is produced by its own encode, consumed once by the clip it
was computed for, and dropped. Only the timing changes.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import time

import torch

import ltx_pipeline as pipeline
from encoder_diagnostics import _context

MODEL_SHA256 = '273ad9125c1cbe239e44ffaa29ce11a7eb8f89d252630de7ef8e6503a1c1cf0f'
_failed = False


def require(value, message):
    if not value:
        raise RuntimeError(message)


def write_json(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')


def native_encode(clip, text, consume_observations=False):
    import nodes
    require(clip is not None, 'CLIP input is invalid: None')
    # On a worker thread the encode issues on this thread's own streams and
    # stages any cross-card moves (sharded encoder) through pinned memory.
    import ltx_graph_capture as capture
    import ltx_graph_text_encoder as tenc
    worker = threading.current_thread().name.startswith('ltx-encode')
    if worker:
        capture.set_pipelined(True)
        try:
            tenc.reset_forward_caches(clip)
        except Exception:  # noqa: BLE001  (encoder not shadowed: nothing to reset)
            pass
    try:
        if worker:
            # Everything the encode issues on a worker thread must sit on that
            # thread's streams: the eager parts (embedding lookup, norms, the
            # projection, the parent loop's clones) as well as the graph replays
            # and staged cross-card copies. With the eager parts on the default
            # stream nothing ordered them against the thread-stream replays, and
            # a replay could read a half-written input: servers 79b-81 produced
            # one all-NaN clip per run, on varying prompts and threads, while the
            # first encode on each thread (captured under a full synchronize)
            # stayed bit-exact.
            import contextlib
            with contextlib.ExitStack() as stack:
                for i in range(torch.xpu.device_count()):
                    stack.enter_context(torch.xpu.stream(capture.thread_stream(torch.device('xpu', i))))
                encoded = nodes.CLIPTextEncode().encode(clip, text)
        else:
            encoded = nodes.CLIPTextEncode().encode(clip, text)
    finally:
        if worker:
            for i in range(torch.xpu.device_count()):
                try:
                    capture.thread_stream(torch.device('xpu', i)).synchronize()
                except Exception:  # noqa: BLE001
                    pass
            capture.set_pipelined(False)
    require(isinstance(encoded, tuple) and len(encoded) == 1,
            'CLIPTextEncode no longer returns a single conditioning')
    if consume_observations:
        # The lab's embedding instrumentation enforces one-encode-then-consume,
        # and its consumer is LTXHostEmbeddingPlacementCheck, which a pipelined
        # arm cannot carry: under encode-ahead the encode that finishes during a
        # request belongs to the NEXT clip, so the accounting no longer lines up
        # with a request boundary. Every encode here runs on the one worker
        # thread, so consuming right after each encode keeps the protocol
        # satisfied. This discards a diagnostic; it touches no numerical value.
        group = getattr(clip, '_host_embedding', None)
        require(group is not None, 'Pipelined encode expects the host-embedding CLIP adapter')
        group.consume_observations()
    return encoded[0]


def _text_sha256(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _queued_text(index):
    """The prompt text of the queued request for clip `index`, from the server's own queue.

    Returns None when no pending prompt carries a pipeline-mode
    LTXPipelineTextEncode node with that clip index. Only pending prompts are
    considered; the running prompt is the caller.
    """
    try:
        import server
    except ImportError:
        return None
    instance = getattr(server.PromptServer, 'instance', None)
    if instance is None:
        return None
    _running, queued = instance.prompt_queue.get_current_queue_volatile()
    found = None
    for item in queued:
        prompt = item[2] if len(item) > 2 else None
        if not isinstance(prompt, dict):
            continue
        for node in prompt.values():
            if not isinstance(node, dict) or node.get('class_type') != 'LTXPipelineTextEncode':
                continue
            inputs = node.get('inputs', {})
            if inputs.get('mode') == 'pipeline' and inputs.get('clip_index') == index:
                text = inputs.get('text')
                if not isinstance(text, str):
                    return None
                require(found is None or found == text,
                        f'Two queued prompts claim clip {index} with different text')
                found = text
    return found


class LTXPipelineTextEncode:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'clip': ('CLIP',),
                             'text': ('STRING', {'multiline': True}),
                             'mode': (list(pipeline.MODES),),
                             'clip_index': ('INT', {'default': 0, 'min': 0, 'max': 1000000}),
                             'depth': ('INT', {'default': 1, 'min': 1,
                                               'max': pipeline.MAX_PENDING}),
                             'run_name': ('STRING', {'default': 'assign-unique-request-name'})}}

    RETURN_TYPES = ('CONDITIONING',)
    FUNCTION = 'apply'
    CATEGORY = 'lab/validation'

    def apply(self, clip, text, mode, clip_index, depth, run_name):
        global _failed
        try:
            return self._apply(clip, text, mode, clip_index, depth, run_name)
        except BaseException:
            # Sticky: preserve the process and the evidence, never retry.
            _failed = True
            pipeline.clear()
            raise

    def _apply(self, clip, text, mode, clip_index, depth, run_name):
        require(not _failed, 'Previous pipeline failure; halt submissions and inspect evidence')
        require(mode in pipeline.MODES, 'Only preregistered modes are admitted')
        require(isinstance(run_name, str) and re.fullmatch(r'[a-z0-9][a-z0-9-]{0,119}', run_name),
                'Unsafe request name')
        run, identity = _context()
        require(identity['model_verification_sha256'] == MODEL_SHA256 and
                identity['server_identity_sha256'] == os.environ.get('LTX_ENCODER_IDENTITY_SHA256'),
                'Model/startup identity changed')
        server = json.loads((run / 'server-identity.json').read_text())
        hashes = {}
        for path, name in ((Path(pipeline.__file__), 'ltx_pipeline.py'),
                           (Path(__file__), 'pipeline_node.py')):
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            require(server['extension_sha256s'][name] == actual, 'Sealed extension changed: ' + name)
            hashes[name] = actual
        require(torch.are_deterministic_algorithms_enabled() and
                not torch.is_deterministic_algorithms_warn_only_enabled(),
                'Strict determinism required')

        report = {'schema': 'ltx.pipeline-request.v1', **identity, 'run_name': run_name,
                  'mode': mode, 'clip_index': clip_index, 'depth': depth,
                  'extension_sha256s': hashes,
                  'claim': 'every clip computes its own conditioning with the native encode from '
                           'the text of its own queued request and consumes it once; nothing is '
                           'cached, reused or guessed between clips. Only the moment the work runs '
                           'changes, so it overlaps the sampler on other cards.',
                  'passed': False}
        started = time.monotonic()
        try:
            if mode == 'original':
                conditioning = native_encode(clip, text)
                report['detail'] = {'computed_inline': True}
            else:
                tag = _text_sha256(text)
                lookups = []

                def lookahead(i):
                    queued = _queued_text(i)
                    lookups.append({'index': i, 'queued': queued is not None,
                                    'text_sha256': None if queued is None else _text_sha256(queued)})
                    if queued is None:
                        return None
                    return (lambda: native_encode(clip, queued, consume_observations=True),
                            _text_sha256(queued))

                conditioning, detail = pipeline.run_ahead(
                    'encode', clip_index, depth,
                    lambda: native_encode(clip, text, consume_observations=True),
                    tag=tag, lookahead=lookahead)
                detail['placement_observations'] = 'consumed by the pipeline worker'
                detail['text_sha256'] = tag
                detail['lookahead'] = {'source': 'server prompt queue', 'lookups': lookups}
                report['detail'] = detail
            report['passed'] = True
        finally:
            report['seconds'] = time.monotonic() - started
            write_json(run / ('pipeline-' + run_name + '.json'), report)
        return (conditioning,)


NODE_CLASS_MAPPINGS = {'LTXPipelineTextEncode': LTXPipelineTextEncode}
