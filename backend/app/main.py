from fastapi import FastAPI

app = FastAPI(
    title="NoiseMonitorAI",
    version="0.1.0-alpha",
    description="AI-powered local sound monitoring platform",
)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "version": "0.1.0-alpha",
        "service": "NoiseMonitorAI",
    }