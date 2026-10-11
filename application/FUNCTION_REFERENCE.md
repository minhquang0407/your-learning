# Project Function & Method Reference

Purpose: Quick lookup for every declared function and method in the project without reopening its implementation.

> [!IMPORTANT]
> Prefer RuntimeEngine, MultiAgentRuntime, LLMService, public store methods, or application services. Names beginning with `_` are implementation details and may change.

## Quick Entry Points

| Use case | Recommended API |
|---|---|
| Initialize the current system | `main.init_system()` or `Container().runtime_engine()` |
| Deliver one lesson step | `RuntimeEngine.process_action(action_mode="LEARNING", ...)` |
| Local/Global Q&A | `RuntimeEngine.process_action(action_mode="LOCAL_QA"/"GLOBAL_QA", ...)` |
| Generate/grade a quiz | `RuntimeEngine.get_lesson_quiz()` / `grade_lesson_quiz()` |
| Source briefing | `RuntimeEngine.get_source_briefing()` |
| Run multi-agent directly | `MultiAgentRuntime.execute_learning()` |
| Parse and ingest a document | `run_ingestion_pipeline()` |
| Qdrant | Public methods of `QdrantVectorStore` |
| Neo4j | Public methods of `Neo4jManager` |
| New boundary (not implemented yet) | `LearningApplication` and services in `application/` |

## How to Read This Reference

- **Public / callable**: safe to call from the orchestration/application layer.
- **Internal helper**: names beginning with `_`; call only while maintaining that module.
- **TODO scaffold**: the signature exists but currently raises `NotImplementedError`.
- Functions under `tests/` are for testing/evaluation and are not production APIs.

---

## `agents/assessment_agents.py`

**Category:** Production module

### Class `QuizAgent`

- **Base:** `BaseAgent`
- **Purpose:** Assessment agent that generates concept-grounded multiple-choice quizzes.
- **Source:** [`assessment_agents.py`](file:///C:/Users/nguye/PROJECTS/your-learning/agents/assessment_agents.py#L17)

#### `QuizAgent.run()`

```python
def run(self, task: AgentTask, blackboard: BlackboardState)
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

### Class `GraderAgent`

- **Base:** `BaseAgent`
- **Purpose:** Assessment agent that grades quiz submissions and plans remediation.
- **Source:** [`assessment_agents.py`](file:///C:/Users/nguye/PROJECTS/your-learning/agents/assessment_agents.py#L85)

#### `GraderAgent.run()`

```python
def run(self, task: AgentTask, blackboard: BlackboardState)
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

---

## `agents/base.py`

**Category:** Production module

### Class `BaseAgent`

- **Base:** `ABC`
- **Purpose:** Base interface for all multi-agent runtime agents.
- **Source:** [`base.py`](file:///C:/Users/nguye/PROJECTS/your-learning/agents/base.py#L8)

#### `BaseAgent.__init__()`

```python
def __init__(self, llm_service: Any=None, tools: Optional[Dict[str, Any]]=None)
```

- **Visibility:** Dunder / lifecycle
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `BaseAgent.run()`

```python
def run(self, task: AgentTask, blackboard: BlackboardState) -> AgentResult
```

- **Visibility:** Public / callable
- **Purpose:** Execute an agent task and return a structured result.

#### `BaseAgent._build_result()`

```python
def _build_result(self, task: AgentTask, content: str, *, confidence: float=0.0, needs_revision: bool=False, success: bool=True, error: Optional[str]=None, metadata: Optional[Dict[str, Any]]=None) -> AgentResult
```

- **Visibility:** Internal helper - do not call from UI
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `BaseAgent._llm_invoke_text()`

```python
def _llm_invoke_text(self, system_prompt: str, human_prompt: str) -> str
```

- **Visibility:** Internal helper - do not call from UI
- **Purpose:** Invoke the configured chat LLM and return cleaned text.

---

## `agents/composer_agent.py`

**Category:** Production module

### Class `ComposerAgent`

- **Base:** `BaseAgent`
- **Purpose:** Final synthesis agent that produces the polished user-facing output.
- **Source:** [`composer_agent.py`](file:///C:/Users/nguye/PROJECTS/your-learning/agents/composer_agent.py#L5)

#### `ComposerAgent.run()`

```python
def run(self, task: AgentTask, blackboard: BlackboardState)
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

---

## `agents/critic_agent.py`

**Category:** Production module

### Class `CriticAgent`

- **Base:** `BaseAgent`
- **Purpose:** Verifier agent for grounding, correctness, and pedagogy.
- **Source:** [`critic_agent.py`](file:///C:/Users/nguye/PROJECTS/your-learning/agents/critic_agent.py#L5)

#### `CriticAgent.run()`

```python
def run(self, task: AgentTask, blackboard: BlackboardState)
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

---

## `agents/graph_agent.py`

**Category:** Production module

### Class `GraphAgent`

- **Base:** `BaseAgent`
- **Purpose:** Tool agent responsible for Neo4j graph context retrieval.
- **Source:** [`graph_agent.py`](file:///C:/Users/nguye/PROJECTS/your-learning/agents/graph_agent.py#L5)

#### `GraphAgent.run()`

```python
def run(self, task: AgentTask, blackboard: BlackboardState)
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

---

## `agents/memory_agent.py`

**Category:** Production module

### Class `MemoryAgent`

- **Base:** `BaseAgent`
- **Purpose:** Tool agent responsible for Qdrant and Neo4j learner memory.
- **Source:** [`memory_agent.py`](file:///C:/Users/nguye/PROJECTS/your-learning/agents/memory_agent.py#L8)

#### `MemoryAgent.run()`

```python
def run(self, task: AgentTask, blackboard: BlackboardState)
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `MemoryAgent.retrieve_memory()`

```python
def retrieve_memory(self, task: AgentTask, blackboard: BlackboardState)
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `MemoryAgent.persist_turn()`

```python
def persist_turn(self, task: AgentTask, blackboard: BlackboardState)
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

---

## `agents/planner_agent.py`

**Category:** Production module

### Class `PlannerAgent`

- **Base:** `BaseAgent`
- **Purpose:** Dynamic planner that creates a multi-agent execution plan.
- **Source:** [`planner_agent.py`](file:///C:/Users/nguye/PROJECTS/your-learning/agents/planner_agent.py#L7)

#### `PlannerAgent.run()`

```python
def run(self, task: AgentTask, blackboard: BlackboardState)
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

---

## `agents/specialists.py`

**Category:** Production module

### Class `SpecialistAgent`

- **Base:** `BaseAgent`
- **Purpose:** Reusable base class for teaching specialist agents.
- **Source:** [`specialists.py`](file:///C:/Users/nguye/PROJECTS/your-learning/agents/specialists.py#L5)

#### `SpecialistAgent.run()`

```python
def run(self, task: AgentTask, blackboard: BlackboardState)
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

---

## `agents/supervisor_agent.py`

**Category:** Production module

### Class `SupervisorAgent`

- **Base:** `BaseAgent`
- **Purpose:** Top-level controller for selecting and monitoring agentic workflows.
- **Source:** [`supervisor_agent.py`](file:///C:/Users/nguye/PROJECTS/your-learning/agents/supervisor_agent.py#L5)

#### `SupervisorAgent.run()`

```python
def run(self, task: AgentTask, blackboard: BlackboardState)
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

---

## `application/assessment_service.py`

**Category:** TODO application scaffold

### Class `AssessmentService`

- **Base:** `object`
- **Purpose:** No docstring yet; inspect the function name and module notes before use.
- **Source:** [`assessment_service.py`](file:///C:/Users/nguye/PROJECTS/your-learning/application/assessment_service.py#L16)

#### `AssessmentService.__init__()`

```python
def __init__(self, runtime_engine: Any)
```

- **Visibility:** Dunder / lifecycle
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `AssessmentService.generate_quiz()`

```python
def generate_quiz(self, request: QuizRequest) -> dict[str, Any]
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `AssessmentService.grade_quiz()`

```python
def grade_quiz(self, request: GradeQuizRequest) -> dict[str, Any]
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

---

## `application/facade.py`

**Category:** TODO application scaffold

### Class `LearningApplication`

- **Base:** `object`
- **Purpose:** Groups framework-neutral use cases without implementing transport logic.
- **Source:** [`facade.py`](file:///C:/Users/nguye/PROJECTS/your-learning/application/facade.py#L17)

#### `LearningApplication.__init__()`

```python
def __init__(self, *, ingestion: IngestionService, learning: LearningService, qa: QAService, assessment: AssessmentService, library: LibraryService)
```

- **Visibility:** Dunder / lifecycle
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

---

## `application/ingestion_service.py`

**Category:** TODO application scaffold

### Class `IngestionService`

- **Base:** `object`
- **Purpose:** No docstring yet; inspect the function name and module notes before use.
- **Source:** [`ingestion_service.py`](file:///C:/Users/nguye/PROJECTS/your-learning/application/ingestion_service.py#L19)

#### `IngestionService.__init__()`

```python
def __init__(self, vector_store: Any, graph_store: Any, llm_service: Any, document_processor: Any)
```

- **Visibility:** Dunder / lifecycle
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `IngestionService.ingest()`

```python
def ingest(self, request: IngestDocumentRequest) -> Iterable[ApplicationEvent]
```

- **Visibility:** Public / callable
- **Purpose:** Ingest one document while reporting framework-neutral progress events.

---

## `application/learning_service.py`

**Category:** TODO application scaffold

### Class `LearningService`

- **Base:** `object`
- **Purpose:** No docstring yet; inspect the function name and module notes before use.
- **Source:** [`learning_service.py`](file:///C:/Users/nguye/PROJECTS/your-learning/application/learning_service.py#L18)

#### `LearningService.__init__()`

```python
def __init__(self, runtime_engine: Any)
```

- **Visibility:** Dunder / lifecycle
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `LearningService.stream_lesson()`

```python
def stream_lesson(self, request: LessonRequest) -> Iterable[ApplicationEvent]
```

- **Visibility:** Public / callable
- **Purpose:** Stream one teaching step independently of any UI framework.

---

## `application/library_service.py`

**Category:** TODO application scaffold

### Class `LibraryService`

- **Base:** `object`
- **Purpose:** No docstring yet; inspect the function name and module notes before use.
- **Source:** [`library_service.py`](file:///C:/Users/nguye/PROJECTS/your-learning/application/library_service.py#L14)

#### `LibraryService.__init__()`

```python
def __init__(self, vector_store: Any, graph_store: Any)
```

- **Visibility:** Dunder / lifecycle
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `LibraryService.list_documents()`

```python
def list_documents(self) -> list[str]
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `LibraryService.get_curriculum()`

```python
def get_curriculum(self, file_name: str) -> dict[str, Any]
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `LibraryService.get_progress()`

```python
def get_progress(self, user_id: str, file_name: str) -> dict[str, Any]
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `LibraryService.get_graph()`

```python
def get_graph(self, user_id: str, file_name: str, chapter_name: str | None=None) -> dict[str, Any]
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

---

## `application/qa_service.py`

**Category:** TODO application scaffold

### Class `QAService`

- **Base:** `object`
- **Purpose:** No docstring yet; inspect the function name and module notes before use.
- **Source:** [`qa_service.py`](file:///C:/Users/nguye/PROJECTS/your-learning/application/qa_service.py#L16)

#### `QAService.__init__()`

```python
def __init__(self, runtime_engine: Any)
```

- **Visibility:** Dunder / lifecycle
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `QAService.ask()`

```python
def ask(self, request: QuestionRequest) -> AnswerResult
```

- **Visibility:** Public / callable
- **Purpose:** Answer one local or global question.

---

## `core/data_ingestion.py`

**Category:** Production module

### Module functions

#### `run_ingestion_pipeline()`

```python
def run_ingestion_pipeline(markdown_content: str, file_name: str, db, llm, dag)
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.
- **Source:** [`data_ingestion.py`](file:///C:/Users/nguye/PROJECTS/your-learning/core/data_ingestion.py#L6)

---

## `core/interfaces.py`

**Category:** Production module

### Class `ILLMService`

- **Base:** `ABC`
- **Purpose:** Standard interface for LLM services (Extraction & Q&A).
- **Source:** [`interfaces.py`](file:///C:/Users/nguye/PROJECTS/your-learning/core/interfaces.py#L4)

#### `ILLMService.extract_section_curriculum_and_dag()`

```python
def extract_section_curriculum_and_dag(self, section_text: str, existing_nodes: List[str]=None) -> Dict[str, Any]
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `ILLMService.generate_hypothetical_questions()`

```python
def generate_hypothetical_questions(self, section_text: str, num_questions: int=5) -> List[str]
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `ILLMService.rerank_candidate_questions()`

```python
def rerank_candidate_questions(self, user_query: str, candidates: List[Dict[str, str]]) -> str
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

### Class `IVectorStore`

- **Base:** `ABC`
- **Purpose:** Interface for Vector Database.
- **Source:** [`interfaces.py`](file:///C:/Users/nguye/PROJECTS/your-learning/core/interfaces.py#L20)

#### `IVectorStore.upsert_section()`

```python
def upsert_section(self, text: str, metadata: dict, parent_id: str) -> None
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `IVectorStore.upsert_questions()`

```python
def upsert_questions(self, questions: List[str], parent_id: str, source_file: str) -> None
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `IVectorStore.upsert_curriculum_group()`

```python
def upsert_curriculum_group(self, group_data: dict, parent_id: str, source_file: str, chapter: str, section: str) -> None
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `IVectorStore.get_curriculum_groups()`

```python
def get_curriculum_groups(self, target_file: str, target_section: str) -> List[Dict[str, Any]]
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `IVectorStore.get_section_exact()`

```python
def get_section_exact(self, target_file: str, target_section: str) -> List[Dict[str, Any]]
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `IVectorStore.search_candidates_and_fetch_parent()`

```python
def search_candidates_and_fetch_parent(self, query: str, llm_service: ILLMService, target_file: str='') -> List[Dict[str, Any]]
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `IVectorStore.upsert_user_memory()`

```python
def upsert_user_memory(self, user_id: str, turn_id: str, query: str, answer: str, summary: str)
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `IVectorStore.search_semantic_memory()`

```python
def search_semantic_memory(self, user_id: str, query: str, limit: int=5) -> List[Dict]
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `IVectorStore.delete_source()`

```python
def delete_source(self, source_name: str) -> None
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

### Class `IGraphStore`

- **Base:** `ABC`
- **Purpose:** Interface for Graph Database.
- **Source:** [`interfaces.py`](file:///C:/Users/nguye/PROJECTS/your-learning/core/interfaces.py#L60)

#### `IGraphStore.save_knowledge_graph()`

```python
def save_knowledge_graph(self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]], file_name: str, chapter_name: str, section_title: str, main_entities: List[str])
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `IGraphStore.mark_concept_as_learned()`

```python
def mark_concept_as_learned(self, concept_id: str, user_id: str='guest_01')
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `IGraphStore.get_unlearned_prerequisites()`

```python
def get_unlearned_prerequisites(self, target_concept: str, max_depth: int=2, user_id: str='guest_01') -> List[str]
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `IGraphStore.get_learned_prerequisites()`

```python
def get_learned_prerequisites(self, target_concept: str, max_depth: int=3, user_id: str='guest_01') -> List[str]
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `IGraphStore.get_concept_subgraph()`

```python
def get_concept_subgraph(self, target_concept: str, max_depth: int=1) -> Dict[str, List[str]]
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `IGraphStore.get_graph_context()`

```python
def get_graph_context(self, node_names: List[str], search_mode: str='search') -> List[Dict[str, str]]
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `IGraphStore.save_chat_turn()`

```python
def save_chat_turn(self, user_id: str, turn_id: str, query: str, raw_answer: str, summary: str, concept_ids: list=None, target_file: str='', target_section: str='')
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `IGraphStore.get_recent_history()`

```python
def get_recent_history(self, user_id: str, limit: int=5) -> List[Dict]
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `IGraphStore.get_raw_chat_turns()`

```python
def get_raw_chat_turns(self, turn_ids: List[str]) -> List[Dict]
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `IGraphStore.get_raw_chat_turns_by_user()`

```python
def get_raw_chat_turns_by_user(self, user_id: str) -> List[Dict]
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `IGraphStore.delete_source()`

```python
def delete_source(self, source_name: str) -> None
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

---

## `database/document_processor.py`

**Category:** Production module

### Class `MathAwareDocumentProcessor`

- **Base:** `object`
- **Purpose:** No docstring yet; inspect the function name and module notes before use.
- **Source:** [`document_processor.py`](file:///C:/Users/nguye/PROJECTS/your-learning/database/document_processor.py#L9)

#### `MathAwareDocumentProcessor.__init__()`

```python
def __init__(self)
```

- **Visibility:** Dunder / lifecycle
- **Purpose:** - Reason: Simplified document processor focusing only on Structural Parsing (TOC & Sections). - Function: Initializes without max_chunk_size since we now preserve full section macro-contexts.

#### `MathAwareDocumentProcessor.process_markdown()`

```python
def process_markdown(self, markdown_text: str) -> Tuple[List[Dict[str, Any]], Dict[str, List[str]]]
```

- **Visibility:** Public / callable
- **Purpose:** - Reason: To parse the structural hierarchy of the textbook without unnecessarily breaking math blocks. - Function: Splits markdown by headers, builds a Table of Contents (TOC), and yields full sections. - Usage: Called by the data ingestion pipeline. - Parameters:     - markdown_text (str): The raw string content of the markdown file. - Returns: A tuple containing the list of section documents and the TOC dictionary.

---

## `database/semantic_dag.py`

**Category:** Production module

### Class `Neo4jManager`

- **Base:** `IGraphStore`
- **Purpose:** - Reason for use: Manages the Global Knowledge Graph, effectively solving the issue of data overwriting when multiple books have the same Section name.
- **Source:** [`semantic_dag.py`](file:///C:/Users/nguye/PROJECTS/your-learning/database/semantic_dag.py#L8)

#### `Neo4jManager.__init__()`

```python
def __init__(self, uri: str, user: str, password: str)
```

- **Visibility:** Dunder / lifecycle
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `Neo4jManager.close()`

```python
def close(self)
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `Neo4jManager._is_available()`

```python
def _is_available(self) -> bool
```

- **Visibility:** Internal helper - do not call from UI
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `Neo4jManager._initialize_user()`

```python
def _initialize_user(self, user_id: str='guest_01')
```

- **Visibility:** Internal helper - do not call from UI
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `Neo4jManager.save_table_of_contents()`

```python
def save_table_of_contents(self, file_name: str, toc_tree: Dict[str, Any])
```

- **Visibility:** Public / callable
- **Purpose:** Persist a document table of contents in Neo4j so it survives app restarts.

#### `Neo4jManager.get_table_of_contents()`

```python
def get_table_of_contents(self, file_name: str) -> Dict[str, Any]
```

- **Visibility:** Public / callable
- **Purpose:** Load a persisted document table of contents from Neo4j.

#### `Neo4jManager.delete_table_of_contents()`

```python
def delete_table_of_contents(self, file_name: str)
```

- **Visibility:** Public / callable
- **Purpose:** Delete persisted TOC metadata for one document.

#### `Neo4jManager.save_knowledge_graph()`

```python
def save_knowledge_graph(self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]], file_name: str, chapter_name: str, section_title: str, main_entities: List[str])
```

- **Visibility:** Public / callable
- **Purpose:** - Function: Saves Graph (including Nodes with types and Edges with relations). Creates absolute positioning locators.

#### `Neo4jManager.mark_concept_as_learned()`

```python
def mark_concept_as_learned(self, concept_id: str, user_id: str='guest_01')
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `Neo4jManager.reset_user_data()`

```python
def reset_user_data(self, user_id: str='guest_01')
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `Neo4jManager.get_unlearned_prerequisites()`

```python
def get_unlearned_prerequisites(self, target_concept: str, max_depth: int=2, user_id: str='guest_01') -> List[str]
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `Neo4jManager.get_learned_prerequisites()`

```python
def get_learned_prerequisites(self, target_concept: str, max_depth: int=3, user_id: str='guest_01') -> List[str]
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `Neo4jManager.get_concept_subgraph()`

```python
def get_concept_subgraph(self, target_concept: str, max_depth: int=1) -> Dict[str, List[str]]
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `Neo4jManager.get_graph_context()`

```python
def get_graph_context(self, node_names: List[str], search_mode: str='search') -> List[Dict[str, str]]
```

- **Visibility:** Public / callable
- **Purpose:** - Reason: Dual-mode graph traversal for different cognitive tasks (Learning vs. Q&A). - Function: Executes targeted Cypher queries based on the search_mode. - Parameters:     - node_names (List[str]): The target entities to anchor the search.     - search_mode (str): "semi_search" for backwards 1-hop, "search" for undirected 2-hops.

#### `Neo4jManager.get_visual_graph()`

```python
def get_visual_graph(self, user_id: str, locator: str) -> Dict[str, List[Dict[str, Any]]]
```

- **Visibility:** Public / callable
- **Purpose:** - Reason: Specifically designed for UI visualization. - Function: Fetches all concepts belonging to a specific source locator and their relationships. - Returns: A dictionary with 'nodes' and 'edges' formatted for visualization libraries.

#### `Neo4jManager.get_global_visual_graph()`

```python
def get_global_visual_graph(self, user_id: str, file_name: str) -> Dict[str, List[Dict[str, Any]]]
```

- **Visibility:** Public / callable
- **Purpose:** - Function: Fetches all concepts belonging to an entire file (all chapters/sections).

#### `Neo4jManager.get_chapter_visual_graph()`

```python
def get_chapter_visual_graph(self, user_id: str, file_name: str, chapter_name: str) -> Dict[str, List[Dict[str, Any]]]
```

- **Visibility:** Public / callable
- **Purpose:** - Function: Fetches all concepts belonging to a specific chapter within a file.

#### `Neo4jManager.get_recent_history()`

```python
def get_recent_history(self, user_id: str, limit: int=5) -> List[Dict]
```

- **Visibility:** Public / callable
- **Purpose:** Fetches the N most recent chat summaries for context window.

#### `Neo4jManager.get_raw_chat_turns()`

```python
def get_raw_chat_turns(self, turn_ids: List[str]) -> List[Dict]
```

- **Visibility:** Public / callable
- **Purpose:** Fetches raw data when LLM Router requests it.

#### `Neo4jManager.get_raw_chat_turns_by_user()`

```python
def get_raw_chat_turns_by_user(self, user_id: str) -> List[Dict]
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `Neo4jManager.get_file_learning_progress()`

```python
def get_file_learning_progress(self, user_id: str, file_name: str) -> Dict[str, Any]
```

- **Visibility:** Public / callable
- **Purpose:** - Function: Calculates learning progress for a specific file. - Returns: Dictionary with total_concepts, learned_concepts, and percentage.

#### `Neo4jManager.save_chat_turn()`

```python
def save_chat_turn(self, user_id: str, turn_id: str, query: str, raw_answer: str, summary: str, concept_ids: list=None, target_file: str='', target_section: str='')
```

- **Visibility:** Public / callable
- **Purpose:** - LÃ­ do táº¡i sao dÃ¹ng: LÆ°u trá»¯ Episodic Memory vÃ o Neo4j lÃ m Nguá»“n Sá»± Tháº­t Duy Nháº¥t (SSOT). - Chá»©c nÄƒng: LÆ°u lÆ°á»£t chat, liÃªn káº¿t vá»›i User, NHIá»€U Concept vÃ  gáº¯n metadata Section. - CÃ¡ch dÃ¹ng: Gá»i sau khi LLM xá»­ lÃ½ xong má»™t lÆ°á»£t há»c/há»i Ä‘Ã¡p.

#### `Neo4jManager.get_history_by_section()`

```python
def get_history_by_section(self, user_id: str, target_file: str, target_section: str, limit: int=50) -> List[Dict]
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `Neo4jManager.delete_source()`

```python
def delete_source(self, source_name: str) -> None
```

- **Visibility:** Public / callable
- **Purpose:** - Function: Removes all knowledge graph nodes and chat turns associated with a file.

---

## `database/structural_db.py`

**Category:** Production module

### Class `QdrantVectorStore`

- **Base:** `IVectorStore`
- **Purpose:** No docstring yet; inspect the function name and module notes before use.
- **Source:** [`structural_db.py`](file:///C:/Users/nguye/PROJECTS/your-learning/database/structural_db.py#L15)

#### `QdrantVectorStore.__init__()`

```python
def __init__(self, host: str='localhost', port: int=6333, api_key: str=None, collection_name: str='math_curriculum_v4')
```

- **Visibility:** Dunder / lifecycle
- **Purpose:** - Reason: To manage vector embeddings and handle collection initialization conflicts. - Function: Initializes the Qdrant client, embedding model, and robustly ensures required collections exist. - Usage: Instantiated once at application startup. - Parameters:     - collection_name (str): The base name for the collections (default: "math_curriculum_v4"). - Returns: None. - Alternatives: Manual directory cleanup before startup.

#### `QdrantVectorStore._ensure_collections_and_indexes()`

```python
def _ensure_collections_and_indexes(self) -> None
```

- **Visibility:** Internal helper - do not call from UI
- **Purpose:** Ensure Qdrant collections and payload indexes required by filters exist.

#### `QdrantVectorStore._reset_fastembed_cache()`

```python
def _reset_fastembed_cache(self) -> None
```

- **Visibility:** Internal helper - do not call from UI
- **Purpose:** Remove corrupted FastEmbed cache so the ONNX model can be downloaded again.

#### `QdrantVectorStore._reinitialize_embed_model()`

```python
def _reinitialize_embed_model(self) -> None
```

- **Visibility:** Internal helper - do not call from UI
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `QdrantVectorStore._embed_query_safe()`

```python
def _embed_query_safe(self, text: str) -> List[float]
```

- **Visibility:** Internal helper - do not call from UI
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `QdrantVectorStore._embed_documents_safe()`

```python
def _embed_documents_safe(self, texts: List[str]) -> List[List[float]]
```

- **Visibility:** Internal helper - do not call from UI
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `QdrantVectorStore.upsert_section()`

```python
def upsert_section(self, text: str, metadata: dict, parent_id: str) -> None
```

- **Visibility:** Public / callable
- **Purpose:** - Reason: To store the macro-context of a textbook section. - Function: Embeds raw text and saves it as a parent node. - Usage: Called during the data ingestion phase. - Parameters: text, metadata, parent_id. - Returns: None.

#### `QdrantVectorStore.upsert_questions()`

```python
def upsert_questions(self, qa_pairs: List[Dict[str, str]], parent_id: str, source_file: str) -> None
```

- **Visibility:** Public / callable
- **Purpose:** - Function: Links multiple hypothetical questions and their key knowledge to a parent section.

#### `QdrantVectorStore.upsert_curriculum_group()`

```python
def upsert_curriculum_group(self, group_data: dict, parent_id: str, source_file: str, chapter: str, section: str) -> None
```

- **Visibility:** Public / callable
- **Purpose:** - Reason: To store the AOT roadmap and agent queues. - Function: Extracts the pre-assigned agents and saves them into the payload. - Usage: Core function for the new roadmap-driven architecture. - Parameters: group_data, parent_id, source_file, chapter, section. - Returns: None.

#### `QdrantVectorStore.get_curriculum_groups()`

```python
def get_curriculum_groups(self, target_file: str, target_section: str) -> List[Dict[str, Any]]
```

- **Visibility:** Public / callable
- **Purpose:** - Function: Retrieves pre-compiled roadmap steps. - Returns: Sorted list of teaching steps.

#### `QdrantVectorStore.get_section_exact()`

```python
def get_section_exact(self, target_file: str, target_section: str) -> List[Dict[str, Any]]
```

- **Visibility:** Public / callable
- **Purpose:** - Function: Direct text retrieval by metadata match.

#### `QdrantVectorStore.search_candidates_and_fetch_parent()`

```python
def search_candidates_and_fetch_parent(self, query: str, llm_service: ILLMService, target_file: str='') -> List[Dict[str, Any]]
```

- **Visibility:** Public / callable
- **Purpose:** - Function: Advanced HyDE search with semantic reranking.

#### `QdrantVectorStore.upsert_user_memory()`

```python
def upsert_user_memory(self, user_id: str, turn_id: str, query: str, answer: str, summary: str)
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `QdrantVectorStore.search_semantic_memory()`

```python
def search_semantic_memory(self, user_id: str, query: str, limit: int=5) -> List[Dict]
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `QdrantVectorStore.delete_user_history()`

```python
def delete_user_history(self, user_id: str='guest_01') -> None
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `QdrantVectorStore.get_section_questions()`

```python
def get_section_questions(self, parent_id: str) -> List[str]
```

- **Visibility:** Public / callable
- **Purpose:** - Function: Retrieves all pre-generated questions for a specific section.

#### `QdrantVectorStore.delete_source()`

```python
def delete_source(self, source_name: str) -> None
```

- **Visibility:** Public / callable
- **Purpose:** - Function: Deletes all points associated with a specific source file across collections.

---

## `main.py`

**Category:** Production module

### Module functions

#### `init_system()`

```python
def init_system()
```

- **Visibility:** Public / callable
- **Purpose:** - Reason: Initialize all core services (Qdrant, Neo4j, LLM, Engine) exactly once and cache them in Streamlit to avoid reloading on every UI refresh. - Function: Establish DB connections and assemble the RuntimeEngine. - Usage: Called automatically when the Streamlit app starts. - Parameters: None. - Returns: RuntimeEngine - The central engine that coordinates all tasks. - Alternatives: None.
- **Source:** [`main.py`](file:///C:/Users/nguye/PROJECTS/your-learning/main.py#L28)

#### `_sync_section_history()`

```python
def _sync_section_history()
```

- **Visibility:** Internal helper - do not call from UI
- **Purpose:** - Reason: Solves Streamlit's state evaporation on tab switch or F5. Neo4j becomes the Single Source of Truth. - Function: Pulls chat history from Neo4j, classifies into LEARNING and LOCAL_QA for correct tab rendering.   Restores the current lesson index (seq_idx). - Usage: Called automatically when st.session_state.current_loaded_section changes. - Parameters: None (reads directly from st.session_state). - Returns: None.
- **Source:** [`main.py`](file:///C:/Users/nguye/PROJECTS/your-learning/main.py#L261)

#### `render_knowledge_graph()`

```python
def render_knowledge_graph(engine, user_id, chapter_name=None, file_name=None)
```

- **Visibility:** Public / callable
- **Purpose:** Helper to render graph using agraph for either a specific chapter or an entire file.
- **Source:** [`main.py`](file:///C:/Users/nguye/PROJECTS/your-learning/main.py#L313)

---

## `orchestrator/llm_factory.py`

**Category:** Production module

### Class `LLMFactory`

- **Base:** `object`
- **Purpose:** Factory to instantiate the appropriate LangChain ChatModel based on configuration.
- **Source:** [`llm_factory.py`](file:///C:/Users/nguye/PROJECTS/your-learning/orchestrator/llm_factory.py#L4)

#### `LLMFactory.create_llm()`

```python
def create_llm(provider: str, model_name: str, base_url: str, temperature: float, max_tokens: int=2048, top_p: float=0.2, **kwargs) -> BaseChatModel
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

---

## `orchestrator/llm_service.py`

**Category:** Production module

### Class `LLMService`

- **Base:** `ILLMService`
- **Purpose:** No docstring yet; inspect the function name and module notes before use.
- **Source:** [`llm_service.py`](file:///C:/Users/nguye/PROJECTS/your-learning/orchestrator/llm_service.py#L58)

#### `LLMService.__init__()`

```python
def __init__(self, llm: BaseChatModel, chat_llm: BaseChatModel)
```

- **Visibility:** Dunder / lifecycle
- **Purpose:** - Function: Initializes the connection using injected LLM instances.

#### `LLMService._extract_json_from_text()`

```python
def _extract_json_from_text(self, text: str) -> str
```

- **Visibility:** Internal helper - do not call from UI
- **Purpose:** - Reason: As a safety net in case the LLM wraps the JSON in markdown code blocks despite JSON mode. - Function: Uses Regular Expressions to pinpoint and extract pure JSON. - Usage: Internal helper called after every LLM generation. - Parameters:     - text (str): The raw text output from the LLM. - Returns: A cleaned JSON string. - Alternatives: Direct JSON parsing.

#### `LLMService.extract_section_curriculum_and_dag()`

```python
def extract_section_curriculum_and_dag(self, section_text: str, existing_nodes: List[str]=None) -> Dict[str, Any]
```

- **Visibility:** Public / callable
- **Purpose:** - Reason: Replaces the Runtime Router. Performs AOT routing, Ontology extraction, and Entity Tagging. - Function: Extracts main entities, teaching roadmap, and the structured knowledge graph. - Usage: Called by the data ingestion pipeline. - Parameters:     - section_text (str): The raw text of the textbook section. - Returns: A dictionary containing 'main_entities', 'teaching_roadmap', and 'knowledge_graph'. - Alternatives: Sequential LLM chains (slower).

#### `LLMService.generate_hypothetical_questions()`

```python
def generate_hypothetical_questions(self, section_text: str, num_questions: int=5) -> List[Dict[str, str]]
```

- **Visibility:** Public / callable
- **Purpose:** - Reason: To implement HyDE (Hypothetical Document Embeddings). - Function: Generates FAQ-style questions and their concise answers (Key Knowledge).

#### `LLMService.generate_quiz()`

```python
def generate_quiz(self, section_text: str) -> tuple[List[Dict], Optional[str]]
```

- **Visibility:** Public / callable
- **Purpose:** - Function: Generates a list of multiple choice questions based on section content.

#### `LLMService.generate_source_briefing()`

```python
def generate_source_briefing(self, file_name: str, full_text: str) -> tuple[Dict, Optional[str]]
```

- **Visibility:** Public / callable
- **Purpose:** - Function: Generates a high-level briefing based on the ACTUAL FULL CONTENT.

#### `LLMService.rerank_candidate_questions()`

```python
def rerank_candidate_questions(self, user_query: str, candidates: List[Dict[str, str]]) -> List[str]
```

- **Visibility:** Public / callable
- **Purpose:** - Reason: Rerank vector search results using LLM reasoning. - Function: Identifies the 1-2 hypothetical questions most semantically similar to the user's query. - Returns: A list of unique 'parent_id's.

---

## `runtime/agent_runtime.py`

**Category:** Production module

### Class `MultiAgentRuntime`

- **Base:** `object`
- **Purpose:** Executes GraphRAG-grounded pedagogical workflows with formal agents.
- **Source:** [`agent_runtime.py`](file:///C:/Users/nguye/PROJECTS/your-learning/runtime/agent_runtime.py#L23)

#### `MultiAgentRuntime.__init__()`

```python
def __init__(self, llm_service: Any=None, vector_db: Any=None, graph_db: Any=None, agents: Optional[Dict[str, Any]]=None, critic_enabled: bool=True, max_revision_loops: int=1, stream_agent_outputs: bool=True, tracer: Optional[RuntimeTracer]=None)
```

- **Visibility:** Dunder / lifecycle
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `MultiAgentRuntime._build_default_agents()`

```python
def _build_default_agents(self) -> Dict[str, Any]
```

- **Visibility:** Internal helper - do not call from UI
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `MultiAgentRuntime.build_blackboard()`

```python
def build_blackboard(self, *, user_id: str='guest_01', target_file: str='', target_section: str='', step_data: Optional[Dict[str, Any]]=None, macro_context: str='', micro_context: str='') -> BlackboardState
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `MultiAgentRuntime.execute_learning()`

```python
def execute_learning(self, *, user_id: str, target_file: str, target_section: str, step_data: Dict[str, Any], macro_context: str, anchor_nodes: Optional[list[str]]=None) -> Iterable[Dict[str, Any]]
```

- **Visibility:** Public / callable
- **Purpose:** Run a learning step and yield Streamlit-compatible events.

#### `MultiAgentRuntime.generate_assessment()`

```python
def generate_assessment(self, *, user_id: str, target_file: str, target_section: str, step_data: Dict[str, Any], macro_context: str, question_count: int=5) -> Dict[str, Any]
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `MultiAgentRuntime.grade_assessment()`

```python
def grade_assessment(self, *, quiz: Dict[str, Any], answers: Dict[str, Any], user_id: str='guest_01', pass_threshold: float=0.75) -> Dict[str, Any]
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `MultiAgentRuntime._run_critic()`

```python
def _run_critic(self, reviewed_agent: str, blackboard: BlackboardState)
```

- **Visibility:** Internal helper - do not call from UI
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `MultiAgentRuntime._with_support_steps()`

```python
def _with_support_steps(self, runtime_plan: RuntimePlan, *, include_graph: bool, include_memory: bool) -> RuntimePlan
```

- **Visibility:** Internal helper - do not call from UI
- **Purpose:** Expose pre-planner support agents in the persisted runtime plan without rerunning them.

#### `MultiAgentRuntime._get_runtime_plan()`

```python
def _get_runtime_plan(self, blackboard: BlackboardState, required_agents: list[str]) -> RuntimePlan
```

- **Visibility:** Internal helper - do not call from UI
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

---

## `runtime/blackboard.py`

**Category:** Production module

### Class `Blackboard`

- **Base:** `object`
- **Purpose:** Convenience wrapper around BlackboardState for agent collaboration.
- **Source:** [`blackboard.py`](file:///C:/Users/nguye/PROJECTS/your-learning/runtime/blackboard.py#L6)

#### `Blackboard.__init__()`

```python
def __init__(self, state: Optional[BlackboardState]=None, **kwargs)
```

- **Visibility:** Dunder / lifecycle
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `Blackboard.write_message()`

```python
def write_message(self, message: AgentMessage) -> None
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `Blackboard.write_critic_report()`

```python
def write_critic_report(self, report: CriticReport) -> None
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `Blackboard.set_artifact()`

```python
def set_artifact(self, key: str, value: Any) -> None
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `Blackboard.get_artifact()`

```python
def get_artifact(self, key: str, default: Any=None) -> Any
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `Blackboard.set_final_output()`

```python
def set_final_output(self, content: str) -> None
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `Blackboard.messages_by_agent()`

```python
def messages_by_agent(self, agent_name: str) -> List[AgentMessage]
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `Blackboard.latest_message()`

```python
def latest_message(self, agent_name: Optional[str]=None) -> Optional[AgentMessage]
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `Blackboard.context_snapshot()`

```python
def context_snapshot(self) -> Dict[str, Any]
```

- **Visibility:** Public / callable
- **Purpose:** Return a serializable snapshot useful for prompts and debugging.

---

## `runtime/engine.py`

**Category:** Production module

### Class `SupportAgent`

- **Base:** `object`
- **Purpose:** No docstring yet; inspect the function name and module notes before use.
- **Source:** [`engine.py`](file:///C:/Users/nguye/PROJECTS/your-learning/runtime/engine.py#L10)

#### `SupportAgent.__init__()`

```python
def __init__(self, llm: BaseChatModel)
```

- **Visibility:** Dunder / lifecycle
- **Purpose:** - Reason: To handle out-of-band user queries without disrupting the main Learning Queue. - Function: Generates isolated, single-shot answers based on Graph and Chat context. - Usage: Called by RuntimeEngine during LOCAL_QA or GLOBAL_QA.

#### `SupportAgent.summarize_turn()`

```python
def summarize_turn(self, query: str, answer: str) -> str
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `SupportAgent.route_and_answer()`

```python
def route_and_answer(self, query: str, semantic_memory: list, recent_history: list, graph_context: list=None, macro_context: str='', micro_context: str='', raw_details: list=None) -> dict
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

### Class `RuntimeEngine`

- **Base:** `object`
- **Purpose:** No docstring yet; inspect the function name and module notes before use.
- **Source:** [`engine.py`](file:///C:/Users/nguye/PROJECTS/your-learning/runtime/engine.py#L143)

#### `RuntimeEngine.__init__()`

```python
def __init__(self, orchestrator, vector_db, graph_db, support_agent, multi_agent_runtime=None, use_multi_agent_runtime: bool=False)
```

- **Visibility:** Dunder / lifecycle
- **Purpose:** - Reason: The Central Dispatcher (Air Traffic Controller) of the system. - Function: Routes actions to LEARNING or QA, manages memory, and handles DB retrievals. - Usage: Instantiated once at the application entry point (e.g., app.py). - Parameters: Runtime orchestrators, database stores, and support agents.

#### `RuntimeEngine.save_learning_turn()`

```python
def save_learning_turn(self, user_id: str, target_file: str, target_section: str, step_data: dict, full_lecture_text: str)
```

- **Visibility:** Public / callable
- **Purpose:** - Reason: Decouples lecture persistence logic from the UI streaming flow. - Function: Assigns a static summary, saves raw text to Qdrant, and links all entities in Neo4j.

#### `RuntimeEngine._stream_learning_action()`

```python
def _stream_learning_action(self, target_file: str, target_section: str, step_data: dict, user_id: str)
```

- **Visibility:** Internal helper - do not call from UI
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `RuntimeEngine.process_action()`

```python
def process_action(self, action_mode: str, query: str='', target_file: str='', target_section: str='', step_data: dict=None, user_id: str='guest_01')
```

- **Visibility:** Public / callable
- **Purpose:** - Reason: Unified entry point for all UI interactions. - Function: Executes the distinct logic flows for LEARNING, LOCAL_QA, and GLOBAL_QA.

#### `RuntimeEngine.get_lesson_quiz()`

```python
def get_lesson_quiz(self, target_file: str, target_section: str) -> tuple[List[Dict], Optional[str]]
```

- **Visibility:** Public / callable
- **Purpose:** - Logic: Fetches exact section text and generates MCQ quiz. - Returns: (Quiz List, Error Message)

#### `RuntimeEngine.grade_lesson_quiz()`

```python
def grade_lesson_quiz(self, quiz: List[Dict], answers: Dict[str, int], user_id: str='guest_01') -> Dict[str, Any]
```

- **Visibility:** Public / callable
- **Purpose:** Grade a generated quiz and return feedback plus remediation guidance.

#### `RuntimeEngine.get_source_briefing()`

```python
def get_source_briefing(self, target_file: str) -> tuple[Dict, Optional[str]]
```

- **Visibility:** Public / callable
- **Purpose:** - Logic: Fetches all sections, concatenates them, and generates a global briefing. - Returns: (Briefing Dict, Error Message)

#### `RuntimeEngine.reset_all_user_data()`

```python
def reset_all_user_data(self, user_id: str='guest_01')
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

---

## `runtime/protocols.py`

**Category:** Production module

### Module functions

#### `clean_think_tags()`

```python
def clean_think_tags(text: str) -> str
```

- **Visibility:** Public / callable
- **Purpose:** Remove reasoning traces emitted inside <think>...</think> blocks.
- **Source:** [`protocols.py`](file:///C:/Users/nguye/PROJECTS/your-learning/runtime/protocols.py#L8)

#### `strip_markdown_fences()`

```python
def strip_markdown_fences(text: str) -> str
```

- **Visibility:** Public / callable
- **Purpose:** Remove surrounding Markdown code fences from model output.
- **Source:** [`protocols.py`](file:///C:/Users/nguye/PROJECTS/your-learning/runtime/protocols.py#L15)

#### `normalize_latex_markdown()`

```python
def normalize_latex_markdown(text: str) -> str
```

- **Visibility:** Public / callable
- **Purpose:** Normalize common malformed LLM LaTeX into Streamlit-friendly Markdown math.
- **Source:** [`protocols.py`](file:///C:/Users/nguye/PROJECTS/your-learning/runtime/protocols.py#L24)

#### `extract_json_object()`

```python
def extract_json_object(text: str) -> str
```

- **Visibility:** Public / callable
- **Purpose:** Extract the first likely JSON object from an LLM response.
- **Source:** [`protocols.py`](file:///C:/Users/nguye/PROJECTS/your-learning/runtime/protocols.py#L55)

#### `repair_truncated_json()`

```python
def repair_truncated_json(text: str) -> str
```

- **Visibility:** Public / callable
- **Purpose:** Best-effort repair for simple truncated JSON object responses.
- **Source:** [`protocols.py`](file:///C:/Users/nguye/PROJECTS/your-learning/runtime/protocols.py#L65)

#### `_sanitize_json_string_content()`

```python
def _sanitize_json_string_content(text: str) -> str
```

- **Visibility:** Internal helper - do not call from UI
- **Purpose:** Escape raw control chars and invalid backslash escapes inside JSON strings.
- **Source:** [`protocols.py`](file:///C:/Users/nguye/PROJECTS/your-learning/runtime/protocols.py#L87)

#### `parse_json_object()`

```python
def parse_json_object(text: str) -> Dict[str, Any]
```

- **Visibility:** Public / callable
- **Purpose:** Parse an LLM JSON object with cleaning and best-effort repair.
- **Source:** [`protocols.py`](file:///C:/Users/nguye/PROJECTS/your-learning/runtime/protocols.py#L131)

#### `agent_result_to_event()`

```python
def agent_result_to_event(result: AgentResult) -> Dict[str, Any]
```

- **Visibility:** Public / callable
- **Purpose:** Convert an AgentResult into a Streamlit-compatible runtime event.
- **Source:** [`protocols.py`](file:///C:/Users/nguye/PROJECTS/your-learning/runtime/protocols.py#L148)

#### `critic_report_to_event()`

```python
def critic_report_to_event(report: CriticReport) -> Dict[str, Any]
```

- **Visibility:** Public / callable
- **Purpose:** Convert a CriticReport into a Streamlit-compatible runtime event.
- **Source:** [`protocols.py`](file:///C:/Users/nguye/PROJECTS/your-learning/runtime/protocols.py#L160)

---

## `runtime/queue.py`

**Category:** Production module

### Class `QueueOrchestrator`

- **Base:** `object`
- **Purpose:** No docstring yet; inspect the function name and module notes before use.
- **Source:** [`queue.py`](file:///C:/Users/nguye/PROJECTS/your-learning/runtime/queue.py#L11)

#### `QueueOrchestrator.__init__()`

```python
def __init__(self, llm_service)
```

- **Visibility:** Dunder / lifecycle
- **Purpose:** - Reason: Legacy fallback for the original sequential expert queue. - Function: Manages the pre-MultiAgentRuntime teaching flow. - Usage: Kept during migration so the app can fall back if the new runtime is disabled. - Parameters:     - llm_service: The service used to communicate with the configured LLM. - Returns: None. - Alternatives: MultiAgentRuntime, LangGraph StateGraph.

#### `QueueOrchestrator._clean_think_tags()`

```python
def _clean_think_tags(self, text: str) -> str
```

- **Visibility:** Internal helper - do not call from UI
- **Purpose:** - Reason: reasoning models output thoughts in <think> tags. - Function: Removes everything between <think> and </think> inclusive.

#### `QueueOrchestrator.initialize_state()`

```python
def initialize_state(self, step_id: str, macro_context: str, graph_context: str='')
```

- **Visibility:** Public / callable
- **Purpose:** - Reason: To reset or initialize the partitioned memory (scratchpads) for a new teaching step. - Function: Creates a fresh QueueState object. - Usage: Called at the beginning of each new curriculum group/step. - Parameters:     - step_id (str): The unique identifier of the current teaching step.     - macro_context (str): The full section text.     - graph_context (str): Learned vs unlearned prerequisites. - Returns: None.

#### `QueueOrchestrator.execute_teaching_step()`

```python
def execute_teaching_step(self, step_data: Dict[str, Any], macro_context: str, graph_context: str='')
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `QueueOrchestrator.mutate_queue()`

```python
def mutate_queue(self, target_queue: deque, new_agents: List[str])
```

- **Visibility:** Public / callable
- **Purpose:** - Reason: To allow dynamic agent injection at runtime. - Function: Pushes new agents to the FRONT of the queue. - Usage: Can be called by specific agents if they detect a gap in the student's knowledge. - Parameters:     - target_queue (deque): The current running queue.     - new_agents (List[str]): List of agent roles to inject. - Returns: None.

#### `QueueOrchestrator._stream_agent_llm()`

```python
def _stream_agent_llm(self, system_prompt: str, user_prompt: str, **kwargs)
```

- **Visibility:** Internal helper - do not call from UI
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `QueueOrchestrator._route_and_execute_agent()`

```python
def _route_and_execute_agent(self, agent_role: str, step_data: Dict[str, Any]) -> str
```

- **Visibility:** Internal helper - do not call from UI
- **Purpose:** Internal router to call the appropriate agent function based on the role.

#### `QueueOrchestrator._run_concept_agent()`

```python
def _run_concept_agent(self, content_focus: str)
```

- **Visibility:** Internal helper - do not call from UI
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `QueueOrchestrator._run_math_agent()`

```python
def _run_math_agent(self, content_focus: str)
```

- **Visibility:** Internal helper - do not call from UI
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `QueueOrchestrator._run_formula_agent()`

```python
def _run_formula_agent(self, content_focus: str)
```

- **Visibility:** Internal helper - do not call from UI
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `QueueOrchestrator._run_algorithm_agent()`

```python
def _run_algorithm_agent(self, content_focus: str)
```

- **Visibility:** Internal helper - do not call from UI
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `QueueOrchestrator._run_example_agent()`

```python
def _run_example_agent(self, content_focus: str)
```

- **Visibility:** Internal helper - do not call from UI
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `QueueOrchestrator._run_dynamic_agent()`

```python
def _run_dynamic_agent(self, role_detail: str, content_focus: str)
```

- **Visibility:** Internal helper - do not call from UI
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `QueueOrchestrator._update_global_summary()`

```python
def _update_global_summary(self, agent_role: str, recent_content: str)
```

- **Visibility:** Internal helper - do not call from UI
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

---

## `runtime/tracing.py`

**Category:** Production module

### Class `RuntimeTracer`

- **Base:** `object`
- **Purpose:** Lightweight local JSONL tracer for multi-agent runtime observability.
- **Source:** [`tracing.py`](file:///C:/Users/nguye/PROJECTS/your-learning/runtime/tracing.py#L10)

#### `RuntimeTracer.__init__()`

```python
def __init__(self, trace_dir: str='runtime_traces')
```

- **Visibility:** Dunder / lifecycle
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `RuntimeTracer.start_trace()`

```python
def start_trace(self, *, user_id: str, target_file: str='', target_section: str='', workflow_mode: str='') -> RuntimeTrace
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `RuntimeTracer.record()`

```python
def record(self, event_type: str, *, agent_name: Optional[str]=None, task_id: Optional[str]=None, message: str='', success: Optional[bool]=None, latency_ms: Optional[float]=None, payload: Optional[Dict[str, Any]]=None) -> Optional[AgentTraceEvent]
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `RuntimeTracer.finish_trace()`

```python
def finish_trace(self, *, blackboard: Optional[BlackboardState]=None, success: bool=True) -> Optional[RuntimeTrace]
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `RuntimeTracer.persist()`

```python
def persist(self) -> None
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `RuntimeTracer.as_dict()`

```python
def as_dict(self) -> Dict[str, Any]
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

---

## `tests/test_ablation_study.py`

**Category:** Test / evaluation only

### Module functions

#### `llm_evaluate()`

```python
def llm_evaluate(llm, query: str, answer: str, ground_truth: str) -> Dict[str, float]
```

- **Visibility:** Public / callable
- **Purpose:** Use the LLM to score the answer against ground truth on 3 dimensions. Returns dict with correctness, completeness, faithfulness (each 1-10).
- **Source:** [`test_ablation_study.py`](file:///C:/Users/nguye/PROJECTS/your-learning/tests/test_ablation_study.py#L136)

#### `engine()`

```python
def engine()
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.
- **Source:** [`test_ablation_study.py`](file:///C:/Users/nguye/PROJECTS/your-learning/tests/test_ablation_study.py#L270)

#### `run_qa_with_config()`

```python
def run_qa_with_config(engine, query: str, user_id: str, target_file: str='', *, use_hyde=True, use_graph=True, use_memory=True, use_fetch_raw=True, force_search_mode=None) -> AblationResult
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.
- **Source:** [`test_ablation_study.py`](file:///C:/Users/nguye/PROJECTS/your-learning/tests/test_ablation_study.py#L292)

#### `test_ablation_study()`

```python
def test_ablation_study(engine)
```

- **Visibility:** Public / callable
- **Purpose:** Full ablation pipeline:   1. Ingest GNN textbook (fixture)   2. Seed chat history   3. Run 4 queries Ã— 6 configs = 24 experiments   4. LLM-as-Judge scores each answer against ground truth   5. Output quality comparison + per-query tables
- **Source:** [`test_ablation_study.py`](file:///C:/Users/nguye/PROJECTS/your-learning/tests/test_ablation_study.py#L379)

#### `test_memory_stress()`

```python
def test_memory_stress(engine)
```

- **Visibility:** Public / callable
- **Purpose:** Memory Stress Test: Simulate a user with 15 past conversations, then ask a RECALL question that targets turn #3 (eigenvalues/Fiedler value), buried deep in history.  This is the scenario where: - Full System: semantic search finds turn #3 by meaning â†’ high score - No Memory: LLM has zero history context â†’ must guess from textbook only - No Self-Routing: has summaries but can't fetch_raw for exact details
- **Source:** [`test_ablation_study.py`](file:///C:/Users/nguye/PROJECTS/your-learning/tests/test_ablation_study.py#L509)

### Class `AblationResult`

- **Base:** `object`
- **Purpose:** No docstring yet; inspect the function name and module notes before use.
- **Source:** [`test_ablation_study.py`](file:///C:/Users/nguye/PROJECTS/your-learning/tests/test_ablation_study.py#L47)

#### `AblationResult.__post_init__()`

```python
def __post_init__(self)
```

- **Visibility:** Dunder / lifecycle
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `AblationResult.avg_score()`

```python
def avg_score(self) -> float
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

### Class `AblationReport`

- **Base:** `object`
- **Purpose:** No docstring yet; inspect the function name and module notes before use.
- **Source:** [`test_ablation_study.py`](file:///C:/Users/nguye/PROJECTS/your-learning/tests/test_ablation_study.py#L184)

#### `AblationReport.add()`

```python
def add(self, result: AblationResult)
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `AblationReport.final_table()`

```python
def final_table(self) -> str
```

- **Visibility:** Public / callable
- **Purpose:** The main comparison table with quality scores.

#### `AblationReport.per_query_table()`

```python
def per_query_table(self) -> str
```

- **Visibility:** Public / callable
- **Purpose:** Detailed per-query breakdown.

---

## `tests/test_graph_memory.py`

**Category:** Test / evaluation only

### Module functions

#### `mock_dependencies()`

```python
def mock_dependencies()
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.
- **Source:** [`test_graph_memory.py`](file:///C:/Users/nguye/PROJECTS/your-learning/tests/test_graph_memory.py#L9)

#### `test_router_agent_decides_to_answer()`

```python
def test_router_agent_decides_to_answer(mock_dependencies)
```

- **Visibility:** Public / callable
- **Purpose:** Happy Path: LLM has enough info from summaries and answers directly.
- **Source:** [`test_graph_memory.py`](file:///C:/Users/nguye/PROJECTS/your-learning/tests/test_graph_memory.py#L55)

#### `test_router_agent_decides_to_fetch()`

```python
def test_router_agent_decides_to_fetch(mock_dependencies)
```

- **Visibility:** Public / callable
- **Purpose:** Happy Path: LLM realizes it needs raw details and requests fetch.
- **Source:** [`test_graph_memory.py`](file:///C:/Users/nguye/PROJECTS/your-learning/tests/test_graph_memory.py#L68)

#### `test_fetch_raw_history()`

```python
def test_fetch_raw_history(mock_dependencies)
```

- **Visibility:** Public / callable
- **Purpose:** Integration Mock: Ensure Memory Manager correctly queries Neo4j for raw texts.
- **Source:** [`test_graph_memory.py`](file:///C:/Users/nguye/PROJECTS/your-learning/tests/test_graph_memory.py#L81)

#### `test_save_chat_turn()`

```python
def test_save_chat_turn(mock_dependencies)
```

- **Visibility:** Public / callable
- **Purpose:** Integration Mock: Ensure full turn (raw + summary) is pushed to Neo4j.
- **Source:** [`test_graph_memory.py`](file:///C:/Users/nguye/PROJECTS/your-learning/tests/test_graph_memory.py#L92)

### Class `MockSupportAgent`

- **Base:** `object`
- **Purpose:** No docstring yet; inspect the function name and module notes before use.
- **Source:** [`test_graph_memory.py`](file:///C:/Users/nguye/PROJECTS/your-learning/tests/test_graph_memory.py#L29)

#### `MockSupportAgent.__init__()`

```python
def __init__(self, llm)
```

- **Visibility:** Dunder / lifecycle
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `MockSupportAgent.route_and_answer()`

```python
def route_and_answer(self, query: str, summary_history: str, graph_context: list)
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

### Class `MockGraphMemoryManager`

- **Base:** `object`
- **Purpose:** No docstring yet; inspect the function name and module notes before use.
- **Source:** [`test_graph_memory.py`](file:///C:/Users/nguye/PROJECTS/your-learning/tests/test_graph_memory.py#L42)

#### `MockGraphMemoryManager.__init__()`

```python
def __init__(self, graph_db)
```

- **Visibility:** Dunder / lifecycle
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `MockGraphMemoryManager.save_chat_turn()`

```python
def save_chat_turn(self, query: str, raw_answer: str, summary: str, concept_id: str)
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

#### `MockGraphMemoryManager.fetch_raw_history()`

```python
def fetch_raw_history(self, turn_ids: list)
```

- **Visibility:** Public / callable
- **Purpose:** No docstring yet; inspect the function name and module notes before use.

---

## `tests/test_hybrid_memory_flow.py`

**Category:** Test / evaluation only

### Module functions

#### `test_long_interactive_learning_session()`

```python
def test_long_interactive_learning_session(capsys)
```

- **Visibility:** Public / callable
- **Purpose:** - LÃ­ do táº¡i sao dÃ¹ng: MÃ´ phá»ng má»™t ngÆ°á»i há»c liÃªn tá»¥c há»i nhiá»u cÃ¢u liÃªn tiáº¿p. - Chá»©c nÄƒng: In ra toÃ n bá»™ thÃ´ng tin Semantic Memory, Recent History gá»­i vÃ o LLM á»Ÿ má»—i turn.
- **Source:** [`test_hybrid_memory_flow.py`](file:///C:/Users/nguye/PROJECTS/your-learning/tests/test_hybrid_memory_flow.py#L15)

#### `test_fetch_raw_interactive_session()`

```python
def test_fetch_raw_interactive_session(capsys)
```

- **Visibility:** Public / callable
- **Purpose:** - LÃ­ do táº¡i sao dÃ¹ng: MÃ´ phá»ng ngÆ°á»i dÃ¹ng há»i má»™t cÃ¢u yÃªu cáº§u LLM pháº£i truy cáº­p láº¡i vÄƒn báº£n thÃ´ (fetch_raw). - Chá»©c nÄƒng: In ra nguyÃªn vÄƒn Prompt vÃ  Response Ä‘á»ƒ xem LLM quyáº¿t Ä‘á»‹nh tháº¿ nÃ o.
- **Source:** [`test_hybrid_memory_flow.py`](file:///C:/Users/nguye/PROJECTS/your-learning/tests/test_hybrid_memory_flow.py#L84)

---

## `tests/test_learning_eval.py`

**Category:** Test / evaluation only

### Module functions

#### `initialize_engine()`

```python
def initialize_engine()
```

- **Visibility:** Public / callable
- **Purpose:** Initialize engine without Streamlit dependencies.
- **Source:** [`test_learning_eval.py`](file:///C:/Users/nguye/PROJECTS/your-learning/tests/test_learning_eval.py#L15)

#### `run_learning_evaluation()`

```python
def run_learning_evaluation(roadmap, main_entities, llm)
```

- **Visibility:** Public / callable
- **Purpose:** Evaluates a teaching roadmap using LLM-as-Judge.
- **Source:** [`test_learning_eval.py`](file:///C:/Users/nguye/PROJECTS/your-learning/tests/test_learning_eval.py#L31)

#### `test_learning_roadmap_quality()`

```python
def test_learning_roadmap_quality()
```

- **Visibility:** Public / callable
- **Purpose:** Main test to evaluate Learning Mode roadmap quality.
- **Source:** [`test_learning_eval.py`](file:///C:/Users/nguye/PROJECTS/your-learning/tests/test_learning_eval.py#L71)

---

## `tests/test_ragas_eval.py`

**Category:** Test / evaluation only

### Module functions

#### `engine()`

```python
def engine()
```

- **Visibility:** Public / callable
- **Purpose:** Initialize engine + ingest textbook (once per session).
- **Source:** [`test_ragas_eval.py`](file:///C:/Users/nguye/PROJECTS/your-learning/tests/test_ragas_eval.py#L53)

#### `dataset()`

```python
def dataset()
```

- **Visibility:** Public / callable
- **Purpose:** Load the evaluation dataset from JSON.
- **Source:** [`test_ragas_eval.py`](file:///C:/Users/nguye/PROJECTS/your-learning/tests/test_ragas_eval.py#L73)

#### `run_qa_and_capture()`

```python
def run_qa_and_capture(engine, question: str, target_file: str, user_id: str) -> Dict
```

- **Visibility:** Public / callable
- **Purpose:** Run the full QA pipeline and capture:   - answer: the LLM response   - contexts: list of retrieved text chunks used as context
- **Source:** [`test_ragas_eval.py`](file:///C:/Users/nguye/PROJECTS/your-learning/tests/test_ragas_eval.py#L83)

#### `run_ragas_evaluation()`

```python
def run_ragas_evaluation(samples: List[Dict], llm)
```

- **Visibility:** Public / callable
- **Purpose:** Run RAGAS evaluation on collected samples. Returns a dict with averaged scores.  NOTE: We skip ResponseRelevancy because it requires embeddings wrapper that causes EmbeddingUsageEvent validation errors with FastEmbed. We evaluate 3 metrics: Faithfulness, ContextPrecision, ContextRecall.
- **Source:** [`test_ragas_eval.py`](file:///C:/Users/nguye/PROJECTS/your-learning/tests/test_ragas_eval.py#L169)

#### `run_manual_evaluation()`

```python
def run_manual_evaluation(samples: List[Dict], llm) -> Dict
```

- **Visibility:** Public / callable
- **Purpose:** Fallback: LLM-as-Judge evaluation when RAGAS is not installed. Scores each sample on 4 dimensions matching RAGAS metrics.
- **Source:** [`test_ragas_eval.py`](file:///C:/Users/nguye/PROJECTS/your-learning/tests/test_ragas_eval.py#L238)

#### `print_results()`

```python
def print_results(samples: List[Dict], eval_result)
```

- **Visibility:** Public / callable
- **Purpose:** Print formatted evaluation results.
- **Source:** [`test_ragas_eval.py`](file:///C:/Users/nguye/PROJECTS/your-learning/tests/test_ragas_eval.py#L294)

#### `test_ragas_evaluation()`

```python
def test_ragas_evaluation(engine, dataset)
```

- **Visibility:** Public / callable
- **Purpose:** Full RAGAS evaluation pipeline:   1. Ingest textbook (fixture)   2. Run each question through the QA pipeline   3. Capture: question, answer, retrieved contexts, ground truth   4. Run RAGAS evaluation (or LLM-as-Judge fallback)   5. Output formatted results + save JSON
- **Source:** [`test_ragas_eval.py`](file:///C:/Users/nguye/PROJECTS/your-learning/tests/test_ragas_eval.py#L351)

---

## Maintenance TODO

- [ ] Regenerate/update this document whenever public signatures change.
- [ ] Add missing docstrings where this reference says ?Ch?a c? docstring?.
- [ ] Mark deprecated legacy queue APIs after migration to `MultiAgentRuntime`.
- [ ] Replace TODO scaffold descriptions as application services are implemented.


