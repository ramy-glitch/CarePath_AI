"""Application process. The retrieval index is built at startup and kept in memory.

The chat route reads that index. Anonymisation stays a separate route.
The browser client is served from this process so the page and the API share an origin.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api.anonymise_route import router as anonymise_router
from api.chat_route import router as chat_router
from api.fixtures_route import router as fixtures_router
from config import settings
from retrieval.corpus_loader import load_index


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.retrieval = load_index()
    yield
    app.state.retrieval = None


app = FastAPI(title="CarePath AI", lifespan=lifespan)
app.include_router(anonymise_router)
app.include_router(chat_router)
app.include_router(fixtures_router)
app.mount("/corpus", StaticFiles(directory=settings.PROJECT_ROOT / "corpus"), name="corpus")
app.mount("/", StaticFiles(directory=settings.PROJECT_ROOT / "client", html=True), name="client")
