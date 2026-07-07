"""
Provider-agnostic LLM client wrapper, shared by every agent that touches an
LLM (Intake extraction, Summarizer translation, Peer-Review rationale —
never decision-making; see rule 1 in CLAUDE.md).

Provider is selected at call time via LLM_PROVIDER (default: "gemini"):
  - "gemini"          -> Google Gemini, reads GEMINI_API_KEY
  - "openai"          -> OpenAI, reads OPENAI_API_KEY
  - "bedrock_claude"  -> Claude via AWS Bedrock, reads standard AWS
                         credentials (env vars / profile / instance role)

`generate_text` is the single entry point every agent should call — it
returns the raw text of the model's reply regardless of provider, so
callers (e.g. peer_review_agent.generate_rationale) don't need to know
which backend served the request.
"""
import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[3] / ".env")

DEFAULT_TIMEOUT_SECONDS = float(os.environ.get("LLM_TIMEOUT_SECONDS", "10"))
_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="llm-call")


class LLMTimeoutError(TimeoutError):
    """Raised when a generate_text call exceeds its timeout.

    // DEMO-REAL: every LLM call in this system goes through generate_text, so
    every call site inherits this timeout. Per CLAUDE.md's reliability rules,
    callers must catch this (or Exception generally) and fail SAFE — i.e.
    route to human review — never treat a timeout as success.
    """

DEFAULT_PROVIDER = os.environ.get("LLM_PROVIDER", "gemini").lower()

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
BEDROCK_CLAUDE_MODEL = os.environ.get(
    "BEDROCK_CLAUDE_MODEL", "anthropic.claude-sonnet-4-5-20250929-v1:0"
)
BEDROCK_REGION = os.environ.get("AWS_REGION", "us-east-1")

_gemini_client = None
_openai_client = None
_bedrock_client = None


def _get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        from google import genai

        _gemini_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _gemini_client


def _get_openai_client():
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI

        _openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    return _openai_client


def _get_bedrock_client():
    global _bedrock_client
    if _bedrock_client is None:
        from anthropic import AnthropicBedrock

        _bedrock_client = AnthropicBedrock(aws_region=BEDROCK_REGION)
    return _bedrock_client


def _generate_gemini(system_prompt: str, user_content: str, max_tokens: int) -> str:
    from google.genai import types

    client = _get_gemini_client()
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=user_content,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=max_tokens,
        ),
    )
    return response.text.strip()


def _generate_openai(system_prompt: str, user_content: str, max_tokens: int) -> str:
    client = _get_openai_client()
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    )
    return response.choices[0].message.content.strip()


def _generate_bedrock_claude(system_prompt: str, user_content: str, max_tokens: int) -> str:
    client = _get_bedrock_client()
    response = client.messages.create(
        model=BEDROCK_CLAUDE_MODEL,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}],
    )
    return response.content[0].text.strip()


_PROVIDERS = {
    "gemini": _generate_gemini,
    "openai": _generate_openai,
    "bedrock_claude": _generate_bedrock_claude,
}


def generate_text(
    system_prompt: str,
    user_content: str,
    max_tokens: int = 1024,
    provider: str | None = None,
    timeout: float | None = None,
) -> str:
    """Call the selected LLM provider and return the raw reply text.

    `provider` overrides LLM_PROVIDER for this one call; otherwise the
    module-level default (env var, "gemini" if unset) is used.

    Every call is bounded by `timeout` seconds (default DEFAULT_TIMEOUT_SECONDS
    = 10, per CLAUDE.md's reliability rules — no LLM call may hang the graph
    during a live demo). Raises LLMTimeoutError on expiry; callers must treat
    that as a failure and fail SAFE (route to human review), never as success.
    """
    name = (provider or DEFAULT_PROVIDER).lower()
    try:
        fn = _PROVIDERS[name]
    except KeyError:
        raise ValueError(
            f"Unknown LLM_PROVIDER {name!r}; expected one of {sorted(_PROVIDERS)}"
        )
    bound = timeout if timeout is not None else DEFAULT_TIMEOUT_SECONDS
    future = _executor.submit(fn, system_prompt, user_content, max_tokens)
    try:
        return future.result(timeout=bound)
    except FutureTimeoutError:
        raise LLMTimeoutError(
            f"LLM call to provider={name!r} exceeded {bound}s timeout"
        )
