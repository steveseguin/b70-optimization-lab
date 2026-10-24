# Native symbol inventory retention

`build-1792803527629726162/native-symbols.log` retains the complete
5,266,504-byte symbol inventory for this candidate. The build checker and
independent reviewer consume it to verify the linked future Engine and SYCL
registration. Keep the complete context with the source snapshots and receipt.

Restore the exact log from Git and verify its recorded hash. Regeneration uses
`nm -C --defined-only` on the exact binary hashed in `build-compile-only.json`;
a rebuild with different bytes is a separate artifact. Neither operation
invokes the native executable.

Repository hygiene reports this one size warning and zero errors. The prior
failed CPU attempts and earlier successful proof remain retained separately.
