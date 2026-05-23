"""
File Name : main.py

What this file does:
- This is the starting point of the FastAPI app
- Connects all routers together in one place
- Creates the main backend server

Who uses this file:
- Uvicorn server

Where this file stays:
- Inside the app/ folder

Connected with:
- All files inside routers/
"""

from fastapi import FastAPI
from app.routers import webhooks, campaigns, tools, auth , knowledge_base,agencies
from app import config


# ============================================
# CREATE FASTAPI APP
# ============================================

app = FastAPI(
    title=config.APP_NAME,
    description="Insurance Agency Voice AI Platform",
    version="1.0.0"
)



# ============================================
# CONNECT ROUTERS
#
# Each router works like a separate door
# for different backend features
#
# webhooks  -> Receives events from Vapi
# campaigns -> Starts and manages call campaigns
# tools     -> AI tools used during calls
# auth      -> Login and authentication system
# knowledge-base -> File upload/delete এখানে
                    
# ============================================

app.include_router(
    webhooks.router,
    prefix="/webhooks",
    tags=["Vapi Webhooks"]
)

app.include_router(
    campaigns.router,
    prefix="/campaigns",
    tags=["Campaign Control"]
)

app.include_router(
    tools.router,
    prefix="/tools",
    tags=["Vapi Tools"]
)

app.include_router(
    auth.router,
    prefix="/auth",
    tags=["Authentication"]
)

app.include_router(
    knowledge_base.router,
    prefix="/knowledge-base",
    tags=["📚 Knowledge Base"]
)

app.include_router(
    agencies.router,
    prefix="/agencies",
    tags=["Agency Provision"]
)


# ============================================
# HEALTH CHECK API
#
# Purpose:
# Check if the server is running properly
#
# URL:
# http://localhost:8000/
# ============================================

@app.get("/", tags=["Health Check"])
async def root():
    """
    Purpose:
    Confirms the backend server is running

    Returns:
    Simple server status message
    """

    return {
        "app": config.APP_NAME,
        "status": "running",
        "message": "InsureFlow AI is live!"
    }


# for health check
@app.get("/health")
def health_check():
    return{
        'status':'OK'
    }