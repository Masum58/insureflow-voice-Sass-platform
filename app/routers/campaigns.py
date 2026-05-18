"""
File Name   : campaigns.py
Description : Manages outbound call campaigns
               1. Agency setup (Assistant auto-create)
               2. Campaign start (leads -> Redis queue)
               3. Campaign stop
               4. View campaign status
Called By   : Frontend Dashboard
Dependencies: vapi_service.py, db_service.py, call_worker.py
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services import vapi_service, db_service
from app.workers import call_worker
from app import config
import redis
import json
import asyncio

router = APIRouter()

# Redis Connection
# Description: Manages the call queue
redis_client = redis.from_url(config.REDIS_URL)


# ============================================
# REQUEST MODELS
# Description: Defines the data structure for API requests
# ============================================
class AgencySetupRequest(BaseModel):
    """
    Description: Required data for agency setup
    """
    agency_id      : int
    agency_name    : str
    business_type  : str
    transfer_number: str
    welcome_message: str = "Hello! I am InsureFlow AI. How can I help you?"
    custom_prompt  : str = ""


class CampaignStartRequest(BaseModel):
    """
    Description: Required data for starting a campaign
    """
    agency_id   : int
    campaign_name: str = "Default Campaign"


# ============================================
# AGENCY SETUP
# Description : Creates a Vapi Assistant for a new Agency
# URL         : POST /campaigns/setup-agency
# Called By   : When an Agency signs up
# ============================================
@router.post("/setup-agency")
async def setup_agency(request: AgencySetupRequest):
    """
    Description: Performs all setup steps for an Agency
    Takes      : agency info
    Returns    : assistant_id
    Actions    :
    1. Auto-generates System Prompt
    2. Creates Assistant in Vapi
    3. Saves assistant_id in DB
    """

    print(f"\n[Agency Setup] ID: {request.agency_id} | Name: {request.agency_name}")

    # ============================================
    # Step 1 - Create System Prompt
    # ============================================
    if not request.custom_prompt:
        system_prompt = f"""
You are an AI voice assistant for {request.agency_name}.
Business Type: {request.business_type}

Your job is to qualify leads for insurance.

Rules:
- Always represent {request.agency_name} only
- Be polite and professional
- Speak in Bengali if customer speaks Bengali
- Speak in English if customer speaks English
- Use your knowledge base for accurate answers
- If customer is interested -> use bookAppointment tool
- If customer wants human agent -> use transfer_call_tool
- If customer is busy -> politely end call
- If customer is not interested -> politely end call
- Never make up information about policies
        """
    else:
        system_prompt = request.custom_prompt

    # ============================================
    # Step 2 - Create Assistant in Vapi
    # ============================================
    print(f"[Creating Vapi Assistant...]")

    assistant_id, book_tool_id, transfer_tool_id = await vapi_service.create_agency_assistant(
        agency_id      = request.agency_id,
        agency_name    = request.agency_name,
        business_type  = request.business_type,
        custom_prompt  = system_prompt,
        transfer_number= request.transfer_number,
        welcome_message= request.welcome_message
    )

    if not assistant_id:
        raise HTTPException(
            status_code=500,
            detail="Failed to create Vapi Assistant"
        )

    print(f"[Assistant created] ID: {assistant_id}")

    # ============================================
    # Step 3 - Save Assistant ID to DB
    # ============================================
    await db_service.update_agency(request.agency_id, {
        "vapi_assistant_id"      : assistant_id,
        "vapi_book_tool_id"      : book_tool_id,
        "vapi_transfer_tool_id"  : transfer_tool_id
    })

    return {
        "status"      : "success",
        "agency_id"   : request.agency_id,
        "agency_name" : request.agency_name,
        "assistant_id": assistant_id,
        "message"     : f"Agency {request.agency_name} setup complete!"
    }


# ============================================
# CAMPAIGN START
# Description : Starts a call campaign with the Agency's leads
# URL         : POST /campaigns/start
# Called By   : Frontend Dashboard
# ============================================
@router.post("/start")
async def start_campaign(request: CampaignStartRequest):
    """
    Description: Starts an outbound call campaign
    Takes      : agency_id, campaign_name
    Returns    : campaign info
    Actions    :
    1. Fetches Agency info from DB
    2. Fetches queued leads from DB
    3. Pushes leads to Redis Queue
    4. Automatically starts worker to initiate calls
    """

    print(f"\n[Campaign Start] Agency: {request.agency_id} | Name: {request.campaign_name}")

    # ============================================
    # Step 1 - Fetch Agency Info
    # ============================================
    agency = await db_service.get_agency(request.agency_id)

    if not agency:
        raise HTTPException(
            status_code=404,
            detail=f"Agency {request.agency_id} not found"
        )

    assistant_id = agency.get("vapi_assistant_id")
    if not assistant_id:
        raise HTTPException(
            status_code=400,
            detail="Agency assistant not created yet. Run /campaigns/setup-agency first"
        )

    print(f"[Agency found] Assistant: {assistant_id}")

    # ============================================
    # Step 2 - Fetch Queued Leads
    # ============================================
    leads = await db_service.get_queued_leads(request.agency_id)

    if not leads:
        raise HTTPException(
            status_code=404,
            detail="No queued leads found for this agency"
        )

    print(f"[Leads found] Total: {len(leads)}")

    # ============================================
    # Step 3 - Push Leads to Redis Queue
    # ============================================
    queue_key = f"campaign:{request.agency_id}:queue"

    # Clear previous queue
    redis_client.delete(queue_key)

    # Push all leads
    for lead in leads:
        lead_data = {
            "lead_id"     : lead["id"],
            "phone"       : lead["phone"],
            "name"        : lead["name"],
            "agency_id"   : request.agency_id,
            "assistant_id": assistant_id,
            "twilio_number": agency.get("twilio_number", config.TWILIO_PHONE_NUMBER)
        }
        redis_client.rpush(queue_key, json.dumps(lead_data))

    total_queued = redis_client.llen(queue_key)

    print(f"[Redis Queue] Key: {queue_key} | Total: {total_queued}")

    # ============================================
    # Step 4 - Save Campaign Status in Redis
    # ============================================
    campaign_status = {
        "agency_id"    : request.agency_id,
        "campaign_name": request.campaign_name,
        "status"       : "running",
        "total_leads"  : len(leads),
        "queued"       : total_queued,
        "called"       : 0
    }
    redis_client.set(
        f"campaign:{request.agency_id}:status",
        json.dumps(campaign_status)
    )

    # Step 5 - Run Worker in Background (before returning)
    asyncio.create_task(
        call_worker.run_campaign_worker(request.agency_id)
    )

    return {
        "status"        : "success",
        "campaign_name" : request.campaign_name,
        "agency_id"     : request.agency_id,
        "total_leads"   : len(leads),
        "queued_leads"  : total_queued,
        "message"       : f"Campaign started! {total_queued} leads queued for calling."
    }



# ============================================
# CAMPAIGN STOP
# Description : Stops an ongoing campaign
# URL         : POST /campaigns/stop
# Called By   : Frontend Dashboard
# ============================================
@router.post("/stop")
async def stop_campaign(agency_id: int):
    """
    Description: Stops the campaign
    Takes      : agency_id
    Returns    : success message
    Actions    : Clears the Redis Queue
    """

    print(f"[Campaign Stop] Agency: {agency_id}")

    # Clear Redis Queue
    queue_key = f"campaign:{agency_id}:queue"
    redis_client.delete(queue_key)

    # Update Status
    status_key = f"campaign:{agency_id}:status"
    existing = redis_client.get(status_key)

    if existing:
        status_data = json.loads(existing)
        status_data["status"] = "stopped"
        redis_client.set(status_key, json.dumps(status_data))

    print(f"[Campaign stopped] Agency: {agency_id}")

    return {
        "status"   : "success",
        "agency_id": agency_id,
        "message"  : "Campaign stopped successfully"
    }


# ============================================
# CAMPAIGN STATUS
# Description : Shows the current status of the campaign
# URL         : GET /campaigns/status/{agency_id}
# Called By   : Frontend Dashboard
# ============================================
@router.get("/status/{agency_id}")
async def get_campaign_status(agency_id: int):
    """
    Description: Shows the current status of the campaign
    Takes      : agency_id
    Returns    : campaign status + progress
    """

    status_key = f"campaign:{agency_id}:status"
    queue_key  = f"campaign:{agency_id}:queue"

    # Get status from Redis
    status_data = redis_client.get(status_key)
    queue_count = redis_client.llen(queue_key)

    if not status_data:
        return {
            "agency_id": agency_id,
            "status"   : "no_campaign",
            "message"  : "No campaign running for this agency"
        }

    status = json.loads(status_data)
    status["remaining_in_queue"] = queue_count

    return status


# ============================================
# TEST ENDPOINT
# ============================================
@router.get("/test")
async def campaigns_test():
    return {
        "router"   : "campaigns",
        "status"   : "ready",
        "endpoints": [
            "POST /campaigns/setup-agency",
            "POST /campaigns/start",
            "POST /campaigns/stop",
            "GET  /campaigns/status/{agency_id}"
        ]
    }