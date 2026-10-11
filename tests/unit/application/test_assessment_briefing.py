import pytest
from application.assessment_service import AssessmentService
from application.briefing_service import BriefingService
from application.contracts import GradeQuizRequest, QuizRequest
from application.exceptions import ValidationError

class FakeEngine:
    def get_lesson_quiz(self, file_name, section): return ([{"question":"q"}], None)
    def grade_lesson_quiz(self, quiz, answers, user_id="guest_01"):
        return {"grading_result":{"score":1.0,"correct_count":1,"total_count":1}}
    def get_source_briefing(self, file_name):
        return ({"synopsis":"s","key_themes":["k"],"podcast_script":"p"}, None)

def test_assessment_service():
    service=AssessmentService(FakeEngine())
    assert len(service.generate_quiz(QuizRequest("u","f","s")).questions) == 1
    result=service.grade_quiz(GradeQuizRequest("u",[{"question":"q"}],{"0":0}))
    assert result.score == 1 and result.correct == 1

def test_assessment_validation():
    with pytest.raises(ValidationError): AssessmentService(FakeEngine()).generate_quiz(QuizRequest("u","","s"))
    with pytest.raises(ValidationError): AssessmentService(FakeEngine()).grade_quiz(GradeQuizRequest("u",[],{}))

def test_briefing_service():
    result=BriefingService(FakeEngine()).generate("f")
    assert result.synopsis == "s" and result.key_themes == ["k"]
