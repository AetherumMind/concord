import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# import only base primitives and core — no API agent imports needed for mock tests
from agents.base_agent import BeliefClaim, CounterWeight
from core.debate_engine import DebateEngine, DebateResult
from core.consensus_resolver import ConsensusResolver
from core.receipt_generator import ReceiptGenerator


# ── mock agents (no httpx, no API keys) ─────────────────────────

class MockAgent:
    def __init__(self, agent_id, confidence, evidence_strength, trust_weight=0.85):
        self.agent_id = agent_id
        self.trust_weight = trust_weight
        self._confidence = confidence
        self._evidence_strength = evidence_strength
        self.wins = 0
        self.losses = 0

    async def generate_claim(self, proposition):
        return BeliefClaim(
            agent_id=self.agent_id,
            proposition=proposition,
            confidence=self._confidence,
            evidence_strength=self._evidence_strength,
            reasoning_chain=[
                f"{self.agent_id} identifies core premise",
                f"{self.agent_id} applies evidential weighting",
                f"{self.agent_id} derives conclusion with confidence {self._confidence}",
            ],
        )

    async def generate_counter(self, own_claim, peer_claims):
        counters = []
        for peer in peer_claims:
            agreement = 0.5 if peer.confidence > own_claim.confidence else -0.3
            counters.append(CounterWeight(
                from_agent=self.agent_id,
                targeting_claim_id=peer.claim_id,
                agreement=agreement,
                challenge=f"{self.agent_id} evaluates {peer.agent_id}: evid delta={abs(peer.evidence_strength - own_claim.evidence_strength):.2f}",
                revised_confidence=own_claim.confidence * 0.98,
            ))
        return counters

    def adjust_trust(self, survived):
        if survived:
            self.trust_weight = min(0.98, self.trust_weight + 0.05)
            self.wins += 1
        else:
            self.trust_weight = max(0.40, self.trust_weight - 0.05)
            self.losses += 1


PASS = 0
FAIL = 0

def check(name, condition):
    global PASS, FAIL
    if condition:
        print(f"  PASS  {name}")
        PASS += 1
    else:
        print(f"  FAIL  {name}")
        FAIL += 1


def test_belief_claim_hash():
    c = BeliefClaim(
        agent_id="test", proposition="sky is blue",
        confidence=0.9, evidence_strength=0.85, reasoning_chain=["step1"],
    )
    check("claim_id generated", len(c.claim_id) == 16)
    check("claim_id is hex", all(ch in "0123456789abcdef" for ch in c.claim_id))


def test_belief_claim_deterministic():
    kwargs = dict(agent_id="test", proposition="sky is blue",
                  confidence=0.9, evidence_strength=0.85, reasoning_chain=["step1"])
    c1 = BeliefClaim(**kwargs)
    c2 = BeliefClaim(**kwargs)
    check("deterministic hash", c1.claim_id == c2.claim_id)


async def test_debate_engine():
    agents = [
        MockAgent("claude", confidence=0.87, evidence_strength=0.84),
        MockAgent("gpt-4o", confidence=0.82, evidence_strength=0.91),
    ]
    engine = DebateEngine(agents)
    result = await engine.run("Is epistemic consensus achievable across AI systems?")
    check("two claims generated", len(result.final_claims) == 2)
    check("at least one round ran", result.rounds_run >= 1)
    check("counter-weights produced", len(result.all_counter_weights) > 0)
    check("rounds_run matches list", result.rounds_run == len(result.rounds))
    return result, agents


async def run_consensus_resolver(result, agents):
    resolver = ConsensusResolver(agents)
    consensus = resolver.resolve(result.final_claims, result.all_counter_weights)
    check("winner is valid agent", consensus.winning_agent in ["claude", "gpt-4o"])
    check("integrity score > 0", consensus.integrity_score > 0)
    check("dissent preserved", isinstance(consensus.dissent, list))
    check("rationale non-empty", len(consensus.rationale) > 0)
    check("higher evidence wins (gpt-4o)", consensus.winning_agent == "gpt-4o")
    return consensus


async def test_trust_adjustment():
    agents = [
        MockAgent("claude", confidence=0.87, evidence_strength=0.84),
        MockAgent("gpt-4o", confidence=0.82, evidence_strength=0.91),
    ]
    engine = DebateEngine(agents)
    result = await engine.run("Trust weight adjustment test")
    resolver = ConsensusResolver(agents)
    consensus = resolver.resolve(result.final_claims, result.all_counter_weights)
    winner = next(a for a in agents if a.agent_id == consensus.winning_agent)
    loser  = next(a for a in agents if a.agent_id != consensus.winning_agent)
    check("winner trust increased", winner.trust_weight > 0.85)
    check("loser trust decreased",  loser.trust_weight  < 0.85)


async def run_receipt(result, consensus):
    gen = ReceiptGenerator()
    receipt = gen.generate(
        "Is epistemic consensus achievable across AI systems?",
        result, consensus,
        ledger_hash="phase1-mock-no-ledger",
    )
    check("header present",        "CONCORD CONSENSUS RECEIPT" in receipt)
    check("consensus block",       "CONSENSUS:" in receipt)
    check("counter-weights block", "COUNTER-WEIGHTS:" in receipt)
    check("agent reasoning block", "AGENT REASONING:" in receipt)
    check("dissent block",         "DISSENT" in receipt)
    return receipt


async def run_all():
    print()
    print("=" * 64)
    print("CONCORD — PHASE 1 TEST SUITE")
    print("=" * 64)
    print()

    print("[ belief claim ]")
    test_belief_claim_hash()
    test_belief_claim_deterministic()
    print()

    print("[ debate engine ]")
    result, agents = await test_debate_engine()
    print()

    print("[ consensus resolver ]")
    consensus = await run_consensus_resolver(result, agents)
    print()

    print("[ trust adjustment ]")
    await test_trust_adjustment()
    print()

    print("[ receipt generator ]")
    receipt = await run_receipt(result, consensus)
    print()

    print("=" * 64)
    print(f"RESULTS: {PASS} passed  {FAIL} failed")
    print("=" * 64)
    print()
    print(receipt)


if __name__ == "__main__":
    asyncio.run(run_all())
