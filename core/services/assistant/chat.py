"""Turn orchestration, session memory, tool audit, citations and actions."""
import re
import threading
from collections import OrderedDict

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from core.models import Dealer
from .llm import generate_turn
from .tools import ToolContext, execute_tool

_LOCK = threading.RLock()
_SESSIONS = OrderedDict()
_MAX_SESSIONS = 500
_MAX_HISTORY_MESSAGES = 12
_SKU_RE = re.compile(r"\b[A-Z]{2,8}-\d{3,8}\b", re.I)


def _history_key(dealer_id, session_id):
    return (int(dealer_id), session_id)


def chat(*, dealer, session_id, message):
    key = _history_key(dealer.id, session_id)
    with _LOCK:
        history = list(_SESSIONS.get(key, []))
        _SESSIONS.move_to_end(key) if key in _SESSIONS else None

    ctx = ToolContext(dealer=dealer)
    audit = []
    def run_tool(name, args):
        result = execute_tool(name, args, ctx)
        return result

    try:
        reply, audit = generate_turn(message, history, run_tool)
    except ImproperlyConfigured:
        raise
    # Keep model-authored conversation parts from the adapter when possible; store a compact,
    # provider-independent transcript so the next turn can use role/text context.
    history.extend([{"role": "user", "parts": [{"text": message}]}, {"role": "model", "parts": [{"text": reply}]}])
    with _LOCK:
        _SESSIONS[key] = history[-_MAX_HISTORY_MESSAGES:]
        _SESSIONS.move_to_end(key)
        while len(_SESSIONS) > _MAX_SESSIONS:
            _SESSIONS.popitem(last=False)

    sku_candidates = set()
    for item in audit:
        result = item.get("result", {})
        for product in result.get("products", []) if isinstance(result, dict) else []:
            if product.get("sku"):
                sku_candidates.add(product["sku"])
        if result.get("sku"):
            sku_candidates.add(result["sku"])
        order = result.get("order", {})
        for line in order.get("items", []) if isinstance(order, dict) else []:
            if line.get("sku"):
                sku_candidates.add(line["sku"])
    mentioned = {m.upper() for m in _SKU_RE.findall(reply)}
    citations = sorted(s for s in sku_candidates if s.upper() in mentioned)
    public_calls = [{"name": item["name"], "arguments": item["arguments"]} for item in audit]
    actions = [{"type": "draft_order_created", "order_number": number} for number in ctx.created_orders]
    return {"reply": reply, "cited_skus": citations, "tool_calls": public_calls, "actions": actions}, audit


def clear_sessions_for_tests():
    with _LOCK:
        _SESSIONS.clear()
