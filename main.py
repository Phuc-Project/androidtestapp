import os
import sys
import webbrowser
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.config import load_settings, BASE_DIR
from app.database import init_db, log_event
from app.routers import instances, accounts, proxies, screen, system, services, campaign
from app.campaign_runner import campaign_runner

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    log_event("SUCCESS", "SYSTEM", "DroidRouter 9 Engine initialized successfully")
    campaign_runner.start_scheduler()
    yield
    # Shutdown
    log_event("INFO", "SYSTEM", "DroidRouter 9 Engine stopped")

app = FastAPI(
    title="DroidRouter 9",
    description="Local Android Virtual Machine & Proxy Gateway Management Engine",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(instances.router)
app.include_router(accounts.router)
app.include_router(proxies.router)
app.include_router(screen.router)
app.include_router(system.router)
app.include_router(services.router)
app.include_router(campaign.router)

# Mount Static Files
static_dir = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/")
async def serve_index():
    index_file = static_dir / "index.html"
    return FileResponse(str(index_file))

def run_server():
    if sys.platform == "win32":
        try:
            if sys.stdout:
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            if sys.stderr:
                sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    settings = load_settings()
    host = settings.get("host", "127.0.0.1")
    port = int(settings.get("port", 9090))
    url = f"http://{host}:{port}"
    print(f"\n=======================================================")
    print(f"[DROIDROUTER 9] ANDROID VM & PROXY GATEWAY ENGINE")
    print(f"=======================================================")
    print(f"* Local Dashboard: {url}")
    print(f"* MuMu Manager:    {settings.get('mumu_manager_path')}")
    print(f"* ADB Executable:  {settings.get('adb_path')}")
    print(f"=======================================================\n")

    # Auto-open browser if run standalone
    try:
        # Only open browser if not invoked via launcher (check env or argv)
        if "--no-browser" not in sys.argv:
            webbrowser.open(url)
    except Exception:
        pass

    uvicorn.run("main:app", host=host, port=port, reload=False, log_level="info")

if __name__ == "__main__":
    run_server()
