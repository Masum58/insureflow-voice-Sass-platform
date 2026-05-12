"""
ফাইলের নাম  : campaigns.py
ফাইলের কাজ  : Outbound call campaign manage করে
               1. Agency setup (Assistant auto-create)
               2. Campaign start (leads → Redis queue)
               3. Campaign stop
               4. Campaign status দেখা
কে call করে : Frontend Dashboard
সংযুক্ত     : vapi_service.py, db_service.py, call_worker.py
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
# কাজ: Call queue manage করে
redis_client = redis.from_url(config.REDIS_URL)


# ============================================
# REQUEST MODELS
# কাজ: API request এর data structure define করে
# ============================================
class AgencySetupRequest(BaseModel):
    """
    কাজ  : Agency setup এর জন্য required data
    """
    agency_id      : int
    agency_name    : str
    business_type  : str
    transfer_number: str
    welcome_message: str = "হ্যালো! আমি InsureFlow AI। কীভাবে সাহায্য করতে পারি?"
    custom_prompt  : str = ""


class CampaignStartRequest(BaseModel):
    """
    কাজ  : Campaign start এর জন্য required data
    """
    agency_id   : int
    campaign_name: str = "Default Campaign"


# ============================================
# AGENCY SETUP
# কাজ : নতুন Agency এর জন্য Vapi Assistant বানায়
# URL : POST /campaigns/setup-agency
# কে call করে : Agency sign up করলে
# ============================================
@router.post("/setup-agency")
async def setup_agency(request: AgencySetupRequest):
    """
    কাজ  : Agency র জন্য সব setup করে
    নেয়  : agency info
    দেয়  : assistant_id
    করে  :
    1. System Prompt auto-generate করে
    2. Vapi তে Assistant create করে
    3. DB তে assistant_id save করে
    """

    print(f"\n🏢 Agency Setup | ID: {request.agency_id} | Name: {request.agency_name}")

    # ============================================
    # Step 1 — System Prompt বানাও
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
- If customer is interested → use bookAppointment tool
- If customer wants human agent → use transfer_call_tool
- If customer is busy → politely end call
- If customer is not interested → politely end call
- Never make up information about policies
        """
    else:
        system_prompt = request.custom_prompt

    # ============================================
    # Step 2 — Vapi তে Assistant Create করো
    # ============================================
    print(f"🤖 Creating Vapi Assistant...")

    assistant_id = await vapi_service.create_agency_assistant(
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
            detail="❌ Failed to create Vapi Assistant"
        )

    print(f"✅ Assistant created | ID: {assistant_id}")

    # ============================================
    # Step 3 — DB তে Assistant ID save করো
    # ============================================
    await db_service.update_agency(request.agency_id, {
        "vapi_assistant_id": assistant_id
    })

    return {
        "status"      : "success ✅",
        "agency_id"   : request.agency_id,
        "agency_name" : request.agency_name,
        "assistant_id": assistant_id,
        "message"     : f"Agency {request.agency_name} setup complete!"
    }


# ============================================
# CAMPAIGN START
# কাজ : Agency র leads নিয়ে call campaign শুরু করে
# URL : POST /campaigns/start
# কে call করে : Frontend Dashboard
# ============================================
@router.post("/start")
async def start_campaign(request: CampaignStartRequest):
    """
    কাজ  : Outbound call campaign শুরু করে
    নেয়  : agency_id, campaign_name
    দেয়  : campaign info
    করে  :
    1. Agency info DB থেকে নিয়ে আসে
    2. Queued leads DB থেকে নিয়ে আসে
    3. Redis Queue তে leads push করে
    4. Worker automatically call শুরু করে
    """

    print(f"\n🚀 Campaign Start | Agency: {request.agency_id} | Name: {request.campaign_name}")

    # ============================================
    # Step 1 — Agency Info নিয়ে আসো
    # ============================================
    agency = await db_service.get_agency(request.agency_id)

    if not agency:
        raise HTTPException(
            status_code=404,
            detail=f"❌ Agency {request.agency_id} not found"
        )

    assistant_id = agency.get("vapi_assistant_id")
    if not assistant_id:
        raise HTTPException(
            status_code=400,
            detail="❌ Agency assistant not created yet. Run /campaigns/setup-agency first"
        )

    print(f"✅ Agency found | Assistant: {assistant_id}")

    # ============================================
    # Step 2 — Queued Leads নিয়ে আসো
    # ============================================
    leads = await db_service.get_queued_leads(request.agency_id)

    if not leads:
        raise HTTPException(
            status_code=404,
            detail="❌ No queued leads found for this agency"
        )

    print(f"📋 Leads found | Total: {len(leads)}")

    # ============================================
    # Step 3 — Redis Queue তে Leads Push করো
    # ============================================
    queue_key = f"campaign:{request.agency_id}:queue"

    # আগের queue clear করো
    redis_client.delete(queue_key)

    # সব leads push করো
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

    print(f"✅ Redis Queue | Key: {queue_key} | Total: {total_queued}")

    # ============================================
    # Step 4 — Campaign Status Redis এ Save করো
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

    # Step 5 — Worker Background এ চালাও ✅ (return এর আগে)
    asyncio.create_task(
        call_worker.run_campaign_worker(request.agency_id)
    )

    return {
        "status"        : "success ✅",
        "campaign_name" : request.campaign_name,
        "agency_id"     : request.agency_id,
        "total_leads"   : len(leads),
        "queued_leads"  : total_queued,
        "message"       : f"Campaign started! {total_queued} leads queued for calling."
    }



# ============================================
# CAMPAIGN STOP
# কাজ : চলমান campaign বন্ধ করে
# URL : POST /campaigns/stop
# কে call করে : Frontend Dashboard
# ============================================
@router.post("/stop")
async def stop_campaign(agency_id: int):
    """
    কাজ  : Campaign বন্ধ করে
    নেয়  : agency_id
    দেয়  : success message
    করে  : Redis Queue clear করে
    """

    print(f"⏹️ Campaign Stop | Agency: {agency_id}")

    # Redis Queue clear করো
    queue_key = f"campaign:{agency_id}:queue"
    redis_client.delete(queue_key)

    # Status update করো
    status_key = f"campaign:{agency_id}:status"
    existing = redis_client.get(status_key)

    if existing:
        status_data = json.loads(existing)
        status_data["status"] = "stopped"
        redis_client.set(status_key, json.dumps(status_data))

    print(f"✅ Campaign stopped | Agency: {agency_id}")

    return {
        "status"   : "success ✅",
        "agency_id": agency_id,
        "message"  : "Campaign stopped successfully"
    }


# ============================================
# CAMPAIGN STATUS
# কাজ : Campaign এর current status দেখায়
# URL : GET /campaigns/status/{agency_id}
# কে call করে : Frontend Dashboard
# ============================================
@router.get("/status/{agency_id}")
async def get_campaign_status(agency_id: int):
    """
    কাজ  : Campaign এর current status দেখায়
    নেয়  : agency_id
    দেয়  : campaign status + progress
    """

    status_key = f"campaign:{agency_id}:status"
    queue_key  = f"campaign:{agency_id}:queue"

    # Redis থেকে status নাও
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