"""FastAPI application entry point for your-learning."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.dependencies import get_container, set_container
from api.routes.chat import router as chat_router
from api.routes.documents import router as documents_router
from api.routes.health import router as health_router
from api.routes.ws import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize container on startup
    container = get_container()
    app.state.container = container
    yield
    # Cleanup on shutdown if needed
    set_container(None)


def create_app() -> FastAPI:
    """Create and configure FastAPI application instance."""
    app = FastAPI(
        title="Your Learning - Cognitive AI Studio API",
        description="FastAPI Backend for next-generation multi-agent interactive learning classroom",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS configuration for Vite frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routes
    app.include_router(health_router)
    app.include_router(documents_router)
    app.include_router(chat_router)
    app.include_router(ws_router)

    @app.get("/")
    def root():
        return {
            "name": "Your Learning API",
            "status": "online",
            "docs_url": "/docs",
            "version": "1.0.0",
        }

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.app:app", host="0.0.0.0", port=8000, reload=True)
