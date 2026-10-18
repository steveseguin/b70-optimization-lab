# Native preparation fixes

The first GNU entry compile refused the initial forward-only dispatch header:

```
error: conflicting declaration ‘using integrated::Matrix = using iq3::kopt4::Matrix = using iq3::kopt3::Matrix = struct iq3::kopt2::Matrix’
error: conflicting declaration ‘using integrated::Launch = using iq3::kopt4::Launch = struct iq3::kopt3::Launch’
```

Those names are aliases. The header now forward declares the underlying
`iq3::kopt2::Matrix` and `iq3::kopt3::Launch` types and uses matching aliases.
No kernel arithmetic changed. The failed compile never executed a device.
