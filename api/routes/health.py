"""Health and connectivity diagnostics route."""

from typing import Any, Dict
from fastapi import APIRouter, Depends

from api.dependencies import get_runtime_engine
from runtime.engine import RuntimeEngine

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def check_health(engine: RuntimeEngine = Depends(get_runtime_engine)) -> Dict[str, Any]:
    """Check connectivity to Neo4j AuraDB, Qdrant Vector Store, and LLM."""
    components: Dict[str, Any] = {}

    # 1. Check Qdrant Vector Store
    try:
        engine.vector_db.client.get_collections()
        components["qdrant"] = {"status": "connected", "details": "Qdrant collections accessible"}
    except Exception as exc:
        components["qdrant"] = {"status": "error", "error": str(exc)}

    # 2. Check Neo4j Graph DB
    try:
        with engine.graph_db.driver.session() as session:
            session.run("RETURN 1")
        components["neo4j"] = {"status": "connected", "details": "Neo4j session active"}
    except Exception as exc:
        components["neo4j"] = {"status": "error", "error": str(exc)}

    # 3. Check LLM Service
    try:
        res = engine.llm_service.chat_llm.invoke("Say 'OK'")
        components["llm"] = {
            "status": "connected",
            "response": getattr(res, "content", str(res)),
        }
    except Exception as exc:
        components["llm"] = {"status": "error", "error": str(exc)}

    connected_count = sum(1 for c in components.values() if c.get("status") == "connected")
    if connected_count == len(components):
        overall_status = "healthy"
    elif connected_count > 0:
        overall_status = "degraded"
    else:
        overall_status = "unhealthy"

    return {
        "status": overall_status,
        "components": components,
    }
