from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import hashlib
import json


@dataclass
class BeliefClaim:
    agent_id: str
    proposition: str
    confidence: float
    evidence_strength: float
    reasoning_chain: list
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    sequence_number: int = 0
    claim_id: str = ""
    citations: list = field(default_factory=list)

    def __post_init__(self):
        if not self.claim_id:
            payload = json.dumps({
                "agent_id": self.agent_id,
                "proposition": self.proposition,
                "confidence": self.confidence,
                "evidence_strength": self.evidence_strength,
                "reasoning_chain": self.reasoning_chain,
            }, sort_keys=True)
            self.claim_id = hashlib.sha256(payload.encode()).hexdigest()[:16]


@dataclass
class CounterWeight:
    from_agent: str
    targeting_claim_id: str
    agreement: float
    challenge: str
    revised_confidence: float
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class BaseAgent(ABC):
    def __init__(self, agent_id: str, trust_weight: float = 0.85):
        self.agent_id = agent_id
        self.trust_weight = trust_weight
        self.wins = 0
        self.losses = 0

    @abstractmethod
    async def generate_claim(self, proposition: str) -> BeliefClaim:
        pass

    @abstractmethod
    async def generate_counter(
        self,
        own_claim: BeliefClaim,
        peer_claims: list
    ) -> list:
        pass

    def adjust_trust(self, survived: bool):
        if survived:
            self.trust_weight = min(0.98, self.trust_weight + 0.05)
            self.wins += 1
        else:
            self.trust_weight = max(0.40, self.trust_weight - 0.05)
            self.losses += 1

    def __repr__(self):
        return f"<{self.agent_id} trust={self.trust_weight:.2f}>"
