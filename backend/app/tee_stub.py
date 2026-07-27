"""Exploratory TEE (Trusted Execution Environment) prototype notes.

Status: exploratory — NOT productized. No production enclave deployment.

Goal
----
Prove that even platform operators cannot silently alter attestation /
hash-chain generation because critical logic runs in hardware-isolated
enclaves (AWS Nitro Enclaves, Intel SGX, or equivalent).

MVP choice
----------
We do **not** ship a live Nitro/SGX binary in this repository. Reasons:
- Enclave build/CI needs specialized AMIs, nitro-cli, and signing keys.
- Local developer machines cannot run Nitro Enclaves.
- Cost and ops complexity exceed MVP scope (explicit non-goal).

What we ship instead
--------------------
1. This document + `tee_attestation_stub()` used by verify packs when
   `ATA_TEE_MODE=exploratory` is set.
2. A clear attestation document shape that a future enclave worker would
   populate (PCR measurements, signature, module hash).
3. Compliance / verify UI surfaces a "TEE 证明（探索性）" section only when
   a stub or real attestation is present — never claims production TEE.

Hypothetical architecture (future)
----------------------------------
```
Client → API (untrusted) → Enclave worker
                              ├─ metering + chain hash
                              ├─ returns {chain_hash, attestation_doc}
                              └─ host cannot read enclave memory
Public verifier checks attestation_doc against manufacturer roots.
```

Exit criteria to leave "exploratory"
------------------------------------
- [ ] Enclave image builds in CI
- [ ] Attestation document verifies offline against AWS/Intel roots
- [ ] Hash-chain append path only accepted when attestation matches
- [ ] Ops runbook + key ceremony documented

Until then: treat any TEE field as a prototype marker, not a security claim.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from attestation import sha256_text, utc_now


def tee_attestation_stub(
    *,
    module: str = "attestation_chain",
    payload_hash: str = "",
) -> Optional[Dict[str, Any]]:
    """Return exploratory TEE stub when ATA_TEE_MODE=exploratory; else None."""
    mode = os.environ.get("ATA_TEE_MODE", "").strip().lower()
    if mode not in ("exploratory", "1", "true", "stub"):
        return None
    ts = utc_now()
    doc_hash = sha256_text(f"tee-stub|{module}|{payload_hash}|{ts}")
    return {
        "status": "exploratory",
        "platform": "stub-not-enclave",
        "module": module,
        "payload_hash": payload_hash,
        "timestamp": ts,
        "attestation_document_hash": doc_hash,
        "note": (
            "Exploratory stub only. Not hardware-attested. "
            "See docs/tee_exploratory.md"
        ),
        "verify_method": (
            "Production path would verify manufacturer-signed attestation; "
            "this stub only proves the field shape."
        ),
    }
