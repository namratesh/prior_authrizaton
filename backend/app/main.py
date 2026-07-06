from fastapi import FastAPI

# DEMO-REAL
app = FastAPI(title="AgenticPA")


@app.get("/health")
def health():
    return {"status": "ok"}
