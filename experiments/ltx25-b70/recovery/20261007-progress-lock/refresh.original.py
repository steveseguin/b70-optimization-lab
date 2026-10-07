def refresh(self, nolock=False, lock_args=None):
    """
    Force refresh the display of this bar.

    Parameters
    ----------
    nolock  : bool, optional
        If `True`, does not lock.
        If [default: `False`]: calls `acquire()` on internal lock.
    lock_args  : tuple, optional
        Passed to internal lock's `acquire()`.
        If specified, will only `display()` if `acquire()` returns `True`.
    """
    if self.disable:
        return

    if not nolock:
        if lock_args:
            if not self._lock.acquire(*lock_args):
                return False
        else:
            self._lock.acquire()
    self.display()
    if not nolock:
        self._lock.release()
    return True
