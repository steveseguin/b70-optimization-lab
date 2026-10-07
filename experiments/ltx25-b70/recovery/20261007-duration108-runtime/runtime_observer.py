"""Read real registered Comfy node owners, never a separately imported mirror.

Imports are lazy. Observation neither loads models nor changes execution state.
Source closure and the identity of supplied runtime modules belong to the sealed
launcher. Native memory admission is a separate synchronized safety operation.
"""
import inspect


def node_globals(registry, class_name, method):
    cls = registry[class_name]
    function = inspect.unwrap(getattr(cls, method))
    state = function.__globals__
    if state.get('NODE_CLASS_MAPPINGS', {}).get(class_name) is not cls:
        raise RuntimeError('Registered node owner does not match its defining module: ' + class_name)
    return state


def observe(registry, prompt_queue, pipeline, capture, lean, *, fault=False):
    graph = node_globals(registry, 'LTXGraphCaptureGate', '_apply')
    decode = node_globals(registry, 'LTXPipelineDecode', 'apply')
    running, pending = prompt_queue.get_current_queue()
    # Import only the already configured session module; no device import here.
    import ltx_resolution_session as session
    pipe = session.pipeline_snapshot(pipeline)
    installed = graph['_installed']
    routes = len(capture._ROUTES)
    if installed is not None:
        # Both the registered node's installation and actual graph route objects
        # are inspected. A route disappearing from one inventory is not absence.
        routes = max(routes, len(installed[1]), 1)
    replicas = sum(len(values) for values in decode['_REPLICA_SETS'].values())
    lean_count = len(lean._MEMO_INSTALLED) + len(lean._SENTRY_INSTALLED)
    writer = decode['_WRITER']
    with writer.queue.mutex:
        preview_pending = writer.queue.unfinished_tasks
    preview_failures = len(decode['SAVE_FAILURES'])
    return {'queue_running': len(running), 'queue_pending': len(pending),
            'queue_running_ids': [row[1] for row in running],
            'queue_pending_ids': [row[1] for row in pending],
            'pipeline': pipe, 'fault': bool(fault or preview_failures),
            'preview_pending': preview_pending, 'preview_failures': preview_failures,
            'sampler_routes': routes, 'lean_state': lean_count,
            'decode_replicas': replicas,
            'captures_frozen': capture.CAPTURES_FROZEN[0],
            'loads_frozen': capture.LOADS_FROZEN[0],
            'registered_module_paths': {'graph': graph['__file__'], 'decode': decode['__file__']}}


def actual_state(fault=False):
    import nodes
    from server import PromptServer
    import ltx_pipeline
    import ltx_graph_capture
    import ltx_lean_conditioning
    return observe(nodes.NODE_CLASS_MAPPINGS, PromptServer.instance.prompt_queue,
                   ltx_pipeline, ltx_graph_capture, ltx_lean_conditioning, fault=fault)
