from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from firmsignal.api.routes import router

app = FastAPI(
    title="FirmSignal API",
    description="Multi-agent company intelligence system",
    version="0.1.0",
)

# Allow all origins during development.
# Week 6: lock this down to your Vercel frontend URL.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "firmsignal"}