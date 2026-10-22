# emSign incident certificate fixtures

Public certificates only, downloaded 2026-10-22 from https://emudhra.we-have-a-problem.com/.

- `chains.zip` SHA256: `8a2edc81b6c51e3ad27d45ca1e441ec84c961e2dee0fc547f2a02c0f74315f95`; all 12 TLS chains retained, including AAA cross-signs.
- `roots.pem`: the four records from `roots.json`; SHA256 `4c4636738b19d1d46e7cb42ba259989d93f6e4908e5de4b5b8a31f34c710f231`.
- `shared/security/emudhra_intermediates.pem`: all 16 records from `impacted-intermediates.json`; each DER fingerprint checked against the publisher, 8 distinct public keys; SHA256 `c6bef0a3d76e4065f63e3bb83932f28a02bc8bc69a6a27a7481310cbb7be393e`.

The root bundle is an intentionally unsafe positive control, never a runtime trust store. Offline tests fix the verification time to 2026-10-22 so future certificate expiry cannot turn an acceptance control into a false pass.
