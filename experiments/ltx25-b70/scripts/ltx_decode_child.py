"""Packet 92b: decode in its own process.

Question: is per-process GPU runtime state the shared resource that slows
every stage when they run as threads of one process? 92a refuted the
interpreter lock (lock wait 0.064 ms under load, switch interval inert) but
found the lane threads close to CPU-bound in native code. A decode child gets
its own Python, SYCL runtime and Level Zero context.

Module roles:

* Front end (imported by the decode node): `ensure_started` spawns the child
  once per server process, at custom-node import time: after the launcher's
  preflight and before ComfyUI serves, while no other process initialises a
  card. `request` sends one job and waits for its reply; `stop` asks the child
  to exit and waits for it; nothing here ever kills the child.
* Child (`python ltx_decode_child.py --fd N --config JSON`): imports torch and
  only the ComfyUI model code the VAEs need, with the server's own argv (so
  dtype and determinism flags match), sees only xpu:3 (ZE_AFFINITY_MASK, and
  its device uuid must equal the front end's xpu:3), loads its own copy of
  both VAEs, then decodes requests sequentially.

Protocol (multiprocessing.connection.Connection over a socketpair): one
header message (JSON) followed by one raw-bytes message per tensor. Every
tensor entry carries dtype, shape, nbytes and the sha256 of its bytes (the
oracle capture's convention); the receiver checks length and sha256 before
building the tensor and fails the job on any mismatch. Both directions.
"""
import hashlib
import json
import os
import sys
import threading
import time

PROTOCOL = 'ltx.decode-child.v1'
REPLY_TIMEOUT_S = 180.0
READY_TIMEOUT_S = 900.0
STOP_TIMEOUT_S = 120.0
CHILD_PHYSICAL_DEVICE = 3          # torch xpu index in the front end
MIN_FREE_AFTER_LOAD = 5 * 2**30    # xpu:3 free (device-wide) after the child loads its VAEs
MIN_FREE_AFTER_PROBE = 1 * 2**30   # ... after the probe's decodes


class ChildError(RuntimeError):
    """Any protocol, child or integrity failure. The caller latches."""


def require(value, message):
    if not value:
        raise ChildError(message)


# --- framing -------------------------------------------------------------------
def tensor_entry(name, tensor):
    import torch
    t = tensor.detach().to('cpu').contiguous()
    raw = t.view(torch.uint8).numpy().tobytes() if t.numel() else b''
    return ({'name': name, 'dtype': str(t.dtype).replace('torch.', ''), 'shape': list(t.shape),
             'nbytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}, raw)


def build_tensor(entry, raw):
    import torch
    require(isinstance(raw, (bytes, bytearray)) and len(raw) == entry['nbytes'],
            'short or long payload for %s: %s of %s bytes' % (entry.get('name'), len(raw), entry.get('nbytes')))
    require(hashlib.sha256(raw).hexdigest() == entry['sha256'],
            'sha256 mismatch for %s across the process boundary' % entry.get('name'))
    dtype = getattr(torch, entry['dtype'])
    if not raw:
        return torch.empty(entry['shape'], dtype=dtype)
    return torch.frombuffer(bytearray(raw), dtype=torch.uint8).view(dtype).reshape(entry['shape']).clone()


def send(conn, header, tensors=None):
    entries, payloads = [], []
    for name, tensor in (tensors or {}).items():
        entry, raw = tensor_entry(name, tensor)
        entries.append(entry)
        payloads.append(raw)
    header = dict(header, protocol=PROTOCOL, tensors=entries)
    conn.send_bytes(json.dumps(header).encode())
    for raw in payloads:
        conn.send_bytes(raw)
    return {e['name']: e['sha256'] for e in entries}


def recv(conn, timeout):
    """(header, {name: tensor}). Raises ChildError on timeout, EOF, length or hash mismatch."""
    if timeout is not None and not conn.poll(timeout):
        raise ChildError('no reply from the decode child within %.0f s' % timeout)
    try:
        header = json.loads(conn.recv_bytes().decode())
    except EOFError as error:
        raise ChildError('decode child pipe closed (child exited or died)') from error
    require(header.get('protocol') == PROTOCOL, 'protocol mismatch: %r' % header.get('protocol'))
    tensors = {}
    for entry in header.get('tensors', []):
        if timeout is not None and not conn.poll(timeout):
            raise ChildError('decode child stopped mid-message (%s)' % entry.get('name'))
        try:
            raw = conn.recv_bytes()
        except EOFError as error:
            raise ChildError('decode child pipe closed mid-message (%s)' % entry.get('name')) from error
        tensors[entry['name']] = build_tensor(entry, raw)
    return header, tensors


# --- front end -------------------------------------------------------------------
_STATE = {'proc': None, 'conn': None, 'ready': None, 'error': None, 'stopped': False,
          'lock': threading.Lock(), 'started_unix': None}


def state():
    s = {k: v for k, v in _STATE.items() if k not in ('proc', 'conn', 'lock')}
    proc = _STATE['proc']
    s['pid'] = None if proc is None else proc.pid
    s['returncode'] = None if proc is None else proc.poll()
    return s


def alive():
    proc = _STATE['proc']
    return proc is not None and proc.poll() is None and not _STATE['stopped'] and _STATE['error'] is None


def ensure_started(config, popen=None, child_script=None):
    """Spawn the child once and wait for its 'ready'. Records failure instead of raising."""
    import multiprocessing.connection
    import socket
    import subprocess
    with _STATE['lock']:
        if _STATE['proc'] is not None or _STATE['error'] is not None:
            return state()
        try:
            parent_sock, child_sock = socket.socketpair()
            env = dict(os.environ)
            # The child sees only its card; the launcher's own environment is
            # untouched (it refuses device filters for itself).
            env['ZE_AFFINITY_MASK'] = str(config.get('ze_affinity_mask', CHILD_PHYSICAL_DEVICE))
            env.pop('ONEAPI_DEVICE_SELECTOR', None)
            script = child_script or os.path.abspath(__file__)
            argv = [sys.executable, '-B', script, '--fd', str(child_sock.fileno()),
                    '--config', json.dumps(config)]
            proc = (popen or subprocess.Popen)(argv, env=env, pass_fds=(child_sock.fileno(),),
                                               stdin=subprocess.DEVNULL)
            child_sock.close()
            conn = multiprocessing.connection.Connection(parent_sock.detach())
            _STATE.update(proc=proc, conn=conn, started_unix=time.time())
            header, _ = recv(conn, config.get('ready_timeout_s', READY_TIMEOUT_S))
            require(header.get('op') == 'ready', 'child did not report ready: %s' % header.get('error', header))
            _STATE['ready'] = header
        except Exception as error:  # noqa: BLE001  (recorded; the child arm is refused)
            _STATE['error'] = repr(error)[:2000]
        return state()


def request(op, header=None, tensors=None, timeout=REPLY_TIMEOUT_S):
    """One round trip. Raises ChildError (the caller latches) on any failure."""
    require(alive(), 'decode child is not running: %s' % (_STATE['error'] or state()))
    conn = _STATE['conn']
    try:
        sent = send(conn, dict(header or {}, op=op), tensors)
        reply, out = recv(conn, timeout)
    except ChildError as error:
        _STATE['error'] = repr(error)[:2000]
        raise
    except (OSError, ValueError) as error:
        _STATE['error'] = repr(error)[:2000]
        raise ChildError('decode child pipe failed: %r' % error) from error
    if reply.get('op') == 'error':
        raise ChildError('decode child failed: %s' % reply.get('error', '')[-2000:])
    require(reply.get('received_sha256') == sent, 'child received different bytes than were sent')
    return reply, out


def stop(timeout=STOP_TIMEOUT_S):
    """Cooperative stop: ask, then wait for the process to exit. Never kills."""
    proc, conn = _STATE['proc'], _STATE['conn']
    record = {'requested': True, 'exited': False, 'returncode': None, 'reason': ''}
    if proc is None:
        record.update(exited=True, reason='never started')
        return record
    if proc.poll() is None and conn is not None:
        try:
            send(conn, {'op': 'stop'})
            reply, _ = recv(conn, 30.0)
            record['ack'] = reply.get('op')
        except Exception as error:  # noqa: BLE001  (fall through to waiting for exit)
            record['reason'] = 'stop message: ' + repr(error)[:300]
    try:
        record['returncode'] = proc.wait(timeout=timeout)
        record['exited'] = True
    except Exception as error:  # noqa: BLE001
        record['reason'] += ' no exit within %.0f s (%r); NOT killed' % (timeout, error)
    _STATE['stopped'] = True
    try:
        if conn is not None and record['exited']:
            conn.close()
    except Exception:  # noqa: BLE001
        pass
    return record


# --- child -------------------------------------------------------------------------
def _child_decode(vae, audio_vae, video, audio):
    """What the decode node's native path returns (VAEDecode + LTXVAudioVAEDecode),
    decoded with this process's own copy of the VAEs. The waveform stays on CPU
    here; the front end moves it to the audio latent's device, as the native
    node does."""
    latent = video
    if latent.is_nested:
        latent = latent.unbind()[0]
    images = vae.decode(latent)
    if len(images.shape) == 5:
        images = images.reshape(-1, images.shape[-3], images.shape[-2], images.shape[-1])
    audio_latent = audio
    if audio_latent.is_nested:
        audio_latent = audio_latent.unbind()[-1]
    waveform = audio_vae.decode(audio_latent).movedim(-1, 1).to(audio_latent.device)
    return images, waveform, int(audio_vae.first_stage_model.output_sample_rate)


def child_main(argv=None):
    import argparse
    import multiprocessing.connection
    ap = argparse.ArgumentParser()
    ap.add_argument('--fd', type=int, required=True)
    ap.add_argument('--config', required=True)
    a = ap.parse_args(argv)
    conn = multiprocessing.connection.Connection(a.fd)
    config = json.loads(a.config)
    sys.dont_write_bytecode = True
    try:
        source = config['source_dir']
        os.chdir(source)
        sys.path[:0] = [os.path.join(source, 'scripts'), source]
        sys.argv = list(config['server_argv'])
        import torch
        torch.set_num_threads(int(config.get('torch_threads', 16)))
        torch.use_deterministic_algorithms(True, warn_only=False)
        import comfy.options
        comfy.options.enable_args_parsing()
        import comfy.model_management  # noqa: F401  (parses the server's argv)
        import comfy.sd
        import comfy.utils
        torch.use_deterministic_algorithms(True, warn_only=False)
        require(torch.are_deterministic_algorithms_enabled() and
                not torch.is_deterministic_algorithms_warn_only_enabled(), 'strict determinism not set')
        require(torch.xpu.device_count() == 1, 'child must see exactly one card, sees %d' % torch.xpu.device_count())
        uuid = str(torch.xpu.get_device_properties(0).uuid)
        require(uuid == config['expected_uuid'], 'child card uuid %s is not the front end xpu:3 %s'
                % (uuid, config['expected_uuid']))
        import ltx_gil_probe as gil
        device = torch.device('xpu:0')
        vaes = []
        for path in config['vae_paths']:
            weights, metadata = comfy.utils.load_torch_file(path, return_metadata=True)
            vae = comfy.sd.VAE(sd=weights, metadata=metadata, device=device)
            vae.throw_exception_if_invalid()
            del weights
            vaes.append(vae)
        vae, audio_vae = vaes

        def memory():
            try:
                free, total = torch.xpu.mem_get_info(0)
            except Exception:  # noqa: BLE001
                free, total = None, None
            return {'free': free, 'total': total, 'reserved': int(torch.xpu.memory_reserved(0)),
                    'allocated': int(torch.xpu.memory_allocated(0))}
        send(conn, {'op': 'ready', 'pid': os.getpid(), 'uuid': uuid, 'torch': torch.__version__,
                    'memory': memory(), 'vae_dtypes': [str(v.vae_dtype) for v in vaes],
                    'cpu': gil.cpu_snapshot()})
    except BaseException as error:  # noqa: BLE001
        import traceback
        try:
            send(conn, {'op': 'error', 'error': ''.join(traceback.format_exception(type(error), error,
                                                                                    error.__traceback__))[-4000:]})
        finally:
            return 3
    while True:
        try:
            header, tensors = recv(conn, None)
        except ChildError:
            return 0                       # front end gone: exit quietly
        received = {e['name']: e['sha256'] for e in header.get('tensors', [])}
        op = header.get('op')
        if op == 'stop':
            send(conn, {'op': 'stopping', 'received_sha256': received})
            del vae, audio_vae, vaes
            import gc
            gc.collect()
            try:
                torch.xpu.empty_cache()
            except Exception:  # noqa: BLE001
                pass
            return 0
        try:
            if op == 'decode':
                cpu0, t0 = time.thread_time(), time.perf_counter()
                with torch.inference_mode():
                    images, waveform, rate = _child_decode(vae, audio_vae, tensors['video'], tensors['audio'])
                reply = {'op': 'result', 'index': header.get('index'), 'sample_rate': rate,
                         'received_sha256': received, 'decode_s': round(time.perf_counter() - t0, 4),
                         'job_cpu_s': round(time.thread_time() - cpu0, 4), 'memory': memory(),
                         'cpu': gil.cpu_snapshot()}
                send(conn, reply, {'images': images, 'waveform': waveform})
            elif op == 'stats':
                send(conn, {'op': 'stats', 'received_sha256': received, 'memory': memory(),
                            'cpu': gil.cpu_snapshot()})
            else:
                send(conn, {'op': 'error', 'error': 'unknown op %r' % op, 'received_sha256': received})
        except BaseException as error:  # noqa: BLE001  (reported; the front end latches)
            import traceback
            send(conn, {'op': 'error', 'received_sha256': received,
                        'error': ''.join(traceback.format_exception(type(error), error, error.__traceback__))[-4000:]})


if __name__ == '__main__':
    sys.exit(child_main())
