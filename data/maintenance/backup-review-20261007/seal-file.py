"""Hash, flush and rename one completed backup inside the monitored worker."""
from pathlib import Path
import hashlib
import json
import os
import sys

partial, final = map(Path, sys.argv[1:])
assert partial.is_file() and not partial.is_symlink() and not final.exists()
with partial.open('rb') as stream:
    os.fsync(stream.fileno())
    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
partial.rename(final)
fd = os.open(final.parent, os.O_RDONLY | os.O_DIRECTORY)
try:
    os.fsync(fd)
finally:
    os.close(fd)
print(json.dumps({'path': str(final), 'bytes': final.stat().st_size,
                  'sha256': digest, 'fsynced': True,
                  'post_remount_readback_verified': False}))
