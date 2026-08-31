# Qwen3.8 active packaged GDN stage trace D38 result

D38 is **technical-invalid**. The first request returned no token/content events
in 0.106 seconds and the target trace was absent. The pre-D38 runner saved
server logs only after confirming a trace, so its fail path removed the
container without preserving the request exception.

The generic trace runner now saves container logs before failing a missing
trace. D38r repeats one process first under the same frozen mechanism. Only if
that request succeeds does a four-process causal comparison make sense.
