import asyncio
from dataclasses import dataclass, field
from agents.base_agent import BeliefClaim, CounterWeight


CONVERGENCE_DELTA = 0.05
MAX_ROUNDS = 3


@dataclass
class DebateRound:
    round_number: int
    claims: list
    counter_weights: list
    converged: bool = False


@dataclass
class DebateResult:
    rounds: list = field(default_factory=list)
    final_claims: list = field(default_factory=list)
    all_counter_weights: list = field(default_factory=list)
    converged: bool = False
    rounds_run: int = 0


class DebateEngine:
    def __init__(self, agents: list):
        self.agents = agents

    async def run(self, proposition: str) -> DebateResult:
        result = DebateResult()
        claims = await self._generate_claims(proposition)
        result.final_claims = claims
        prev_confidences = {c.agent_id: c.confidence for c in claims}

        for round_num in range(1, MAX_ROUNDS + 1):
            counters = await self._generate_counters(claims)
            result.all_counter_weights.extend(counters)

            for cw in counters:
                for claim in claims:
                    if claim.agent_id == cw.from_agent:
                        claim.confidence = cw.revised_confidence

            new_confidences = {c.agent_id: c.confidence for c in claims}
            converged = self._check_convergence(prev_confidences, new_confidences)

            result.rounds.append(DebateRound(
                round_number=round_num,
                claims=list(claims),
                counter_weights=list(counters),
                converged=converged,
            ))
            result.rounds_run = round_num

            if converged:
                result.converged = True
                break

            prev_confidences = new_confidences

        result.final_claims = claims
        return result

    async def _generate_claims(self, proposition: str) -> list:
        tasks = [agent.generate_claim(proposition) for agent in self.agents]
        return list(await asyncio.gather(*tasks))

    async def _generate_counters(self, claims: list) -> list:
        all_counters = []
        tasks = []
        for agent in self.agents:
            own_claim = next(c for c in claims if c.agent_id == agent.agent_id)
            peer_claims = [c for c in claims if c.agent_id != agent.agent_id]
            tasks.append(agent.generate_counter(own_claim, peer_claims))
        results = await asyncio.gather(*tasks)
        for counters in results:
            all_counters.extend(counters)
        return all_counters

    def _check_convergence(self, prev: dict, curr: dict) -> bool:
        for agent_id in prev:
            if agent_id not in curr:
                continue
            if abs(prev[agent_id] - curr[agent_id]) > CONVERGENCE_DELTA:
                return False
        return True
