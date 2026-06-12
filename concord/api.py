from fastapi import FastAPI
from pydantic import BaseModel
import os

from agents import get_claude_agent, get_gpt_agent
from core import DebateEngine, ConsensusResolver, ReceiptGenerator

app = FastAPI()

class Question(BaseModel):
    prompt: str

@app.post("/ask")
async def ask(q: Question):
    key_claude = os.environ.get("ANTHROPIC_API_KEY", "")
    key_gpt = os.environ.get("OPENAI_API_KEY", "")

    agents = [
        get_claude_agent()(api_key=key_claude),
        get_gpt_agent()(api_key=key_gpt),
    ]

    debate = await DebateEngine(agents).run(q.prompt)
    consensus = ConsensusResolver(agents).resolve(
        debate.final_claims, debate.all_counter_weights
    )
    receipt = ReceiptGenerator().generate(q.prompt, debate, consensus)

    return {
        "question": q.prompt,
        "winner": consensus.winning_agent,
        "rationale": consensus.rationales,
        "receipt": receipt,
    }
from fastapi import FastAPI
from pydantic import BaseModel
import os

from agents import get_claude_agent, get_gpt_agent
from core import DebateEngine, ConsensusResolver, ReceiptGenerator

app = FastAPI()

class Question(BaseModel):
    prompt: str

@app.post("/ask")
async def ask(q: Question):
    key_claude = os.environ.get("ANTHROPIC_API_KEY")
    key_gpt = os.environ.get("OPENAI_API_KEY")

    agents = [
        get_claude_agent()(api_key=key_claude),
        get_gpt_agent()(api_key=key_gpt),
    ]

    debate = await DebateEngine(agents).run(q.prompt)

    consensus = ConsensusResolver(agents).resolve(
        debate.final_claims,
        debate.all_counter_weights
    )

    receipt = ReceiptGenerator().generate(
        q.prompt,
        debate,
        consensus
    )

    return {
        "question": q.prompt,
        "winner": consensus.winning_agent,
        "rationale": consensus.rationales,
        "receipt": receipt,
    }
