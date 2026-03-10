"""Central planner LLM client for memory operations (compaction, nudge summarization).

Ref: openclaw/src/agents/compaction.ts (summarizeWithFallback — OpenAI chat completions
with system+user messages). Adopted: async SDK call pattern, model as parameter.
"""

from openai import AsyncOpenAI


async def call_planner(
    system_prompt: str,
    user_prompt: str,
    model: str = "gpt-4.1-mini",
) -> str:
    """Call planner LLM for memory operations (compaction, nudge summarization).

    Uses OpenAI Python SDK. Respects OPENAI_API_KEY and OPENAI_API_BASE env vars.
    Raises on API failure (caller decides fallback behavior).
    """
    client = AsyncOpenAI()
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content
