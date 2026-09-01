from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from .alibaba import AlibabaClient


@dataclass
class ScanResult:
    id: str
    category: str
    status: str = "NOT_PROBED"
    tested: bool = False
    error_category: str | None = None
    scanned_at: str = ""


def classify(model_id: str) -> str:
    name = model_id.lower()
    if any(word in name for word in ("image", "vision", "vl")):
        return "VISION"
    if any(word in name for word in ("video", "wan")):
        return "VIDEO"
    if any(word in name for word in ("audio", "speech", "tts", "asr")):
        return "AUDIO"
    if any(word in name for word in ("coder", "code")):
        return "CODING"
    if any(word in name for word in ("reason", "think", "r1")):
        return "REASONING"
    return "GENERAL_CHAT"


async def discover(client: AlibabaClient) -> list[dict]:
    payload = await client.list_models()
    items = payload.get("data", payload if isinstance(payload, list) else [])
    seen = set()
    results = []
    timestamp = datetime.now(timezone.utc).isoformat()
    for item in items:
        model_id = item.get("id") if isinstance(item, dict) else str(item)
        if not model_id or model_id in seen:
            continue
        seen.add(model_id)
        results.append(asdict(ScanResult(id=model_id, category=classify(model_id), scanned_at=timestamp)))
    return results

