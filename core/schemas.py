from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal


class DocumentType(str, Enum):
    """Categorization of ingested documents."""
    PAPER = "PAPER"
    BOOK = "BOOK"
    SLIDE = "SLIDE"


class SubSectionNode(BaseModel):
    """Granular subsection within a section (for books or detailed papers)."""
    title: str = Field(description="Title of the subsection (e.g., '1.2.1 Stochastic Gradient Descent')")
    start_page: int = Field(description="1-based starting page number")
    end_page: int = Field(description="1-based ending page number")
    is_same_page: bool = Field(default=False, description="Flag indicating if subsection shares a page with adjacent siblings")


class SectionNode(BaseModel):
    """Section within a chapter or topic."""
    title: str = Field(description="Title of the section (e.g., '1.2 Optimization' or 'Slide 4: Loss Function')")
    start_page: int = Field(description="1-based starting page number")
    end_page: int = Field(description="1-based ending page number")
    subsections: Optional[List[SubSectionNode]] = Field(
        default_factory=list,
        description="List of granular subsections for BOOK or detailed PAPER",
    )
    is_same_page: bool = Field(default=False, description="Flag indicating if section shares a page with siblings")


class ChapterOrTopicNode(BaseModel):
    """Top-level chapter for BOOK, major section for PAPER, or topic for SLIDE."""
    name: str = Field(description="Chapter name for BOOK, Major Section for PAPER, or Topic for SLIDE")
    start_page: int = Field(description="1-based starting page number")
    end_page: int = Field(description="1-based ending page number")
    sections: List[SectionNode] = Field(
        default_factory=list,
        description="List of child sections within this chapter or topic",
    )


class DocumentStructure(BaseModel):
    """Hierarchical document outline tree extracted via multimodal vision or parsing."""
    document_type: DocumentType = Field(description="Classified document category: PAPER, BOOK, or SLIDE")
    document_title: str = Field(description="Exact canonical title of the document")
    total_pages: int = Field(description="Total number of pages detected in the document")
    summary: str = Field(default="", description="Concise 2-3 sentence pedagogical overview of the document")
    hierarchy: List[ChapterOrTopicNode] = Field(default_factory=list, description="Hierarchical outline tree of the document")



class PedagogicalRelationType(str, Enum):
    """Standardized pedagogical relation types for the knowledge graph."""
    PREREQUISITE_OF = "PREREQUISITE_OF"
    RELATES_TO = "RELATES_TO"
    PART_OF = "PART_OF"
    DESCRIBES = "DESCRIBES"
    VERSUS = "VERSUS"
    EXEMPLIFIES = "EXEMPLIFIES"
    APPLIED_IN = "APPLIED_IN"


PedagogicalRelation = PedagogicalRelationType


class ConceptExtract(BaseModel):
    """Extracted concept candidate with multilingual alignment and contextual provenance."""
    name_en: str = Field(description="Canonical English name of the concept")
    name_vn: Optional[str] = Field(default=None, description="Vietnamese equivalent or alias")
    acronym: Optional[str] = Field(default=None, description="Acronym or abbreviation (e.g., CNN, SGD, RNN)")
    context_snippet: str = Field(default="", description="Verbatim text context where the concept appears")
    source_location: str = Field(default="", description="Source locator pointer (e.g., slide:12, pdf:p4)")


class Concept(BaseModel):
    """Knowledge graph concept node model with canonical name and alias resolution."""
    id: Optional[str] = Field(default=None, description="Unique node identifier")
    name: Optional[str] = Field(default=None, description="Display name of the concept")
    canonical_name: str = Field(default="", description="Canonical English identifier for the concept")
    aliases: List[str] = Field(default_factory=list, description="List of synonymous aliases and abbreviations")
    type: str = Field(default="concept", description="Concept category or ontological type")
    description: str = Field(default="", description="Summary definition of the concept")
    is_main: bool = Field(default=False, description="Flag indicating if concept is a primary subject of the section")
    source_locators: List[str] = Field(default_factory=list, description="List of source locations where this concept occurs")



class TeachingStep(BaseModel):
    step_id: str = Field(description="Unique ID for the teaching step")
    step_title: str = Field(description="Title of the teaching step")
    content_focus: str = Field(description="Focus content (Raw text from the book)")

    # Array of Agent Queues decided by the Ingestion LLM
    required_agents: List[str] = Field(
        description="Ordered list of teaching experts. Choose only from: ['concept', 'formula', 'math', 'algorithm', 'example', 'dynamic:<role>']."
    )


class QAResponse(BaseModel):
    """
    - Reason: To enforce a structured JSON output from the SupportAgent.
    - Function: Validates the LLM's answer.
    """
    answer: str = Field(description="The synthesized academic answer to the user's query.")


class AgentTask(BaseModel):
    """A typed instruction passed to an individual agent."""
    task_id: str = Field(description="Unique task identifier")
    agent_name: str = Field(description="Target agent name")
    instruction: str = Field(description="Natural language instruction for the agent")
    input_keys: List[str] = Field(default_factory=list, description="Blackboard keys the agent should read")
    output_key: Optional[str] = Field(default=None, description="Blackboard key where output should be written")
    requires_critic: bool = Field(default=True, description="Whether the output should be reviewed by CriticAgent")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional task metadata")


class AgentMessage(BaseModel):
    """A structured message written by an agent to the shared blackboard."""
    agent_name: str
    role: str
    content: str
    claims: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    needs_revision: bool = False
    next_suggested_agents: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentResult(BaseModel):
    """The structured output of a completed agent task."""
    task_id: str
    agent_name: str
    message: AgentMessage
    artifacts: Dict[str, Any] = Field(default_factory=dict)
    success: bool = True
    error: Optional[str] = None


class AgentTraceEvent(BaseModel):
    """One observable event emitted during a multi-agent runtime run."""
    event_id: str
    run_id: str
    event_type: str
    timestamp: float
    agent_name: Optional[str] = None
    task_id: Optional[str] = None
    message: str = ""
    success: Optional[bool] = None
    latency_ms: Optional[float] = None
    payload: Dict[str, Any] = Field(default_factory=dict)


class RuntimeTrace(BaseModel):
    """Persistent trace for one runtime execution."""
    run_id: str
    user_id: str = "guest_01"
    target_file: str = ""
    target_section: str = ""
    workflow_mode: str = ""
    started_at: float
    completed_at: Optional[float] = None
    success: bool = True
    events: List[AgentTraceEvent] = Field(default_factory=list)
    blackboard_snapshot: Dict[str, Any] = Field(default_factory=dict)


class QuizQuestion(BaseModel):
    """One multiple-choice assessment question."""
    question: str
    options: List[str] = Field(default_factory=list)
    answer_idx: int = 0
    explanation: str = ""
    concept_id: Optional[str] = None
    difficulty: Literal["easy", "medium", "hard"] = "medium"


class QuizPayload(BaseModel):
    """A generated quiz for a lesson or concept group."""
    quiz_id: str
    title: str = "Assessment"
    questions: List[QuizQuestion] = Field(default_factory=list)
    target_concepts: List[str] = Field(default_factory=list)


class GradingResult(BaseModel):
    """Evaluation result for one submitted quiz."""
    score: float = Field(default=0.0, ge=0.0, le=1.0)
    correct_count: int = 0
    total_count: int = 0
    weak_concepts: List[str] = Field(default_factory=list)
    feedback: str = ""
    remediation_required: bool = False


class RemediationPlan(BaseModel):
    """Follow-up teaching plan for weak concepts detected by assessment."""
    weak_concepts: List[str] = Field(default_factory=list)
    recommended_agents: List[str] = Field(default_factory=list)
    instruction: str = ""


class CriticReport(BaseModel):
    """Verification report produced by CriticAgent."""
    status: Literal["pass", "needs_revision", "fail"] = "pass"
    reviewed_agent: Optional[str] = None
    issues: List[str] = Field(default_factory=list)
    unsupported_claims: List[str] = Field(default_factory=list)
    send_back_to: Optional[str] = None
    revised_instruction: Optional[str] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class PlanStep(BaseModel):
    """One step in a runtime multi-agent execution plan."""
    step_id: str
    agent_name: str
    instruction: str
    depends_on: List[str] = Field(default_factory=list)
    requires_critic: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RuntimePlan(BaseModel):
    """A dynamic execution plan produced by PlannerAgent."""
    plan_id: str
    objective: str
    steps: List[PlanStep] = Field(default_factory=list)
    rationale: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BlackboardState(BaseModel):
    """Shared state for one multi-agent runtime execution."""
    user_id: str = "guest_01"
    target_file: str = ""
    target_section: str = ""
    lesson_goal: str = ""
    macro_context: str = ""
    micro_context: str = ""
    graph_context: Dict[str, Any] = Field(default_factory=dict)
    semantic_memory: List[Dict[str, Any]] = Field(default_factory=list)
    recent_history: List[Dict[str, Any]] = Field(default_factory=list)
    agent_messages: List[AgentMessage] = Field(default_factory=list)
    critic_reports: List[CriticReport] = Field(default_factory=list)
    final_output: str = ""
    artifacts: Dict[str, Any] = Field(default_factory=dict)