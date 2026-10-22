"""Observe inherited limits; never change them in an imported runtime module."""
import resource

KINDS = sorted({getattr(resource, n) for n in dir(resource) if n.startswith('RLIMIT_')})


def snapshot():
    return {str(k): list(resource.getrlimit(k)) for k in KINDS}


BASELINE = snapshot()


def check():
    if resource.getrlimit(resource.RLIMIT_AS) != (resource.RLIM_INFINITY, resource.RLIM_INFINITY):
        raise ValueError('native launch refuses finite RLIMIT_AS')
    if snapshot() != BASELINE:
        raise ValueError('resource limits changed before native exec')
    return snapshot()
