from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4


class AnalysisHistoryStore:
    def __init__(self, max_records: int = 500) -> None:
        self.max_records = max_records
        self._records: OrderedDict[str, dict] = OrderedDict()
        self._lock = Lock()

    def add_record(self, analysis_type: str, source: str) -> str:
        analysis_id = str(uuid4())
        record = {
            "analysis_id": analysis_id,
            "analysis_type": analysis_type,
            "source": source,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        with self._lock:
            self._records[analysis_id] = record
            while len(self._records) > self.max_records:
                self._records.popitem(last=False)

        return analysis_id

    def list_records(self, limit: int = 50) -> list[dict]:
        with self._lock:
            values = list(self._records.values())

        # Return newest first.
        return list(reversed(values))[:limit]

    def delete_record(self, analysis_id: str) -> bool:
        with self._lock:
            if analysis_id not in self._records:
                return False
            del self._records[analysis_id]
            return True