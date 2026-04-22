"""任务分发抽象。

这个模块的核心价值在于：
把“API 收到请求以后如何真正执行任务”抽象掉。

这样当前我们可以用本地线程池模拟异步执行，
未来也可以无缝替换成 Celery + RabbitMQ。
"""

# 启用延迟类型注解。
from __future__ import annotations

# ABC 和 abstractmethod 用来定义抽象接口。
from abc import ABC, abstractmethod
# ThreadPoolExecutor 用来提供本地线程池异步执行能力。
from concurrent.futures import ThreadPoolExecutor
# Callable 用来描述可调用任务的类型。
from typing import Callable


# TaskCallable 表示“一个无参数、无返回值的任务函数”。
TaskCallable = Callable[[], None]


class TaskDispatcher(ABC):
    """统一任务分发接口。"""

    @abstractmethod
    def submit(self, task_id: str, target: TaskCallable) -> None:
        """提交一个任务到调度系统。"""


class InlineTaskDispatcher(TaskDispatcher):
    """同步执行实现。

    这个实现主要用于：
    - 本地调试
    - 单步排查
    - 不想引入异步行为的场景
    """

    def submit(self, task_id: str, target: TaskCallable) -> None:
        """直接在当前线程里执行任务。"""
        # 当前实现不需要 task_id，
        # 但保留参数是为了保持统一接口。
        del task_id
        # 直接调用任务函数。
        target()


class ThreadPoolTaskDispatcher(TaskDispatcher):
    """本地线程池实现。

    它模拟了“任务先提交，再异步执行”的效果，
    是当前项目从同步模式演进到队列模式的过渡层。
    """

    def __init__(self, max_workers: int = 4) -> None:
        """初始化线程池。"""
        # 创建线程池执行器，并给线程起统一前缀，
        # 方便调试时识别线程来源。
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="travel-agent")

    def submit(self, task_id: str, target: TaskCallable) -> None:
        """把任务交给线程池。"""
        # 当前线程池并不直接使用 task_id，
        # 但未来接入真实队列时可以用它做追踪。
        del task_id
        # 提交任务给线程池异步执行。
        self._executor.submit(target)
