# master_agent_entrypoint.py
# Runtime entrypoint for Amazon Bedrock AgentCore Runtime (Strands supervisor agent)

import os
import re
import json
import uuid
from typing import Any, Dict
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from bedrock_agentcore.runtime import BedrockAgentCoreApp  # Runtime SDK

app = BedrockAgentCoreApp()

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_MASTER_FILE = os.path.join(_THIS_DIR, "supply-chain-master-agent.py")


def _load_master_module_safely() -> Dict[str, Any]:
    """
    Load the user's supervisor/orchestrator code from supply-chain-master-agent.py
    while removing the ad-hoc test/print section at the bottom so we don't run it on import.
    """
    if not os.path.exists(_MASTER_FILE):
        raise FileNotFoundError(f"Expected {_MASTER_FILE} next to this entrypoint.")

    with open(_MASTER_FILE, "r", encoding="utf-8") as f:
        code = f.read()

    # Strip any trailing inline test blocks (defensive: handle several possible markers)
    strip_patterns = [
        r"(?s)#\s*Test\s+Orchestrator\s+Workflow.*\Z",
        r'(?s)print\(\s*[\'"]🚀 ORCHESTRATOR WORKFLOW EXECUTION[\'"]\s*\).*?\Z',
        r"(?s)run_orchestrator_workflow\([^)]*\)\s*\Z",
    ]
    for pat in strip_patterns:
        code = re.sub(pat, "", code)

    # Execute into an isolated namespace (not a module import to avoid side effects)
    ns: Dict[str, Any] = {}
    exec(compile(code, _MASTER_FILE, "exec"), ns, ns)

    if "run_orchestrator_workflow" not in ns or not callable(ns["run_orchestrator_workflow"]):
        raise RuntimeError(
            "Could not find callable run_orchestrator_workflow(...) "
            "in supply-chain-master-agent.py after loading."
        )
    return ns


def _derive_user_input(payload: Dict[str, Any]) -> str:
    """
    Convert our supported payloads into the single `user_input` string
    that your orchestrator already expects.
    Supported shapes:
      - {"prompt": "..."}  (direct)
      - {"target":"supervisor","source":"gmail","gmail_query":"...","gmail_max":1}
      - {"target":"supervisor","source":"text","email_text":"<RFQ email body>"}  # your local testing shape
    """
    if isinstance(payload, dict):
        # direct "prompt"
        if "prompt" in payload and isinstance(payload["prompt"], str):
            return payload["prompt"]

        if payload.get("target") == "supervisor":
            src = payload.get("source", "text")
            if src == "gmail":
                q = payload.get("gmail_query", "subject:RFQ")
                limit = payload.get("gmail_max", 1)
                return (
                    f"Fetch the latest RFQ from Gmail using query '{q}' (max {limit}), "
                    "then execute the full RFQ workflow across Agents 0–5 end-to-end."
                )

            # text source
            text = payload.get("email_text", "")
            if isinstance(text, str) and text.strip():
                return (
                    "Use the following RFQ email content as input and execute the full end-to-end "
                    f"RFQ workflow across Agents 0–5:\n\n{text}"
                )

    # Fallback – ask the supervisor to run the entire pipeline
    return "Execute full RFQ workflow end-to-end."


def _jsonable(obj: Any) -> Any:
    """Make sure the return value is JSON-serializable for the AgentCore response."""
    try:
        json.dumps(obj)
        return obj
    except Exception:
        # Try best-effort stringification
        try:
            return json.loads(obj) if isinstance(obj, str) else str(obj)
        except Exception:
            return str(obj)


@app.entrypoint  # This exposes POST /invocations to AgentCore Runtime.
def invoke(payload: Dict[str, Any]):
    # Print raw payload and Python types for CloudWatch observability
    print("=== Incoming payload (raw) ===")
    try:
        print(json.dumps(payload, indent=2, default=str))
    except Exception:
        print(str(payload))
    print("=== Payload key types ===")
    print({k: type(v).__name__ for k, v in (payload or {}).items()})

    # Load your orchestrator without triggering inline tests
    ns = _load_master_module_safely()

    # Convert runtime payload -> the text input that your orchestrator expects
    user_input = _derive_user_input(payload or {})
    print("=== Derived user_input ===")
    print(user_input)

    # Call your orchestrator
    result = ns["run_orchestrator_workflow"](user_input)

    # Ensure JSON-serializable response (AgentCore requires it)
    return {
        "session": str(uuid.uuid4()),
        "result": _jsonable(result),
    }


def local_smoke_test():
    """
    Run this locally before deployment (no container needed).
    """
    sample = {
        "target": "supervisor",
        "source": "text",
        "email_text": "RFQ: 10k units of 5mm bolts needed by Nov 30, 2025. Ship to Seattle, WA."
    }
    print("\n[LOCAL SMOKE TEST] Calling invoke(...) with sample payload\n")
    response = invoke(sample)
    print("\n[LOCAL SMOKE TEST] Response\n")
    print(json.dumps(response, indent=2, default=str))


if __name__ == "__main__":
    # Run HTTP server locally (for curl testing) OR run local test
    if os.environ.get("LOCAL_TEST") == "1":
        local_smoke_test()
    else:
        # Starts the local HTTP server for /invocations and /ping
        app.run()
