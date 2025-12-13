from dataclasses import dataclass
from threading import Lock
from typing import Dict, Optional

@dataclass(frozen=True)
class TrendResponseRecord:
    response_id: int
    chat_response: str
    action_step_plan: str

_lock = Lock()
_next_id: int = 1
_store: Dict[int, TrendResponseRecord] = {}

def save_trend_response(chat_response: str, action_step_plan: str) -> TrendResponseRecord:
    global _next_id
    with _lock:
        rid = _next_id
        _next_id += 1
        rec = TrendResponseRecord(
            response_id=rid,
            chat_response=chat_response,
            action_step_plan=action_step_plan
        )
        _store[rid] = rec
        return rec

def get_trend_response(response_id: int) -> Optional[TrendResponseRecord]:
    return _store.get(response_id)
