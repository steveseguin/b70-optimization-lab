# Packet201 fixed streaming qualification client

The16 packet200 messages, prompt IDs, output caps and session relationships are
preserved. Session names change from p200 to p201. Seven rows use SSE: a-park,
a-chat-append, a-chat-fresh, names, json, unicode and b-final. The other9 use
ordinary JSON. No request is retried. Health/models and one invalid-sampling
request precede the16 valid turns and must not consume a native RUN.

The five original full-length token oracles and resumed/fresh pair remain.
Separately, all16 rows bind the actual p200 consumed prompt IDs, complete output
IDs, displayed text, finish reason and usage. This baseline totals1484 tokens,
including native early stops; it is not silently padded to the1728-token cap.
The32 p200 HTTP/native files and original vector sources are hash checked before
intake. Client success does not itself claim control completion or device drain.

SSE consumption uses bounded `read1` chunks and a bounded line buffer, strict UTF-8, unique JSON keys and
stable response ID/model/created fields. One assistant-role frame precedes content;
one terminal usage frame precedes one `[DONE]`, followed by EOF with no trailing
bytes. Integer usage and exact native text/tokens are checked. The socket is
retained before `getresponse()` because HTTP/1.0 detaches `connection.sock`;
each subsequent read receives the remaining900-second total receive deadline,
including trickled partial lines. The response object is explicitly closed before
the connection, including on parser errors, while preserving the original error.
Missing/invalid final markers, unexpected data or transport failures preserve
bounded partial raw bytes and stop further requests. Only successful disposition
in the pinned server can emit the final markers; the outer worker/client join
must additionally prove both processes exit0 before restoration.

Raw SSE is base64 inside the existing per-turn HTTP JSON. Complete-frame receive
offsets describe client-observed delivery only, never native token-generation
latency. No timing or speed record is claimed. Raw SSE is capped at128KiB, lines
at8192 bytes, frames at output-cap+4, each JSON artifact at256KiB, and the complete
client writer at1MiB/40files. There are37 normal-success files. Initial CPU replay
used about295KB for the1484-token baseline and373KB for a1728-token cap replay
using the largest escaped display piece among the baseline tokens. These are
replay estimates, not a proof for arbitrary output. The hard total refuses any
overflow and leaves an incident instead of raising the storage forecast.

The focused CPU tests use actual pinned codec/token bytes, intercepted native
results and a temporary HTTP/1.0 loopback socket. They cover early incremental
consumption, malformed UTF-8/JSON/identity/terminal sequences, receive deadlines,
partial persistence and original-error retention. No model/native owner, real
endpoint or fresh worker plan is invoked. The outer driver and restore adapter
must require16 exact p200 matches,7 successful SSE sequences,9 ordinary replies,
the original5 oracles,1 pair, clean worker/client exits and physical drain.
