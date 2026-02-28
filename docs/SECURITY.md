# Security / Sensitive data

## Modes

### FULL (default)
- Maximum capture.
- May include passwords, tokens, private keys, certificates, Wi‑Fi PSK, PPPoE credentials, etc.

### SAFE
- Attempts to reduce the most sensitive captures (best‑effort).
- Still **not a guarantee**: configs may contain secrets in unexpected places.

## Sensitive locations list

The probe generates:

- `analysis/SENSITIVE_LOCATIONS.md`

It includes:
- file paths,
- match type (pattern),
- line numbers (best‑effort).

Use it to mask secrets before sharing archives.

## Recommendation

If you want to share data publicly:
1) prefer `--mode safe`;
2) manually review `analysis/SENSITIVE_LOCATIONS.md`;
3) remove/mask secrets;
4) re-pack the archive.
