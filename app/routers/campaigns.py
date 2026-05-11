"""
File Name : campaigns.py

What this file does:
- Starts outbound call campaigns
- Stops running campaigns
- Controls bulk calling operations

Who calls this file:
- Frontend dashboard
- Admin panel
- Manual API requests

Connected with:
- vapi_service.py
- db_service.py
- call_worker.py
"""

from fastapi import APIRouter


# Create router object
router = APIRouter()



# ============================================
# TEST CAMPAIGN ROUTE
#
# Purpose:
# Check if campaign router is working properly
#
# URL:
# /campaigns/test
# ============================================

@router.get("/test")
async def campaigns_test():
    """
    Purpose:
    Simple test API for campaign router

    Returns:
    Router status message
    """

    return {
        "router": "campaigns",
        "status": "ready"
    }