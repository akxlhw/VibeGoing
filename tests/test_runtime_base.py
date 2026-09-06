"""VG-301 Runtime 抽象：TaskSpec/事件/句柄 与 LLMRuntime。"""

from __future__ import annotations

from vibegoing.runtimes.base import (
    LLMRuntime,
    Runtime,
    RuntimeEvent,
    TaskSpec,
)
from vibegoing.runtimes.registry import get_runtime
from vibegoing.soul import Soul


class StubLLM:
    def call(self, messages, **kwargs):
        return "llm 回复内容"


def test_llm_runtime_submit_streams_and_completes():
    runtime = LLMRuntime(model="x/y", llm=StubLLM())
    assert runtime.health().ok

    events: list[RuntimeEvent] = []
    handle = runtime.submit(TaskSpec(instruction="你好"), on_event=events.append)

    assert handle.wait(timeout=5) == "llm 回复内容"
    kinds = [e.kind for e in events]
    assert kinds == ["stdout", "done"]
    assert handle.result == "llm 回复内容"


def test_llm_runtime_error_terminates():
    class Boom:
        def call(self, messages, **kwargs):
            raise RuntimeError("401")

    runtime = LLMRuntime(model="x/y", llm=Boom())
    events: list[RuntimeEvent] = []
    handle = runtime.submit(TaskSpec(instruction="hi"), on_event=events.append)

    try:
        handle.wait(timeout=5)
        raise AssertionError("应当抛错")
    except RuntimeError as exc:
        assert "401" in str(exc)
    assert events[-1].kind == "error"


def test_runtime_is_abstract():
    try:
        Runtime()
        raise AssertionError("Runtime 不可直接实例化")
    except TypeError:
        pass


def test_registry_returns_llm_by_default():
    runtime = get_runtime(Soul(name="ava", model="openai/gpt-4o"))
    assert runtime.name == "llm"


def test_wait_timeout_raises():
    class SlowRuntime(Runtime):
        name = "slow"

        def submit(self, task, *, on_event=None):
            import threading
            import uuid

            from vibegoing.runtimes.base import TaskHandle

            handle = TaskHandle(self.name, uuid.uuid4().hex[:8])
            threading.Timer(10, lambda: handle._complete("late", None)).start()
            return handle

        def health(self):
            from vibegoing.runtimes.base import RuntimeHealth

            return RuntimeHealth(ok=True, detail="")

    handle = SlowRuntime().submit(TaskSpec(instruction="x"))
    try:
        handle.wait(timeout=0.05)
        raise AssertionError("应当超时")
    except TimeoutError:
        pass


def test_handle_events_recorded_without_callback():
    runtime = LLMRuntime(model="x/y", llm=StubLLM())
    handle = runtime.submit(TaskSpec(instruction="hi"))  # 无回调
    handle.wait(timeout=5)
    assert [e.kind for e in handle.events] == ["stdout", "done"]
