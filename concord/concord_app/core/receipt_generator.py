from datetime import datetime


class ReceiptGenerator:
    def generate(
        self,
        proposition: str,
        debate_result,
        consensus,
        ledger_hash: str = "no-ledger"
    ) -> str:
        lines = []
        lines.append("=" * 64)
        lines.append("CONCORD CONSENSUS RECEIPT")
        lines.append(f"Timestamp:   {datetime.utcnow().isoformat()}")
        lines.append(f"Ledger hash: {ledger_hash}")
        lines.append("=" * 64)
        lines.append(f"PROPOSITION: {proposition}")
        lines.append("")
        lines.append(f"DEBATE ROUNDS RUN: {debate_result.rounds_run}")
        lines.append(f"CONVERGED:         {debate_result.converged}")
        lines.append("")
        lines.append("AGENT REASONING:")
        for claim in debate_result.final_claims:
            lines.append(f"  [{claim.agent_id}]")
            lines.append(f"    Claim ID:          {claim.claim_id}")
            lines.append(f"    Confidence:        {claim.confidence:.2f}")
            lines.append(f"    Evidence strength: {claim.evidence_strength:.2f}")
            lines.append(f"    Reasoning chain:")
            for i, step in enumerate(claim.reasoning_chain, 1):
                lines.append(f"      {i}. {step}")
        lines.append("")
        lines.append("COUNTER-WEIGHTS:")
        for cw in debate_result.all_counter_weights:
            lines.append(
                f"  {cw.from_agent} -> {cw.targeting_claim_id}: "
                f"agreement={cw.agreement:.2f} | {cw.challenge}"
            )
        lines.append("")
        lines.append("CONSENSUS:")
        lines.append(f"  Winner:          {consensus.winning_agent}")
        lines.append(f"  Claim ID:        {consensus.winning_claim.claim_id}")
        lines.append(f"  Integrity score: {consensus.integrity_score:.4f}")
        lines.append(f"  Rationale:       {consensus.rationale}")
        lines.append("")
        if consensus.dissent:
            lines.append("DISSENT (preserved):")
            for d in consensus.dissent:
                lines.append(
                    f"  [{d.agent_id}] conf={d.confidence:.2f} "
                    f"evid={d.evidence_strength:.2f}"
                )
        lines.append("=" * 64)
        return "\n".join(lines)
