# Security & privacy

This tool is designed for **your own router** diagnostics.

## What it does NOT do

- It does **not** change the router configuration.
- It does **not** attempt to bypass authentication.
- It does **not** upload data anywhere.

## Secret redaction

The collector tries to redact:
- passwords / passphrases
- keys / private keys
- tokens / api keys
- SNMP community strings

Redaction is applied to:
- `ndmc` outputs (including startup/running config)
- captured config/script files

## Before sharing

Even with redaction, the bundle can still contain sensitive metadata:
- MAC addresses
- IP addresses and routes
- hostnames
- Wi‑Fi SSIDs
- client/device names

Always review the archive before sharing.

