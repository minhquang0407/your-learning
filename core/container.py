from dependency_injector import containers, providers
from config.settings import settings
from database.structural_db import QdrantVectorStore
from database.semantic_dag import Neo4jManager
from orchestrator.llm_factory import LLMFactory
from orchestrator.llm_service import LLMService
from runtime.engine import SupportAgent, RuntimeEngine
from runtime.agent_runtime import MultiAgentRuntime
from database.document_processor import MathAwareDocumentProcessor
from application.assessment_service import AssessmentService
from application.facade import LearningApplication
from application.ingestion_service import IngestionService
from application.learning_service import LearningService
from application.library_service import LibraryService
from application.qa_service import QAService
from application.briefing_service import BriefingService


class Container(containers.DeclarativeContainer):
    # Pass settings object to configuration
    config = providers.Configuration()

    # Database Providers
    vector_db = providers.Singleton(
        QdrantVectorStore,
        host=config.qdrant_host,
        port=config.qdrant_port,
        api_key=config.qdrant_api_key,
        collection_name=config.vector_collection_name
    )

    graph_db = providers.Singleton(
        Neo4jManager,
        uri=config.neo4j_uri,
        user=config.neo4j_user,
        password=config.neo4j_password
    )

    # LLM Providers using Factory
    ingestion_llm = providers.Singleton(
        LLMFactory.create_llm,
        provider=config.llm_provider,
        model_name=config.llm_model_name,
        base_url=config.llm_base_url,
        temperature=config.ingestion_temperature,
        max_tokens=config.ingestion_max_token,
        top_p=config.ingestion_top_p,
        openai_api_key=config.openai_api_key,
        groq_api_key=config.groq_api_key,
        google_api_key=config.google_api_key,
        model_kwargs={"response_format": {"type": "json_object"}}
    )

    learning_llm = providers.Singleton(
        LLMFactory.create_llm,
        provider=config.llm_provider,
        model_name=config.llm_model_name,
        base_url=config.llm_base_url,
        temperature=config.learning_temperature,
        max_tokens=config.learning_max_token,
        top_p=config.learning_top_p,
        openai_api_key=config.openai_api_key,
        groq_api_key=config.groq_api_key,
        google_api_key=config.google_api_key,
    )

    qa_llm = providers.Singleton(
        LLMFactory.create_llm,
        provider=config.llm_provider,
        model_name=config.llm_model_name,
        base_url=config.llm_base_url,
        temperature=config.qa_temperature,
        max_tokens=config.qa_max_token,
        top_p=config.qa_top_p,
        openai_api_key=config.openai_api_key,
        groq_api_key=config.groq_api_key,
        google_api_key=config.google_api_key,
        model_kwargs={"response_format": {"type": "json_object"}}
    )

    # Services
    llm_service = providers.Singleton(
        LLMService,
        llm=ingestion_llm,
        chat_llm=learning_llm
    )

    support_agent = providers.Singleton(
        SupportAgent,
        llm=qa_llm
    )

    multi_agent_runtime = providers.Singleton(
        MultiAgentRuntime,
        llm_service=llm_service,
        vector_db=vector_db,
        graph_db=graph_db,
        critic_enabled=config.critic_enabled,
        max_revision_loops=config.max_revision_loops,
        stream_agent_outputs=config.stream_agent_outputs,
    )

    # Main Engine
    runtime_engine = providers.Singleton(
        RuntimeEngine,
        multi_agent_runtime=multi_agent_runtime,
        vector_db=vector_db,
        graph_db=graph_db,
        support_agent=support_agent,
        llm_service=llm_service,
    )

    document_processor = providers.Singleton(MathAwareDocumentProcessor)

    ingestion_service = providers.Singleton(
        IngestionService,
        vector_store=vector_db,
        graph_store=graph_db,
        llm_service=llm_service,
        document_processor=document_processor,
    )
    learning_service = providers.Singleton(LearningService, runtime_engine=runtime_engine)
    qa_service = providers.Singleton(QAService, runtime_engine=runtime_engine)
    assessment_service = providers.Singleton(AssessmentService, runtime_engine=runtime_engine)
    briefing_service = providers.Singleton(BriefingService, runtime_engine=runtime_engine)
    library_service = providers.Singleton(
        LibraryService,
        vector_store=vector_db,
        graph_store=graph_db,
    )

    learning_application = providers.Singleton(
        LearningApplication,
        ingestion=ingestion_service,
        learning=learning_service,
        qa=qa_service,
        assessment=assessment_service,
        library=library_service,
        briefing=briefing_service,
    )
