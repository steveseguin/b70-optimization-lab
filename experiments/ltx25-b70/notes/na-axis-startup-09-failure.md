# Decoder packet09 startup pin failure

2026-09-14. The controlled application transition completed: packet08 PID66846
exited0 after one SIGINT; packet09 PID82046 started in exec49702. The computer
remained on boot `8e4b1b65-1c38-47bb-8ca5-e4fd6bbdf94a`. Four startup XPU
copy/compute checks and strict determinism passed. No computer reboot, driver
reset, power/memory-setting changes, or restart loop occurred.

Startup endpoint admission failed because `LTXNAAxisDecode` was absent from
`/object_info/LTXNAAxisDecode`. Comfy logged and swallowed the custom-node
import error `Original VAE decode source differs`. No native clip campaign
started and the router installation line was not reached. The application
remains idle while the integration is corrected offline. This is an integration
failure, with no recorded device fault or numerical result.

The node incorrectly pinned upstream `comfy/sd.py` SHA
`3eba634a7311bc51cf19c54b12c91149306fe71ae28fa37744e36cfb9290f00a`.
The sealed source inherited from packet08 is
`41cbf195657cc81a60173f13f192966c4276bf7931a6c10f75870a66c59546b0`.
The difference is the previously preserved five-line CLIP small-state option
propagation, not a VAE decoding change. Other startup dependency pins match.

The preparation checks verified individual artifact hashes but failed to
compare the node's constants with the inherited files. The earlier CPU node
tests exercised `create_node_class`, bypassing environment-driven `initialize`.
The native endpoint admission correctly prevented requests, but the mismatch
should have been caught before application reload.

The original packet09, builder, node, client and test evidence remain intact.
The successor [node](../scripts/na_axis_decode_node_v2.py) corrects SD_SHA and
reports the individual module on a source mismatch; no decode logic changes.
The new [stdlib startup test](../scripts/test-na-axis-startup-stdlib.py)
executes the real environment-driven initialize path against actual sealed
source filenames, using module/router/context stubs. Its eight groups reproduce
the old failure, register the corrected class once, reject changed source and
identity/context, and prove every rejection precedes router installation.
[Test receipt](../data/na-axis-startup-stdlib-01.json). It does not prove native
startup or clip equality. The successor builder also needs cross-file pin
closure before sealing, followed by independent review and native admission.

[Migration evidence](../data/na-axis-migration-09/startup-failure.json) includes
the old exit, new identity, full startup log and empty queue. A first read-only
migration preflight had used system Python and refused missing Torch package
metadata before any signal; the pinned venv then passed and sent one SIGINT.

No speed conclusion or promotion is possible. The next bounded experiment is
still the original/cache/original decoder comparison under the unchanged
256×256,25-frame,24fps,BF16,8+3-step recipe and all four raw-output oracles.
