"""Test all configured LLM providers and deployments end-to-end."""

from __future__ import annotations

import sys
import time
from unittest.mock import MagicMock


class _AttrDict(dict):
    """Dict that also supports attribute access (like Streamlit session_state)."""
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)

    def __setattr__(self, key, value):
        self[key] = value

    def __delattr__(self, key):
        try:
            del self[key]
        except KeyError:
            raise AttributeError(key)


# ---------------------------------------------------------------------------
# Minimal Streamlit mock so we can import app modules outside of Streamlit
# ---------------------------------------------------------------------------
mock_st = MagicMock()
mock_st.session_state = _AttrDict()
mock_st.secrets = {}
mock_st.cache_data = MagicMock()
sys.modules["streamlit"] = mock_st

# Load .env manually — imports must come after sys.modules mock above
from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from app.core.config import LLM_PROVIDERS, load_settings  # noqa: E402

settings = load_settings()
mock_st.session_state["_settings"] = settings

from app.services.llm_service import (  # noqa: E402
    create_azure_embeddings,
    create_azure_llm,
    create_ollama_llm,
    get_available_ollama_models,
)

TEST_PROMPT = "Reply with exactly one word: Hello"
TIMEOUT = 30

RESET = "\033[0m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"


def test_azure_llm(name: str, info: dict) -> tuple[bool, str, float]:
    """Test a single Azure LLM deployment. Returns (success, message, latency_s)."""
    start = time.time()
    try:
        llm = create_azure_llm(
            account=info["account"],
            azure_deployment=info["deployment"],
        )
        response = llm.invoke(TEST_PROMPT)
        content = response.content if hasattr(response, "content") else str(response)
        elapsed = time.time() - start
        if content and len(content.strip()) > 0:
            return True, content.strip()[:80], elapsed
        return False, "Empty response", elapsed
    except Exception as exc:
        elapsed = time.time() - start
        return False, f"{type(exc).__name__}: {exc}"[:120], elapsed


def test_embeddings(account: str) -> tuple[bool, str, float]:
    """Test Azure embeddings for an account."""
    start = time.time()
    try:
        emb = create_azure_embeddings(account=account)
        vectors = emb.embed_documents(["test embedding"])
        elapsed = time.time() - start
        if vectors and len(vectors) > 0 and len(vectors[0]) > 0:
            return True, f"dim={len(vectors[0])}", elapsed
        return False, "Empty embedding", elapsed
    except Exception as exc:
        elapsed = time.time() - start
        return False, f"{type(exc).__name__}: {exc}"[:120], elapsed


def test_ollama_model(model: str) -> tuple[bool, str, float]:
    """Test a single Ollama model."""
    start = time.time()
    try:
        llm = create_ollama_llm(model=model)
        response = llm.invoke(TEST_PROMPT)
        content = response.content if hasattr(response, "content") else str(response)
        elapsed = time.time() - start
        if content and len(content.strip()) > 0:
            return True, content.strip()[:80], elapsed
        return False, "Empty response", elapsed
    except Exception as exc:
        elapsed = time.time() - start
        return False, f"{type(exc).__name__}: {exc}"[:120], elapsed


def main():
    print(f"\n{BOLD}{'='*80}{RESET}")
    print(f"{BOLD}  LLM Provider Test Suite{RESET}")
    print(f"{BOLD}{'='*80}{RESET}\n")

    results = []

    # -------------------------------------------------------------------
    # 1) Test all Azure LLM deployments
    # -------------------------------------------------------------------
    print(f"{BOLD}{CYAN}[1/3] Testing Azure LLM Deployments ({len(LLM_PROVIDERS)} models){RESET}\n")

    for name, info in LLM_PROVIDERS.items():
        print(f"  Testing: {name:<35s}", end="", flush=True)
        success, msg, elapsed = test_azure_llm(name, info)
        status = f"{GREEN}PASS{RESET}" if success else f"{RED}FAIL{RESET}"
        print(f" [{status}] ({elapsed:.1f}s) — {msg}")
        results.append(("Azure", name, success, msg, elapsed))

    # -------------------------------------------------------------------
    # 2) Test Azure Embeddings
    # -------------------------------------------------------------------
    print(f"\n{BOLD}{CYAN}[2/3] Testing Azure Embeddings{RESET}\n")

    for account in ["osaa_v2"]:
        print(f"  Testing: embeddings ({account}){' ':<19s}", end="", flush=True)
        success, msg, elapsed = test_embeddings(account)
        status = f"{GREEN}PASS{RESET}" if success else f"{RED}FAIL{RESET}"
        print(f" [{status}] ({elapsed:.1f}s) — {msg}")
        results.append(("Embeddings", f"embeddings ({account})", success, msg, elapsed))

    # -------------------------------------------------------------------
    # 3) Test Ollama (if running)
    # -------------------------------------------------------------------
    print(f"\n{BOLD}{CYAN}[3/3] Testing Ollama (local){RESET}\n")

    ollama_models = get_available_ollama_models()
    if ollama_models:
        print(f"  Ollama is running — found {len(ollama_models)} model(s): {', '.join(ollama_models)}\n")
        for model in ollama_models:
            print(f"  Testing: Ollama {model:<28s}", end="", flush=True)
            success, msg, elapsed = test_ollama_model(model)
            status = f"{GREEN}PASS{RESET}" if success else f"{RED}FAIL{RESET}"
            print(f" [{status}] ({elapsed:.1f}s) — {msg}")
            results.append(("Ollama", model, success, msg, elapsed))
    else:
        print(f"  {YELLOW}Ollama is not running or has no models — skipping{RESET}")

    # -------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------
    print(f"\n{BOLD}{'='*80}{RESET}")
    print(f"{BOLD}  Summary{RESET}")
    print(f"{BOLD}{'='*80}{RESET}\n")

    passed = sum(1 for r in results if r[2])
    failed = sum(1 for r in results if not r[2])

    print(f"  Total:  {len(results)}")
    print(f"  {GREEN}Passed: {passed}{RESET}")
    if failed:
        print(f"  {RED}Failed: {failed}{RESET}")
        print(f"\n  {RED}Failed tests:{RESET}")
        for cat, name, success, msg, _ in results:
            if not success:
                print(f"    - [{cat}] {name}: {msg}")
    else:
        print("  Failed: 0")

    print(f"\n  {GREEN if failed == 0 else YELLOW}{'All tests passed!' if failed == 0 else f'{failed} test(s) failed.'}{RESET}\n")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
