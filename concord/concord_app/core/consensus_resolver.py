from dataclasses import dataclass, field
from agents.base_agent import BeliefClaim, CounterWeight


@dataclass
class ResolvedConsensus:
    winning_claim: BeliefClaim
    winning_agent: str
    dissent: list
    integrity_score: float
    rationale: str


class ConsensusResolver:
    def __init__(self, agents: list):
        self.agents = {a.agent_id: a for a in agents}

    def resolve(self, final_claims: list, all_counter_weights: list) -> ResolvedConsensus:
        scored = []
        for claim in final_claims:
            agent = self.agents.get(claim.agent_id)
            trust = agent.trust_weight if agent else 0.85

            peer_agreements = [
                cw.agreement for cw in all_counter_weights
                if cw.targeting_claim_id == claim.claim_id
            ]
            avg_agreement = (
                sum(peer_agreements) / len(peer_agreements)
                if peer_agreements else 0.0
            )

            # evidence_strength is primary signal (80%)
            # confidence is secondary (15%), peer agreement minor (5%)
            integrity = (
                claim.evidence_strength * trust * 0.80
                + claim.confidence * trust * 0.15
                + avg_agreement * 0.05
            )
            scored.append((claim, integrity, trust))

        # deterministic sort: integrity → evidence_strength → trust → claim_id
        scored.sort(key=lambda x: (
            -x[1],
            -x[0].evidence_strength,
            -x[2],
            x[0].claim_id,
        ))

        winner, winner_score, _ = scored[0]
        dissent = [c for c, _, _ in scored[1:]]

        for agent_id, agent in self.agents.items():
            agent.adjust_trust(agent_id == winner.agent_id)

        rationale = (
            f"{winner.agent_id} claim {winner.claim_id} won. "
            f"Integrity score: {winner_score:.4f}. "
            f"Evidence strength: {winner.evidence_strength:.2f}. "
            f"Final confidence: {winner.confidence:.2f}."
        )

        return ResolvedConsensus(
            winning_claim=winner,
            winning_agent=winner.agent_id,
            dissent=dissent,
            integrity_score=winner_score,
            rationale=rationale,
        )
