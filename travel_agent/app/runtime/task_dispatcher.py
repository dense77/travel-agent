"""任务分发抽象。

说明：
- 当前仓库先提供本地 inline 与 threadpool 两种实现。
- 后续可把这里替换成 Celery/RabbitMQ，而不影响 API 和 Service 层。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from typing import Callable


TaskCallable = Callable[[], None]


class TaskDispatcher(ABC):
    """统一任务分发接口。"""

    @abstractmethod
    def submit(self, task_id: str, target: TaskCallable) -> None:
        """提交任务。"""


class InlineTaskDispatcher(TaskDispatcher):
    """同步执行，便于调试。"""

    def submit(self, task_id: str, target: TaskCallable) -> None:
        del task_id
        target()


class ThreadPoolTaskDispatcher(TaskDispatcher):
    """本地线程池实现，模拟异步任务执行。"""

    def __init__(self, max_workers: int = 4) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="travel-agent")

    def submit(self, task_id: str, target: TaskCallable) -> None:
        del task_id
        self._executor.submit(target)
