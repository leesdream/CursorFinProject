"""Local HTTP server that powers the Trade Planner tab — zero Yahoo Finance MCP calls."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import anthropic

PORT = 7823

_SYSTEM = (
    "You are a senior investment advisor. Analyze planned trades through three frameworks:\n\n"
    "PETER LYNCH (GARP): Classify each instrument (Slow Grower / Stalwart / Fast Grower / "
    "Cyclical / Turnaround / Asset Play). Is the entry price reasonable for the growth rate? "
    "What is the PEG direction? Does the trade fit Lynch's 'buy what you know' principle?\n\n"
    "HOWARD MARKS (Risk-First): What is the realistic downside if this goes wrong? "
    "Is risk/reward asymmetric in the investor's favour? What does the consensus assume, "
    "and is there a second-level insight? Where are we in the cycle for this asset class?\n\n"
    "NASSIM TALEB (Antifragility): Does this trade ADD convexity (defined loss, open upside) "
    "or SUBTRACT it (capped upside, open downside)? Does it strengthen or weaken the barbell "
    "(safe core + speculative tail)? Is there any ruin risk — a position large enough to cause "
    "irrecoverable capital impairment? Options with defined premium are antifragile; "
    "naked shorts and leveraged longs are fragile.\n\n"
    "Be specific. Give a clear verdict per trade."
)

_USER_TEMPLATE = """\
Current portfolio:
{portfolio}

Planned trades for next session:
{trades}

Produce exactly these sections:

## Per-Trade Assessment
Table: Trade | Lynch Signal | Marks Risk/Reward | Taleb Rating (Antifragile / Neutral / Fragile)

## Risk Check
Worst realistic outcome if these trades all go against you simultaneously. Any ruin exposure or barbell damage?

## Suggested Modifications
Specific tweaks per trade: different strike, smaller size, hedge to pair with, or timing change.

## Verdict
For each trade: **Go** / **Modify** / **Skip** — one-line rationale.

## Portfolio Impact
After executing all trades: how does the barbell structure and overall antifragility change?\
"""


def _analyze(trades: str, portfolio: str) -> str:
    client = anthropic.Anthropic()
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": _USER_TEMPLATE.format(portfolio=portfolio, trades=trades),
            }
        ],
    )
    return "".join(b.text for b in resp.content if hasattr(b, "text"))


class _ReusableHTTPServer(HTTPServer):
    allow_reuse_address = True


class _Handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_POST(self):
        if self.path != "/analyze":
            self.send_response(404)
            self.end_headers()
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            result = _analyze(body.get("trades", ""), body.get("portfolio", ""))
            self._respond(200, {"analysis": result})
        except Exception as exc:
            self._respond(500, {"error": str(exc)})

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")

    def _respond(self, status: int, data: dict):
        payload = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_):
        pass  # silence request logs


def start(port: int = PORT) -> int:
    """Start the trade advisor HTTP server in a daemon thread. Returns the port."""
    server = _ReusableHTTPServer(("localhost", port), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return port
