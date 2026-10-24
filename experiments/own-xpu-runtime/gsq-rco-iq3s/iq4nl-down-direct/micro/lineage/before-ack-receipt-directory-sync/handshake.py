"""One fixed readiness/physical-contact ACK seam; no device or process operations."""
import ctypes,errno,hashlib,json,os,stat
from pathlib import Path

def publish_ack(result,identity,current_holders,target_nodes,snapshot,unit_state):
    """Call only after the unchanged monitor has accepted this entire sample.

    Returns false while readiness has not been atomically published. Never
    manufactures a DRM FD. Unexpected/malformed readiness is a fatal incident.
    """
    result=Path(result);ready=result/'backend-ready.txt';ack=result/'backend-ack.txt'
    try:fd=os.open(ready,os.O_RDONLY|os.O_NOFOLLOW)
    except FileNotFoundError:return False
    try:
        a=os.fstat(fd)
        assert stat.S_ISREG(a.st_mode) and a.st_nlink==1 and a.st_uid==os.getuid() and 0<a.st_size<=256,'ready type/extent/owner'
        data=os.read(fd,a.st_size+1);b=os.fstat(fd);c=os.stat(ready,follow_symlinks=False)
        stamp=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        assert stamp(a)==stamp(b)==stamp(c) and len(data)==a.st_size,'ready changed'
    finally:os.close(fd)
    parts=data.decode('ascii').split();assert len(parts)==4 and parts[0]=='GSQ_NATIVE_BACKEND_READY_V1','ready schema'
    assert (int(parts[1]),int(parts[2]))==tuple(identity) and len(parts[3])==32 and all(x in '0123456789abcdef' for x in parts[3]),'ready native identity/challenge'
    assert data==(' '.join(parts)+'\n').encode(),'canonical ready message'
    assert current_holders and all(x['node'] in target_nodes for x in current_holders),'positive current native target contact'
    assert all((x['pid'],snapshot['holders'][str(x['pid'])]['start_ticks'])==tuple(identity) for x in current_holders),'current native holder identity'
    assert not ack.exists() and not (result/'backend-ack.partial').exists(),'one ACK only'
    # Bind the exact accepted passive sample before granting execution.
    receipt=dict(native_identity=list(identity),ready_sha256=hashlib.sha256(data).hexdigest(),native_holders=current_holders,snapshot=snapshot,unit_state=unit_state)
    with (result/'backend-contact.json').open('x') as f:json.dump(receipt,f);f.write('\n');f.flush();os.fsync(f.fileno())
    part=result/'backend-ack.partial'
    fd=os.open(part,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        assert os.write(fd,data)==len(data),'ACK write';os.fsync(fd)
    finally:os.close(fd)
    libc=ctypes.CDLL(None,use_errno=True);rename=libc.renameat2
    rename.argtypes=[ctypes.c_int,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p,ctypes.c_uint];rename.restype=ctypes.c_int
    if rename(-100,os.fsencode(part),-100,os.fsencode(ack),1)!=0:raise OSError(ctypes.get_errno(),'exclusive ACK publication')
    fd=os.open(result,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:os.fsync(fd)
    finally:os.close(fd)
    return True
