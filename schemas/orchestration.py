from typing import List, Dict
from pydantic import BaseModel


class Stage(BaseModel):
    name: str
    agents: List[str]
    tasks: Dict[str, str]


class OrchestrationPlan(BaseModel):
    intent: str
    response_format: str
    context_policy: str
    stages: List[Stage]
