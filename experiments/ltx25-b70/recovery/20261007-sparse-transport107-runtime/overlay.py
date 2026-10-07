"""Exact106 -> sparse107 metadata overlay. Pure byte transformation; no runtime imports."""
import ast
import hashlib

GRAPH = 'source/scripts/ltx_graph_capture.py'
SAMPLER = 'source/scripts/pipeline_sampler_node.py'
SOURCE_SHAS = {
    GRAPH: '3a9a99954cb4877829c4407eb74306f6b409864002dfcccf3562fd0c98380400',
    SAMPLER: 'ae4af44f9315b01a2b8d684a046d6fda741cea4d35f52a2b72ea04f268adb0a3',
}
SOURCE_HASHES = SOURCE_SHAS  # Exact builder API; keys are packet-relative script paths.


def require(ok, why):
    if not ok:
        raise ValueError(why)


def replace_once(source, old, new):
    require(source.count(old) == 1, 'Exact source anchor differs: ' + repr(old[:100]))
    return source.replace(old, new, 1)


def transform_graph(source):
    source = replace_once(source, 'import torch\n',
                          'import torch\nimport ltx_sparse_transport107 as _transport107\n')
    source = replace_once(source, '        copied = 0\n        for i, (buffer, value)',
                          '        copied = 0\n        _trace_job = _transport107.current()\n'
                          '        _trace_fill = None\n        for i, (buffer, value)')
    source = replace_once(source,
        '            fill_static(buffer, value)\n            slot.sources[i] = value\n            copied += 1\n        return copied',
        '            if _trace_job.recording:\n'
        '                if _trace_fill is None:\n'
        '                    _trace_fill = _trace_job.fill_begin(str(self.device), thread_stream(self.device))\n'
        "                _trace_target = getattr(buffer, '_graph_fill_target', None)\n"
        '                if _trace_target is None:\n'
        '                    _trace_target = buffer\n'
        '                _trace_job.fill_add(_trace_fill, _trace_target.numel() * _trace_target.element_size())\n'
        '            fill_static(buffer, value)\n            slot.sources[i] = value\n            copied += 1\n'
        '        if _trace_fill is not None:\n'
        '            _trace_job.fill_end(_trace_fill, thread_stream(self.device))\n'
        '        return copied')
    source = replace_once(source,
        '    src_dev = value.device\n    host = _pinned(value.shape, value.dtype, tag)\n',
        '    src_dev = value.device\n    host = _pinned(value.shape, value.dtype, tag)\n'
        '    _trace_job = _transport107.current()\n    _trace_move = None\n')
    source = replace_once(source,
        '        host.copy_(value, non_blocking=True)\n        event = torch.xpu.Event()\n',
        '        if _trace_job.recording:\n'
        '            _trace_move = _trace_job.move_begin(tag, str(src_dev), str(device), tuple(value.shape),\n'
        '                str(value.dtype), value.numel() * value.element_size(), thread_stream(src_dev))\n'
        '        host.copy_(value, non_blocking=True)\n'
        '        if _trace_move is not None:\n'
        '            _trace_job.move_d2h_end(_trace_move, thread_stream(src_dev))\n'
        '        event = torch.xpu.Event()\n')
    source = replace_once(source,
        '    event.synchronize()\n    with torch.xpu.device(device), torch.xpu.stream(thread_stream(device)):\n'
        '        out = torch.empty(value.shape, dtype=value.dtype, device=device)\n'
        '        out.copy_(host, non_blocking=True)\n    return out',
        '    if _trace_move is not None:\n'
        '        _trace_job.wait_begin(_trace_move)\n'
        '    event.synchronize()\n'
        '    if _trace_move is not None:\n'
        '        _trace_job.wait_end(_trace_move)\n'
        '    with torch.xpu.device(device), torch.xpu.stream(thread_stream(device)):\n'
        '        if _trace_move is not None:\n'
        '            _trace_job.move_alloc_begin(_trace_move)\n'
        '        out = torch.empty(value.shape, dtype=value.dtype, device=device)\n'
        '        if _trace_move is not None:\n'
        '            _trace_job.move_alloc_end(_trace_move)\n'
        '            _trace_job.move_h2d_begin(_trace_move, thread_stream(device))\n'
        '        out.copy_(host, non_blocking=True)\n'
        '        if _trace_move is not None:\n'
        '            _trace_job.move_end(_trace_move, thread_stream(device))\n'
        '    return out')
    source = replace_once(source,
        '                _busy = busy_begin(self.device)\n                entry.graph.replay()\n'
        '                busy_end(_busy, self.device, self.index)',
        '                _busy = busy_begin(self.device)\n'
        '                _trace_job = _transport107.current()\n'
        '                _trace_replay = None\n'
        '                if _trace_job.recording:\n'
        '                    _trace_replay = _trace_job.replay_begin(self.index, str(self.device), thread_stream(self.device))\n'
        '                entry.graph.replay()\n'
        '                if _trace_replay is not None:\n'
        '                    _trace_job.replay_end(_trace_replay, self.index + len(self.blocks) - 1,\n'
        '                                          str(self.device), thread_stream(self.device))\n'
        '                busy_end(_busy, self.device, self.index)')
    source = replace_once(source,
        "        route = self.original_route\n        cache = args['transformer_options'][CACHE_KEY]\n",
        '        route = self.original_route\n'
        '        _transport107.current().block_enter(self.index, str(route.device), str(route.primary),\n'
        "            route.last, len(self.blocks), len(args['img']) if isinstance(args['img'], (tuple, list)) else 1)\n"
        "        cache = args['transformer_options'][CACHE_KEY]\n")
    return source


SAMPLER_WRAPPER = '''
_transport107_setup_lock = _transport107_threading.Lock()


def _transport107_event(device):
    with torch.xpu.device(device):
        return torch.xpu.Event(enable_timing=True)


def _transport107_begin_job(clip_index):
    import ltx_resolution_session as _trace_session
    _trace_thread = _transport107_threading.current_thread()
    with pipeline._LOCK:
        _trace_workers = tuple(pipeline._STAGES.get('sample', {}).get('workers', ()))
        require(len(_trace_workers) == 2 and all(w.is_alive() and w.ident is not None for w in _trace_workers),
                'Sparse trace requires exactly two registered live sampler workers')
        _trace_matches = [i for i, w in enumerate(_trace_workers)
                          if w is _trace_thread and w.ident == _transport107_threading.get_ident()]
        require(len(_trace_matches) == 1, 'Sampler job is not on its registered owning thread')
        _trace_bindings = {i: {'ident': w.ident, 'name': w.name} for i, w in enumerate(_trace_workers)}
    _trace_meta = _trace_session.auxiliary_metadata()
    require(_trace_meta is not None and _trace_meta['halted'] is False, 'Sparse trace authority missing or halted')
    _trace_rows = [r for r in _trace_session._authority.plan['requests'] if r['clip_index'] == clip_index]
    if _trace_rows:
        require(len(_trace_rows) == 1 and _trace_rows[0]['phase'] in ('candidate-check', 'timed-fast'),
                'Unexpected sampler job phase')
        _trace_phase = _trace_rows[0]['phase']
        require(_trace_meta['phase'] == {'candidate-check': 'optimized_preparation', 'timed-fast': 'timing'}[_trace_phase],
                'Sparse trace job differs from current authority phase')
    else:
        require(clip_index in (99907030, 99907041) and _trace_meta['phase'] == 'optimized_preparation',
                'Unplanned sampler setup job')
        _trace_phase = 'setup'
    _trace_identity = {k: _trace_meta[k] for k in ('plan_sha256', 'runtime_manifest_sha256',
                                                'server_identity_sha256', 'qualification_id')}
    with _transport107_setup_lock:
        _transport107.configure(_trace_bindings, _transport107_event, _trace_identity)
    return _transport107.begin_job(clip_index, _trace_matches[0], _trace_phase)


def sample_clip(clip_index, noise_a, guider_a, sampler_a, sigmas_a,
                noise_b, guider_b, sampler_b, sigmas_b,
                video_latent, audio_latent, upscale_model, vae, lean_mode=False):
    try:
        _trace_job = _transport107_begin_job(clip_index)
        _trace_result = _sample_clip107_body(clip_index, noise_a, guider_a, sampler_a, sigmas_a,
            noise_b, guider_b, sampler_b, sigmas_b,
            video_latent, audio_latent, upscale_model, vae, lean_mode=lean_mode)
        # Original body returns only after its existing stream drains and sentries.
        _trace_receipt = _trace_job.finish_after_existing_drains(True)
        pipeline.record_fingerprint(('transport-trace', clip_index), _trace_receipt)
        return _trace_result
    finally:
        _transport107.clear()

'''


def transform_sampler(source):
    source = replace_once(source, 'import torch\n',
        'import torch\nimport threading as _transport107_threading\n'
        'import ltx_sparse_transport107 as _transport107\n')
    source = replace_once(source, '\ndef sample_clip(clip_index,',
                          SAMPLER_WRAPPER + '\ndef _sample_clip107_body(clip_index,')
    start = source.index('\ndef _sample_chain(clip_index,')
    end = source.index('\n# --- packet 96:', start)
    chain = source[start:end]
    for stage in ('a', 'b'):
        chain = replace_once(chain, "    lean.set_stage('%s')\n" % stage,
            "    lean.set_stage('%s')\n    _transport107.current().stage('%s')\n" % (stage, stage))
    source = source[:start] + chain + source[end:]
    source = replace_once(source,
        "                    detail['emitted_context_sentry'] = pipeline.fingerprint(('context-sentry', emitted))\n",
        "                    detail['emitted_context_sentry'] = pipeline.fingerprint(('context-sentry', emitted))\n"
        "                    detail['emitted_transport_trace'] = pipeline.fingerprint(('transport-trace', emitted))\n")
    return source


def transform_sources(sources):
    require(set(sources) == set(SOURCE_SHAS), 'Exact two106 source inputs required')
    result = {}
    for path, transform in ((GRAPH, transform_graph), (SAMPLER, transform_sampler)):
        raw = sources[path]
        require(type(raw) is bytes and hashlib.sha256(raw).hexdigest() == SOURCE_SHAS[path],
                'Pinned106 source differs: ' + path)
        modified = transform(raw.decode())
        ast.parse(modified)
        result[path] = modified.encode()
    return result
