import pytest
from application.contracts import QuestionRequest
from application.exceptions import InvalidModeError, OperationFailedError, ValidationError
from application.qa_service import QAService

class FakeEngine:
    def __init__(self, result="answer", error=None): self.result=result; self.error=error; self.calls=[]
    def process_action(self, **kwargs):
        self.calls.append(kwargs)
        if self.error: raise self.error
        return self.result

def test_global_qa_delegates_and_normalizes_string():
    engine=FakeEngine("hello"); result=QAService(engine).ask(QuestionRequest("u", "q", "global_qa"))
    assert result.content == "hello" and engine.calls[0]["action_mode"] == "GLOBAL_QA"

def test_dict_response_preserves_metadata():
    result=QAService(FakeEngine({"answer":"a", "sources":["s"]})).ask(QuestionRequest("u","q","GLOBAL_QA"))
    assert result.content == "a" and result.metadata["sources"] == ["s"]

def test_local_qa_requires_scope():
    with pytest.raises(ValidationError): QAService(FakeEngine()).ask(QuestionRequest("u","q","LOCAL_QA"))

def test_empty_query_and_invalid_mode():
    with pytest.raises(ValidationError): QAService(FakeEngine()).ask(QuestionRequest("u"," ","GLOBAL_QA"))
    with pytest.raises(InvalidModeError): QAService(FakeEngine()).ask(QuestionRequest("u","q","LEARNING"))

def test_runtime_failure_is_chained():
    with pytest.raises(OperationFailedError) as info:
        QAService(FakeEngine(error=RuntimeError("secret"))).ask(QuestionRequest("u","q","GLOBAL_QA"))
    assert isinstance(info.value.__cause__, RuntimeError)
