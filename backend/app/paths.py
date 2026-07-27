"""Resolve product data root for open-source packaging.

Env (first match wins):
  ``ATA_HOME`` → ``{home}/.ai_attestation/``
Else: ``<repo>/data/`` next to ``backend/``.
"""

from __future__ import annotations

import os
from pathlib import Path


def product_data_root(*, sub: str = "") -> Path:
    home = (os.environ.get("ATA_HOME") or "").strip()
    if home:
        root = Path(home).expanduser() / ".ai_attestation"
    else:
        # backend/app -> repo/data
        root = Path(__file__).resolve().parents[2] / "data"
    if sub:
        root = root / sub
    root.mkdir(parents=True, exist_ok=True)
    return root
