"""Owned exact fault/deleted expressions copied from the coordinator driver."""
import re
FAULT = re.compile(r'Fault response|CAT error|engine.*reset|reset.*engine|GPU HANG|'
                   r'GuC.*reset|coredump|timed.?out job|job[^\n]*timed\s*out|wedged|'
                   r'hard LOCKUP|soft lockup|Hardware Error', re.I)
DELETED = re.compile(r'coredump has been deleted', re.I)
