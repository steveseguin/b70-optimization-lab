"""Pure text detector for kernel journal faults; no process or device operations.

Additive to the original GPU pattern. Host signatures name actual kernel
watchdog/RCU/hung-task reports; ordinary uses of "hang", "stall", or "blocked"
are intentionally insufficient. This is a detector, not a recovery policy.
"""
import re

GPU_PATTERN = r'Fault response|CAT error|engine reset|GPU HANG|GuC.*reset|coredump'
HOST_PATTERNS = {
    'soft_lockup': r'\bBUG:[ \t]+soft lockup[ \t]+-[ \t]+CPU#\d+[ \t]+stuck for[ \t]+\d+(?:\.\d+)?s!',
    'rcu_stall': r'\bINFO:[ \t]+rcu_(?:preempt|sched|bh|tasks(?:_rude|_trace)?)[ \t]+(?:self-)?detected[ \t]+(?:expedited[ \t]+)?stalls?[ \t]+on[ \t]+(?:CPUs?(?:/tasks)?|tasks)\b',
    'rcu_kthread_starved': r'\brcu_(?:preempt|sched|bh|tasks(?:_rude|_trace)?)[ \t]+kthread starved for[ \t]+\d+[ \t]+jiffies\b',
    'hung_task': r'\bINFO:[ \t]+task[ \t]+[^\r\n]+:\d+[ \t]+blocked for more than[ \t]+\d+(?:\.\d+)?[ \t]+seconds\.',
}
FAULT = re.compile('|'.join([GPU_PATTERN, *HOST_PATTERNS.values()]), re.I)


def matching_lines(text):
    """Return first-match evidence per matching line; never probe the live host."""
    result = []
    gpu = re.compile(GPU_PATTERN, re.I)
    hosts = [(name, re.compile(pattern, re.I)) for name, pattern in HOST_PATTERNS.items()]
    for number, line in enumerate(text.splitlines(), 1):
        if not FAULT.search(line):
            continue
        kinds = [name for name, pattern in hosts if pattern.search(line)]
        if gpu.search(line):
            kinds.append('legacy_gpu_or_coredump')
        result.append({'line_number': number, 'kinds': kinds, 'line': line})
    return result
