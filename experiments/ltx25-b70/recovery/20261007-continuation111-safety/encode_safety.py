"""Inactive source delta: extend the sealed110 bound VAE OOM refusal to encode.

No model imports, monkey patches, file writes or admission. Future integration
must bind NativeReferenceSafety before any encode and retain its fault latch.
Successful encoding and the existing decode path are byte-for-byte unchanged.
"""
import ast
import hashlib

SOURCE_SHA256 = 'd1c63b66a6d0cf467ecb084d7ec5fb73d20b0fac43181668124a8ded06aa7604'


def transform_sd(raw):
    if type(raw) is not bytes or hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError('Expected exact sealed110 VAE source')
    old = (b'            except Exception as e:\n'
           b'                model_management.raise_non_oom(e)\n'
           b'                logging.warning("Warning: Ran out of memory when regular VAE encoding, retrying with tiled VAE encoding.")')
    new = old.replace(
        b'                logging.warning(',
        b'                if getattr(self, "_ltx_native_reference_safety", None) is not None:\n'
        b'                    self._ltx_native_reference_safety.reject_oom(self, e)\n'
        b'                logging.warning(', 1)
    if raw.count(old) != 1:
        raise ValueError('Encode OOM insertion must be unique')
    result = raw.replace(old, new, 1)
    tree = ast.parse(result)
    vae = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'VAE')
    for name in ('encode', 'decode'):
        method = next(n for n in vae.body if isinstance(n, ast.FunctionDef) and n.name == name)
        calls = [n for n in ast.walk(method) if isinstance(n, ast.Call) and
                 isinstance(n.func, ast.Attribute) and n.func.attr == 'reject_oom']
        if len(calls) != 1:
            raise ValueError('Exactly one OOM refusal required in VAE.' + name)
    return result
