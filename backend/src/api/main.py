from fastapi import Depends, FastAPI, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader

from src.api.routes import router as api_router
from src.core.config import settings

app = FastAPI(
    title="Code Corrector Agent API",
    description="API for the autonomous LangGraph software engineer agent.",
    version="1.0.0"
)

# CORS middleware for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in prod to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(
    api_key_header_val: str = Depends(api_key_header),
    api_key_query_val: str = Query(None, alias="api_key")
):
    key = api_key_header_val or api_key_query_val
    if key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key"
        )
    return key

# Include routers
app.include_router(api_router, prefix="/api/v1", dependencies=[Depends(verify_api_key)])

@app.get("/health")
async def health_check():
    return {"status": "ok"}
