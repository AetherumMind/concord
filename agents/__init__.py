from .base_agent import BaseAgent, BeliefClaim, CounterWeight

__all__ = ["BaseAgent", "BeliefClaim", "CounterWeight"]


def get_claude_agent():
    from .claude_agent import ClaudeAgent
    return ClaudeAgent


def get_gpt_agent():
    from .gpt_agent import GPTAgent
    return GPTAgent
