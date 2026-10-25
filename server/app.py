"""Application process. The retrieval index is built at startup and kept in memory.

The chat route reads that index. Anonymisation stays a separate route.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.chat_route import router as chat_router
from retrieval.corpus_loader import load_index


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.retrieval = load_index()
    yield
    app.state.retrieval = None


app = FastAPI(title="CarePath AI", lifespan=lifespan)
app.include_router(chat_router)
