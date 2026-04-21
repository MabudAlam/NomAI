import logging
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.agent import agent
from app.endpoints import nutrition, chat
from app.endpoints.diet import router as diet_router
from app.utils.envManager import get_env_variable_safe
from app.middleware.exception_handlers import setup_exception_handlers


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI app."""
    yield


isProd = get_env_variable_safe("PROD", "false").lower() == "true"

app = FastAPI(
    title="NomAI Nutrition API",
    description="AI-powered nutrition analysis API with chat functionality",
    version="1.0.0",
    debug=not isProd,
    lifespan=lifespan,
)

app = setup_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(nutrition.router, prefix="/api/v1/nutrition")
app.include_router(chat.router, prefix="/api/v1/users")
app.include_router(agent.router, prefix="/api/v1/chat")
app.include_router(diet_router, prefix="/api/v1/diet")

app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/")
async def root():
    """Serve the chat HTML page."""
    from fastapi.responses import FileResponse

    return FileResponse("app/static/chat_app.html")


@app.get("/diet")
async def diet_app():
    """Serve the diet planner HTML page."""
    from fastapi.responses import FileResponse

    return FileResponse("app/static/diet_app.html")


if __name__ == "__main__":
    host = get_env_variable_safe("HOST", "0.0.0.0")
    port = int(get_env_variable_safe("PORT", "8000"))

    uvicorn.run(app, host=host, port=port, reload=not isProd)
