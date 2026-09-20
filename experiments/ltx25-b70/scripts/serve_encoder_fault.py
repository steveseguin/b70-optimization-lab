"""The sealed launcher's kernel fault detector, shared with the admission tools."""
import re

FAULT = re.compile(
    r'Fault response|CAT error|engine reset|GPU HANG|GuC.*reset|coredump|'
    r'\bBUG:[ \t]+soft lockup[ \t]+-[ \t]+CPU#\d+[ \t]+stuck for[ \t]+\d+(?:\.\d+)?s!|'
    r'\bINFO:[ \t]+rcu_(?:preempt|sched|bh|tasks(?:_rude|_trace)?)[ \t]+(?:self-)?detected[ \t]+(?:expedited[ \t]+)?stalls?[ \t]+on[ \t]+(?:CPUs?(?:/tasks)?|tasks)\b|'
    r'\brcu_(?:preempt|sched|bh|tasks(?:_rude|_trace)?)[ \t]+kthread starved for[ \t]+\d+[ \t]+jiffies\b|'
    r'\bINFO:[ \t]+task[ \t]+[^\r\n]+:\d+[ \t]+blocked for more than[ \t]+\d+(?:\.\d+)?[ \t]+seconds\.'
    , re.I)
