from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class BacktestScenario(BaseModel):
    name: str
    country: str
    start_date: str
    end_date: str
    peak_date: Optional[str] = None
    timeline: List[Dict[str, Any]] = []
