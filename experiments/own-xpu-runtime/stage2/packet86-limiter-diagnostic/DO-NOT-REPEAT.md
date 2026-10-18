# Packet86 boundaries

| Method | Boundary |
| --- | --- |
| Promote a non-exact limiter view | Always forbidden, including its production control |
| Drop loads whose decoded values are unused | Invalid comparison; retain reads and use loadkeep controls |
| Sum ablation savings | Invalid: mechanisms overlap and downstream state changes |
| Call onecached a measured DRAM/cache split | Unsupported without device/counter evidence |
| Treat a token mismatch as a device fault in a non-exact view | Record diagnostic output mismatch; retain every other safety check |
| Treat protocol, memory, numerical or drain failure as expected mismatch | Forbidden; fail normally |
| Infer missing corrected-path cost as zero | Keep it missing; report speculative/corrected paths separately |
| Edit packet75, packet77, shared wrappers or live queue | Outside this task; copies/new proposals only |
