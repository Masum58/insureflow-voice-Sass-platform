"""
ফাইলের নাম  : db_service.py
ফাইলের কাজ  : DB Partner এর API এর সাথে সব যোগাযোগ এই file করে
               এখন Placeholder data দিয়ে কাজ করছে
               DB Partner ready হলে শুধু API call গুলো replace করবো
কে use করে  : webhooks.py, campaigns.py, tools.py
সংযুক্ত     : config.py (DB API URL + Key এর জন্য)
"""

import httpx
from app import config


# ============================================
# DB CLIENT HEADERS
# কাজ : DB Partner API তে request পাঠানোর জন্য
# ============================================
def get_db_headers():
    """
    কাজ  : DB Partner API request এর জন্য headers বানায়
    দেয়  : Authorization header সহ dict
    """
    return {
        "X-Internal-Key": config.DB_API_KEY,
        "Content-Type": "application/json"
    }


# ============================================
# AGENCY FUNCTIONS
# ============================================

# Mock DB to store data in memory while testing
MOCK_AGENCIES = {
    102: {
        "id": 102,
        "name": "ABC Insurance",
        "business_type": "health_insurance",
        "transfer_number": "+8801322158015",
        "welcome_message": "হ্যালো! আমি InsureFlow AI। কীভাবে সাহায্য করতে পারি?",
        "custom_prompt": "You are an AI assistant for ABC Insurance.",
        "vapi_assistant_id": "placeholder_assistant_id",
        "twilio_number": "+18447538461",
        "vapi_phone_number_id": "832b986f-a1c5-496e-a995-3b1fcca264b0",
        "status": "active"
    }
}

async def get_agency(agency_id: int):
    """
    কাজ  : Agency র সব info DB থেকে আনে
    """
    print(f"DB: Getting agency | ID: {agency_id}")
    
    # Return from mock DB if exists, else return a default
    if agency_id in MOCK_AGENCIES:
        return MOCK_AGENCIES[agency_id]
        
    return {
        "id": agency_id,
        "name": "Default Agency",
        "vapi_assistant_id": "placeholder_assistant_id",
        "twilio_number": "+18447538461"
    }

async def get_agency_id_by_phone(phone_number: str) -> int:
    """
    কাজ  : Phone number দিয়ে agency ID বের করে
    """
    print(f"DB: Looking up agency by phone: {phone_number}")
    if phone_number == "+18447538461":
        return 102
    return 1

async def save_agency(agency_data: dict):
    """
    কাজ  : নতুন Agency DB তে save করে
    """
    print(f"DB: Saving agency | Name: {agency_data.get('name')}")
    return {"id": 1, "name": agency_data.get("name"), "status": "active"}

async def update_agency(agency_id: int, update_data: dict):
    """
    কাজ  : Agency র info update করে
    """
    print(f"DB: Updating agency | ID: {agency_id} | Data: {update_data}")
    
    # Update mock DB in memory
    if agency_id in MOCK_AGENCIES:
        MOCK_AGENCIES[agency_id].update(update_data)
        
    return {"id": agency_id, "status": "updated"}


# ============================================
# LEAD FUNCTIONS
# ============================================

async def get_queued_leads(agency_id: int):
    """
    কাজ  : Campaign শুরু করতে queued leads আনে
    নেয়  : agency_id
    দেয়  : leads list (phone, name, email সহ)
    কোথায় যায় : DB Partner → leads table
    """
    # TODO: DB Partner ready হলে replace করবো
    # async with httpx.AsyncClient() as client:
    #     response = await client.get(
    #         f"{config.DB_API_URL}/leads",
    #         params={"agency_id": agency_id, "status": "queued"},
    #         headers=get_db_headers()
    #     )
    #     return response.json()

    print(f"DB: Getting queued leads | Agency: {agency_id}")
    return [
        {
            "id": 1,
            "phone": "+8801335117990",  # Your actual phone number for testing
            "name": "Test User",
            "email": "test@email.com",
            "ghl_contact_id": "ghl_001"
        }
    ]


async def get_lead(lead_id: int):
    """
    কাজ  : একটা lead এর info আনে
    """
    print(f"DB: Getting lead | ID: {lead_id}")
    return {
        "id": lead_id,
        "phone": "+8801711111111",
        "name": "Rahim Ahmed",
        "email": "rahim@email.com",
        "status": "queued",
        "ghl_contact_id": "ghl_001"
    }


async def update_lead(lead_id: int, update_data: dict):
    """
    কাজ  : Lead এর status update করে
    নেয়  : lead_id, update_data (status, intent etc)
    দেয়  : updated lead
    কোথায় যায় : DB Partner → leads table
    কখন : Call শেষে intent বোঝার পর
    """
    # TODO: DB Partner ready হলে replace করবো
    # async with httpx.AsyncClient() as client:
    #     response = await client.put(
    #         f"{config.DB_API_URL}/leads/{lead_id}",
    #         json=update_data,
    #         headers=get_db_headers()
    #     )
    #     return response.json()

    print(f"🔄 DB: Updating lead | ID: {lead_id} | Data: {update_data}")
    return {"id": lead_id, "status": "updated"}


# ============================================
# CALL FUNCTIONS
# ============================================

async def save_call(call_data: dict):
    """
    কাজ  : Call শুরু হলে DB তে record তৈরি করে
    নেয়  : call_data (call_id, lead_id, agency_id, status)
    দেয়  : saved call
    কোথায় যায় : DB Partner → calls table
    কখন : call-start event আসলে
    """
    # TODO: DB Partner ready হলে replace করবো
    # async with httpx.AsyncClient() as client:
    #     response = await client.post(
    #         f"{config.DB_API_URL}/calls",
    #         json=call_data,
    #         headers=get_db_headers()
    #     )
    #     return response.json()

    print(f" DB: Saving call | Call ID: {call_data.get('call_id')}")
    return {"id": 1, "call_id": call_data.get("call_id"), "status": "saved"}


async def update_call(call_id: str, update_data: dict):
    """
    কাজ  : Call শেষে transcript, duration, intent save করে
    নেয়  : call_id, update_data (status, intent, transcript, duration)
    দেয়  : updated call
    কোথায় যায় : DB Partner → calls table
    কখন : end-of-call-report event আসলে
    """
    # TODO: DB Partner ready হলে replace করবো
    # async with httpx.AsyncClient() as client:
    #     response = await client.put(
    #         f"{config.DB_API_URL}/calls/{call_id}",
    #         json=update_data,
    #         headers=get_db_headers()
    #     )
    #     return response.json()

    print(f"🔄 DB: Updating call | Call ID: {call_id} | Status: {update_data.get('status')}")
    return {"call_id": call_id, "status": "updated"}


# ============================================
# MEETING FUNCTIONS
# ============================================

async def save_meeting(meeting_data: dict):
    """
    কাজ  : Meeting book হলে DB তে save করে
    নেয়  : meeting_data (call_id, lead_id, agency_id, meeting_link, scheduled_at)
    দেয়  : saved meeting
    কোথায় যায় : DB Partner → meetings table
    কখন : bookAppointment tool call হলে
    """
    # TODO: DB Partner ready হলে replace করবো
    # async with httpx.AsyncClient() as client:
    #     response = await client.post(
    #         f"{config.DB_API_URL}/meetings",
    #         json=meeting_data,
    #         headers=get_db_headers()
    #     )
    #     return response.json()

    print(f" DB: Saving meeting | Lead: {meeting_data.get('lead_id')}")
    return {
        "id": 1,
        "lead_id": meeting_data.get("lead_id"),
        "meeting_link": meeting_data.get("meeting_link"),
        "status": "saved"
    }