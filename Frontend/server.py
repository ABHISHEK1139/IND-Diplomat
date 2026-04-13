"""
UI Server - Serve the explainability dashboard and proxy API requests.
"""

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os

# Get the directory of this file
UI_DIR = os.path.dirname(os.path.abspath(__file__))
MAIN_API_BASE_URL = os.getenv("IND_DIPLOMAT_MAIN_API_URL", "http://localhost:8000").rstrip("/")
ANALYST_API_BASE_URL = os.getenv("IND_DIPLOMAT_ANALYST_API_URL", "http://localhost:8100").rstrip("/")

app = FastAPI(title="IND-Diplomat UI Server")

# CORS for API calls
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
app.mount("/static", StaticFiles(directory=UI_DIR), name="static")


@app.get("/")
async def serve_dashboard():
    """Serve the main dashboard."""
    return FileResponse(os.path.join(UI_DIR, "index.html"))


@app.get("/styles.css")
async def serve_styles():
    """Serve CSS."""
    return FileResponse(os.path.join(UI_DIR, "styles.css"), media_type="text/css")


@app.get("/app.js")
async def serve_js():
    """Serve JavaScript."""
    return FileResponse(os.path.join(UI_DIR, "app.js"), media_type="application/javascript")


@app.get("/analyst.js")
async def serve_analyst_js():
    """Serve Analyst Workstation JavaScript."""
    return FileResponse(os.path.join(UI_DIR, "analyst.js"), media_type="application/javascript")


# Proxy endpoint to the main API
async def _forward_main_query(request: Request):
    """Proxy quick queries to the configured main API."""
    import httpx

    body = await request.json()

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{MAIN_API_BASE_URL}/v2/query",
                json=body,
                timeout=60.0
            )
            try:
                payload = response.json()
            except ValueError:
                payload = {"error": response.text}
            return JSONResponse(payload, status_code=response.status_code)
    except Exception as e:
        return JSONResponse({"error": str(e), "success": False}, status_code=502)


@app.post("/api/query")
async def proxy_query(request: Request):
    """Backward-compatible quick-query proxy."""
    return await _forward_main_query(request)


@app.post("/v2/query")
async def proxy_v2_query(request: Request):
    """Same-origin proxy for the dashboard's default /v2/query call."""
    return await _forward_main_query(request)


# Proxy endpoints to Analyst API (v3)
@app.api_route("/api/v3/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_analyst_api(path: str, request: Request):
    """Proxy all /api/v3/* requests to the Analyst API on port 8100."""
    import httpx

    url = f"{ANALYST_API_BASE_URL}/api/v3/{path}"
    query_string = str(request.url.query)
    if query_string:
        url += f"?{query_string}"

    try:
        async with httpx.AsyncClient() as client:
            if request.method == "GET":
                response = await client.get(url, timeout=300.0)
            else:
                body = await request.body()
                response = await client.request(
                    request.method,
                    url,
                    content=body,
                    headers={"Content-Type": "application/json"},
                    timeout=300.0
                )
            try:
                payload = response.json()
            except ValueError:
                payload = {"error": response.text}
            return JSONResponse(payload, status_code=response.status_code)
    except Exception as e:
        return JSONResponse({"error": str(e), "success": False}, status_code=502)


if __name__ == "__main__":
    print("=" * 50)
    print("  IND-Diplomat Explainability Dashboard")
    print("=" * 50)
    print(f"\n  Open: http://localhost:3000")
    print(f"  Main API Proxy:    {MAIN_API_BASE_URL}")
    print(f"  Analyst API Proxy: {ANALYST_API_BASE_URL}\n")
    print("=" * 50)
    
    uvicorn.run(app, host="0.0.0.0", port=3000)
