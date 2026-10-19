"""Copy-forward v1: a failed experiment can still have a proven clean teardown.

No launches, signals, device opens, stale-marker recovery or latch removal.
The caller owns the permit, the original drain checks and the success writer.
"""
from contextlib import contextmanager
from pathlib import Path

VERSION = "own-runtime.teardown-on-error.v1"


def require(condition, message):
    if not condition:
        raise ValueError(message)


class StickyCheck:
    """A consumed journal fault (or stop/check failure) cannot later look clean."""

    def __init__(self, check):
        self.check = check
        self.failure = None

    def __call__(self):
        if self.failure is not None:
            raise self.failure
        try:
            return self.check()
        except BaseException as error:
            self.failure = error
            raise


def require_reaped(pids, proc=Path('/proc')):
    """Require /proc disappearance, stronger than zombie-aware PID identity.

    An existing directory, including a zombie, reused PID, or an unreadable
    directory, refuses. A reaped PID has neither fd nor fdinfo entries. Only
    ENOENT/ESRCH proves absence; permission and other I/O errors propagate.
    This deliberately does not reap, stop, or signal someone else's process.
    """
    for pid in pids:
        require(type(pid) is int and pid > 0, 'invalid child PID')
        try:
            (Path(proc) / str(pid)).lstat()
        except (FileNotFoundError, ProcessLookupError):
            continue
        raise ValueError('child not reaped (or PID reused): ' + str(pid))


def finish_on_error(error, *, prove, complete):
    """Prove first, then call the SAME completion path used on success.

    Return whether cleanup succeeded. The caller must still raise the original
    error (or preserve an existing nonzero return). A secondary failure is a
    note on that error, never a reason to discard it or relax the proof.
    """
    try:
        prove()
        complete()
    except BaseException as cleanup_error:
        error.add_note('teardown remains unconfirmed: ' + str(cleanup_error))
        return False
    return True


@contextmanager
def drained_on_error(*, prove, complete):
    try:
        yield
    except BaseException as error:
        finish_on_error(error, prove=prove, complete=complete)
        raise


def finish_chain_error(admission, error):
    """Packet124b-style adapter hook, called while both permits are held."""
    if admission.lease.completed:
        return True

    def prove():
        require(admission.lease.entered, 'lane reservation not acquired')
        require(admission.drain.stream is not None and admission.drain.record is not None,
                'this window does not own a drain permit')
        watch = admission.watch
        require(watch is not None, 'window supervision not established')
        require(not watch.new_gpu_fault, 'new GPU fault observed')
        require(set(watch.launched) == set(admission.monitor.owners),
                'launched owners differ from monitored owners')
        require_reaped(watch.launched, admission.proc)
        for child in watch.cpu_children:
            require(child.poll() is not None, 'CPU child still running')
        require_reaped([child.pid for child in watch.cpu_children], admission.proc)
        # Do not depend on the rate-limited last check, or a success-only
        # postflight skipped by the Python failure. Keep its full five seconds.
        admission.failure_check()
        watch.last = float('-inf')
        watch.postflight()
        require(not watch.new_gpu_fault, 'new GPU fault during postflight')
        admission.failure_check()
        require_reaped(watch.launched, admission.proc)

    def complete():
        admission.record.update(passed=False, teardown_on_error=VERSION,
                                window_error=str(error))
        # Includes monitor.finish, READY proof, foreign-client census, the
        # shared drain writer and matching-token lane release, in that order.
        admission.complete_teardown()

    return finish_on_error(error, prove=prove, complete=complete)


def prove_screen_exit(row, child, teardown, output, *, proc=Path('/proc')):
    """A v4 parent may release only its worker's already-confirmed drain.

    This never overwrites a refused/prior Teardown record. The parent's release
    callback still performs its original stop, fault and foreign-client checks.
    """
    require(child is not None and child.poll() is not None, 'screen worker still live')
    require(row.get('pid') == child.pid and row.get('device_executed') is True,
            'screen child identity missing')
    require(type(row.get('process_start_ticks')) is int, 'screen start identity missing')
    require(not row.get('child_still_running') and not row.get('child_retained'),
            'screen owner retained')
    require_reaped([child.pid], proc)
    require(teardown.get('drained') is True and not teardown.get('gate_refused')
            and teardown.get('pid') == child.pid
            and teardown.get('boot_id') == row.get('boot_id')
            and teardown.get('output') == str(Path(output) / 'run'),
            'this screen has no matching completed drain')


def prove_transport_exit(transport, *, proc=Path('/proc')):
    """Worker-side proof; a closed flag alone is never evidence of reaping."""
    require(transport.children and not transport.retained, 'rank ownership incomplete')
    require(all(child.poll() is not None for child in transport.children), 'rank still live')
    require_reaped([child.pid for child in transport.children], proc)
    # Bound before the first rank launch; this callback reads the whole new
    # journal suffix, so a fault consumed by the parent cannot disappear here.
    transport.teardown_check()
