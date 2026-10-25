"""Application process. The retrieval index is built at startup and kept in memory.

Chat and anonymisation routes are mounted separately. This module only prepares retrieval.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from retrieval.corpus_loader import load_index


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.retrieval = load_index()
    yield
    app.state.retrieval = None


app = FastAPI(title="CarePath AI", lifespan=lifespan)
