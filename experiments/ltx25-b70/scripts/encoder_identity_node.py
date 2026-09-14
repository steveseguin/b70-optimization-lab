"""Expose the immutable startup identity through the local ComfyUI endpoint."""
import hashlib
import json
import os
from pathlib import Path

from aiohttp import web
from server import PromptServer

identity_path = Path(os.environ['LTX_ENCODER_RUN_DIR']) / 'server-identity.json'
identity_bytes = identity_path.read_bytes()
if hashlib.sha256(identity_bytes).hexdigest() != os.environ['LTX_ENCODER_IDENTITY_SHA256']:
    raise RuntimeError('Encoder startup identity changed')
identity = json.loads(identity_bytes)
if identity['pid'] != os.getpid():
    raise RuntimeError('Encoder identity names another process')


@PromptServer.instance.routes.get('/ltx-encoder/identity')
async def encoder_identity(request):
    return web.json_response(identity)


NODE_CLASS_MAPPINGS = {}
