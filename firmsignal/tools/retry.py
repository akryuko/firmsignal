import logging

import anthropic
import requests
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    wait_fixed,
)

logger = logging.getLogger(__name__)


# ─── Tavily retry ─────────────────────────────────────────────────────────────

def _should_retry_tavily(exc: BaseException) -> bool:
    if isinstance(exc, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)):
        return True
    if isinstance(exc, Exception) and "rate" in str(exc).lower():
        return True
    return False


def _on_tavily_giveup(retry_state: RetryCallState):
    exc = retry_state.outcome.exception()
    logger.error("[retry] Tavily gave up after %d attempts: %s", retry_state.attempt_number, exc)
    return []


def _log_tavily_retry(retry_state: RetryCallState):
    print(f"[Tavily] Retrying search (attempt {retry_state.attempt_number + 1})...")


tavily_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception(_should_retry_tavily),
    before_sleep=_log_tavily_retry,
    retry_error_callback=_on_tavily_giveup,
)


# ─── LLM retry ────────────────────────────────────────────────────────────────

llm_retry = retry(
    stop=stop_after_attempt(2),
    wait=wait_fixed(3),
    retry=retry_if_exception_type((
        anthropic.APITimeoutError,
        anthropic.RateLimitError,
        anthropic.InternalServerError,
    )),
    reraise=True,
)


# ─── yfinance retry ───────────────────────────────────────────────────────────

def _on_yfinance_giveup(retry_state: RetryCallState):
    exc = retry_state.outcome.exception()
    logger.error("[retry] yfinance gave up after %d attempts: %s", retry_state.attempt_number, exc)
    return None


yfinance_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(2),
    retry=retry_if_exception_type(Exception),
    retry_error_callback=_on_yfinance_giveup,
)
