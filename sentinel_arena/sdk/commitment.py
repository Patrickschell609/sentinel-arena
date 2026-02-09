"""
SENTINEL Commitment - SHA256 hash commitment for audit trail.

Every SENTINEL decision produces a cryptographic commitment:
  SHA256(score | action | timestamp | model_id)

This proves the decision was made at a specific time with a specific
score, and wasn't tampered with after the fact.
"""

import hashlib
import json
from datetime import datetime, timezone
from dataclasses import dataclass, asdict


@dataclass
class Commitment:
    """An auditable commitment to a SENTINEL decision."""
    score: float
    action: str
    model_id: str
    timestamp: str
    input_hash: str
    commitment_hash: str

    def to_dict(self) -> dict:
        return asdict(self)


def commit_action(
    score: float,
    action: str,
    model_id: str,
    input_text: str = "",
) -> Commitment:
    """
    Create a SHA256 commitment for a SENTINEL decision.

    Args:
        score: The extracted score [0.0, 1.0]
        action: The resolved action string
        model_id: The model that produced the score
        input_text: The original input (hashed, not stored)

    Returns:
        A Commitment with the hash.
    """
    ts = datetime.now(timezone.utc).isoformat()

    # Hash the input separately (don't store raw text)
    input_hash = hashlib.sha256(input_text.encode()).hexdigest()[:16]

    # Build the commitment payload
    payload = json.dumps({
        "score": round(score, 6),
        "action": action,
        "model_id": model_id,
        "timestamp": ts,
        "input_hash": input_hash,
    }, sort_keys=True)

    commitment_hash = hashlib.sha256(payload.encode()).hexdigest()

    return Commitment(
        score=round(score, 6),
        action=action,
        model_id=model_id,
        timestamp=ts,
        input_hash=input_hash,
        commitment_hash=commitment_hash,
    )
