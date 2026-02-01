import os
import json
from pathlib import Path
from typing import Any, Dict, List

import requests


def main() -> None:
    """Call the hosted Contoso agent for each eval test case and write JSONL.

    Output format is "simple agent data" for Azure AI Evaluation SDK:
      - query: user question
      - response: agent's answer
      - plus metadata (id, customer_id, expected/required tools, success_criteria)
    """
    backend_chat_url = os.environ.get("BACKEND_CHAT_URL")
    if not backend_chat_url:
        raise RuntimeError("BACKEND_CHAT_URL env var must be set to your /chat endpoint, e.g. https://<backend-fqdn>/chat")

    root = Path(__file__).resolve().parent
    dataset_path = root / "eval_dataset.json"
    output_path = root / "evaluation_input_data.jsonl"

    with dataset_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    test_cases: List[Dict[str, Any]] = data.get("test_cases", [])
    if not test_cases:
        raise RuntimeError("No test_cases found in eval_dataset.json")

    print(f"Loaded {len(test_cases)} test cases from {dataset_path}")

    with output_path.open("w", encoding="utf-8") as out_f:
        for case in test_cases:
            case_id = case.get("id") or "unknown_id"
            query = case.get("customer_query") or ""
            customer_id = case.get("customer_id")

            if not query:
                print(f"[WARN] Skipping case {case_id} with empty customer_query")
                continue

            session_id = str(case_id)
            payload = {"session_id": session_id, "prompt": query}

            print(f"[INFO] Calling agent for case {case_id}...")
            resp = requests.post(backend_chat_url, json=payload, timeout=60)
            try:
                resp.raise_for_status()
            except Exception as e:
                print(f"[ERROR] Request failed for case {case_id}: {e}")
                continue

            try:
                body = resp.json()
            except ValueError:
                print(f"[ERROR] Non-JSON response for case {case_id}: {resp.text[:200]}")
                continue

            answer = body.get("response", "")
            if not isinstance(answer, str):
                answer = str(answer)

            # Tools actually used by the hosted agent for this turn (if provided
            # by the backend). We normalize into both a simple list of tool names
            # and a list of call objects with a "name" field for downstream
            # evaluators.
            tools_used = body.get("tools_used") or []
            if not isinstance(tools_used, list):
                tools_used = [str(tools_used)]

            tool_calls = [{"name": t} for t in tools_used]

            record: Dict[str, Any] = {
                "id": case_id,
                "customer_id": customer_id,
                "query": query,
                "response": answer,
                "actual_tools": tools_used,
                "tool_calls": tool_calls,
            }

            # Carry through expectations as metadata (useful for custom analysis or future tool-call evals)
            for key in [
                "expected_analysis",
                "expected_systems_accessed",
                "expected_tools",
                "required_tools",
                "expected_knowledge_queries",
                "success_criteria",
            ]:
                if key in case:
                    record[key] = case[key]

            out_f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"Wrote evaluation input data to {output_path}")


if __name__ == "__main__":
    main()
