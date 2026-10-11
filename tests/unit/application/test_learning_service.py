import pytest
from application.contracts import LessonRequest
from application.events import EventKind
from application.exceptions import ValidationError
from application.learning_service import LearningService

class FakeEngine:
    def __init__(self, fail=False): self.fail=fail; self.calls=[]
    def process_action(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail: raise RuntimeError("boom")
        return iter([{"type":"status","message":"start"},{"type":"chunk","content":"hello"},{"type":"final","content":"done"}])

def request(): return LessonRequest("u","f","s",{"step_id":"1"})

def test_learning_stream_maps_events():
    engine=FakeEngine(); events=list(LearningService(engine).stream_lesson(request()))
    assert [x.kind for x in events] == [EventKind.STATUS, EventKind.CHUNK, EventKind.FINAL]
    assert engine.calls[0]["action_mode"] == "LEARNING"

def test_learning_failure_becomes_safe_error_event():
    event=list(LearningService(FakeEngine(True)).stream_lesson(request()))[0]
    assert event.kind is EventKind.ERROR and event.payload["exception_type"] == "RuntimeError"

def test_learning_validation_occurs_on_iteration():
    with pytest.raises(ValidationError): list(LearningService(FakeEngine()).stream_lesson(LessonRequest("u","","s",{})))
