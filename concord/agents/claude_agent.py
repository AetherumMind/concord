import httpx
import json
import os
from .base_agent import BaseAgent, BeliefClaim, CounterWeight


CLAIM_PROMPT = """You are a reasoning agent in a multi-agent consensus system.

Analyze this proposition and respond ONLY with valid JSON matching this structure:
{{
  "confidence": <float 0.0-1.0>,
  "evidence_strength": <float 0.0-1.0>,
  "reasoning_chain": ["step 1", "step 2", "step 3"],
  "citations": []
}}

Proposition: {proposition}

Rules:
- confidence: how confident you are in your position
- evidence_strength: how strong the evidence supporting your position is
- reasoning_chain: 3-5 discrete logical steps
- Return ONLY the JSON object, no other text"""


COUNTER_PROMPT = """You are a reasoning agent reviewing peer claims in a consensus system.

Your own claim:
{own_claim}

Peer claims to evaluate:
{peer_claims}

Respond ONLY with valid JSON as a list of counter-weights:
[
  {{
    "targeting_claim_id": "<claim_id>",
    "agreement": <float -1.0 to 1.0>,
    "challenge": "<specific logical challenge or agreement reason>",
    "revised_confidence": <your revised confidence float 0.0-1.0>
  }}
]

Rules:
- agreement: -1.0 = completely disagree, 0 = neutral, 1.0 = completely agree
- challenge: be specific about the logical strength or weakness
- revised_confidence: update your own confidence after seeing peer reasoning
- Return ONLY the JSON array, no other text"""


class ClaudeAgent(BaseAgent):
    def __init__(self, api_key: str = None, trust_weight: float = 0.85):
        super().__init__(agent_id="claude", trust_weight=trust_weight)
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = "claude-sonnet-4-20250514"
        self.base_url = "https://api.anthropic.com/v1/messages"

    async def _call(self, prompt: str) -> str:
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": self.model,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        }
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(self.base_url, headers=headers, json=payload)
            r.raise_for_status()
            return r.json()["content"][0]["text"]

    async def generate_claim(self, proposition: str) -> BeliefClaim:
        prompt = CLAIM_PROMPT.format(proposition=proposition)
        raw = await self._call(prompt)
        data = json.loads(raw.strip())
        return BeliefClaim(
            agent_id=self.agent_id,
            proposition=proposition,
            confidence=data["confidence"],
            evidence_strength=data["evidence_strength"],
            reasoning_chain=data["reasoning_chain"],
            citations=data.get("citations", []),
        )

    async def generate_counter(self, own_claim: BeliefClaim, peer_claims: list) -> list:
        own_str = json.dumps({
            "claim_id": own_claim.claim_id,
            "proposition": own_claim.proposition,
            "confidence": own_claim.confidence,
            "reasoning_chain": own_claim.reasoning_chain,
        }, indent=2)
        peers_str = json.dumps([{
            "claim_id": c.claim_id,
            "agent_id": c.agent_id,
            "proposition": c.proposition,
            "confidence": c.confidence,
            "evidence_strength": c.evidence_strength,
            "reasoning_chain": c.reasoning_chain,
        } for c in peer_claims], indent=2)
        prompt = COUNTER_PROMPT.format(own_claim=own_str, peer_claims=peers_str)
        raw = await self._call(prompt)
        data = json.loads(raw.strip())
        return [
            CounterWeight(
                from_agent=self.agent_id,
                targeting_claim_id=item["targeting_claim_id"],
                agreement=item["agreement"],
                challenge=item["challenge"],
                revised_confidence=item["revised_confidence"],
            ) for item in data
        ]
