from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn
import os

from database import init_db
from routers import import_data, dashboard, users, team

app = FastAPI(title="ARO Sprint 2 Tracker")

# Initialize DB
init_db()

# Include routers
app.include_router(import_data.router)
app.include_router(dashboard.router)
app.include_router(users.router)
app.include_router(team.router)

# Serve static files
# Create static directory if it doesn't exist
if not os.path.exists("static"):
    os.makedirs("static")

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_index():
    return FileResponse("static/index.html")

@app.get("/{page}")
async def read_page(page: str):
    if os.path.exists(f"static/{page}.html"):
        return FileResponse(f"static/{page}.html")
    return FileResponse("static/index.html")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
