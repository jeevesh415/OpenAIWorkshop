import os
import sys
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from dotenv import load_dotenv

# Load env from project root (one level up)
PROJECT_ROOT_ENV = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
load_dotenv(dotenv_path=PROJECT_ROOT_ENV)

TIMEOUT_SECONDS = 8


def check_url(url: str, label: str) -> bool:
    """Return True if the URL is network-reachable (any HTTP response), False otherwise.
    Treat HTTP status codes (including 401/403/404) as reachable; only network errors/timeouts fail.
    """
    req = Request(url, method="GET")
    try:
        with urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
            code = getattr(resp, "status", None) or getattr(resp, "code", None)
            print(f"[OK] {label}: {url} (HTTP {code})")
            return True
    except HTTPError as e:
        # HTTPError: server responded; consider reachable
        print(f"[OK] {label}: {url} (HTTP {e.code})")
        return True
    except URLError as e:
        print(f"[FAIL] {label}: {url} ({e.reason})")
        return False
    except Exception as e:
        print(f"[FAIL] {label}: {url} ({e})")
        return False


def main() -> int:
    mcp_base = os.getenv("MCP_SERVICE_URL")
    azure_ep = os.getenv("AZURE_AI_PROJECT_ENDPOINT")

    if not mcp_base:
        print("[WARN] MCP_SERVICE_URL is not set in environment.")
    if not azure_ep:
        print("[WARN] AZURE_AI_PROJECT_ENDPOINT is not set in environment.")

    # Check MCP tools endpoint if MCP_SERVICE_URL provided
    mcp_ok = True
    if mcp_base:
        mcp_tools = mcp_base.rstrip("/") + "/tools"
        mcp_ok = check_url(mcp_tools, "MCP tools endpoint")

    # Check Azure AI Project endpoint if provided
    azure_ok = True
    if azure_ep:
        azure_ok = check_url(azure_ep, "Azure AI Project endpoint")

    # Exit code: 0 if all provided endpoints reachable; 1 otherwise
    if (mcp_base and not mcp_ok) or (azure_ep and not azure_ok):
        print("[RESULT] One or more endpoints are not reachable.")
        return 1

    print("[RESULT] Reachability checks passed for provided endpoints.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
