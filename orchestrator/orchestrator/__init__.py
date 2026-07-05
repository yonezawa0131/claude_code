"""マルチモデル・オーケストレーター。

Router / Verification Loop / Memory / StateManager を組み合わせた
自己改善型のタスク実行基盤。公式 Anthropic SDK を基盤にする。
"""

from .loop import ExecutionLoop, TaskResult
from .memory import MemoryStore
from .models import CATALOG, ModelInfo, estimate_cost
from .providers import AnthropicProvider, Completion, ModelRefusedError, Provider
from .router import Complexity, Router, RoutingDecision, Task
from .state import CostLimitExceeded, StateManager
from .verification import VerificationEngine, VerificationResult

__all__ = [
    "AnthropicProvider",
    "CATALOG",
    "Completion",
    "Complexity",
    "CostLimitExceeded",
    "ExecutionLoop",
    "MemoryStore",
    "ModelInfo",
    "ModelRefusedError",
    "Provider",
    "Router",
    "RoutingDecision",
    "StateManager",
    "Task",
    "TaskResult",
    "VerificationEngine",
    "VerificationResult",
    "estimate_cost",
]
