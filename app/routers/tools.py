"""
File Name : tools.py
Purpose   : Handle all Vapi requests during calls

             1. Book meetings (bookAppointment)
             2. Qualify leads (qualifyLead)
             3. Get transfer number (getTransferNumber)

Called By : Vapi (automatically during calls)
Connected : ghl_service.py, db_service.py
"""

from fastapi import APIRouter, Request

router = APIRouter()


# ============================================
# BOOK APPOINTMENT
# Purpose : Book customer meetings
# URL     : POST /tools/book-appointment
# Called By : Vapi (when customer asks for meeting)
# ============================================
@router.post("/book-appointment")
async def book_appointment(request: Request):
    """
    Purpose : Book customer appointment
    Inputs  : customer_name, datetime, lead_id, timezone
    Returns : meeting link to Vapi
    Action  : Save booking in GHL Calendar + Database
    """
    try:
        data = await request.json()
    except:
        data = {}

    customer_name = data.get("customer_name", "")
    datetime_str  = data.get("datetime", "")
    lead_id       = data.get("lead_id", "")
    timezone      = data.get("timezone", "Asia/Dhaka")

    print(f"📅 Booking: {customer_name} | Time: {datetime_str} | Lead: {lead_id}")

    # TODO: Add GHL Calendar API integration
    # TODO: Save meeting into database

    return {
        "status": "success",
        "message": f"Appointment booked for {customer_name}",
        "meeting_link": "https://calendly.com/placeholder"
    }


# ============================================
# QUALIFY LEAD
# Purpose : Update lead status based on call intent
# URL     : POST /tools/qualify-lead
# Called By : Vapi (when intent is detected)
# ============================================
@router.post("/qualify-lead")
async def qualify_lead(request: Request):
    """
    Purpose : Update lead status based on intent
    Inputs  : lead_id, intent, agency_id
    Returns : success response
    Action  : Update DB + GHL CRM

    Possible Intents:
    → interested
    → not_interested
    → busy
    → talk_to_agent
    """
    try:
        data = await request.json()
    except:
        data = {}

    lead_id   = data.get("lead_id", "")
    intent    = data.get("intent", "")
    agency_id = data.get("agency_id", "")

    print(f"🎯 Lead Qualified | Lead: {lead_id} | Intent: {intent} | Agency: {agency_id}")

    # TODO: Update lead status in database
    # await db_service.update_lead_status(lead_id, intent)

    # TODO: Update GHL CRM contact status
    # await ghl_service.update_contact_status(lead_id, intent)

    return {
        "status": "success",
        "lead_id": lead_id,
        "intent": intent,
        "message": f"Lead {lead_id} updated to {intent}"
    }


# ============================================
# GET TRANSFER NUMBER
# Purpose : Return correct agent number per agency
# URL     : POST /tools/transfer-number
# Called By : Vapi (before transferCall)
# ============================================
@router.post("/transfer-number")
async def get_transfer_number(request: Request):
    """
    Purpose : Return agency-specific transfer number
    Inputs  : agency_id
    Returns : transfer number
    Action  : Fetch number from database

    Why Needed:
    → Each agency has different agent numbers
    → Static number sends all calls to one place
    → Dynamic routing sends calls correctly
    """
    try:
        data = await request.json()
    except:
        data = {}

    agency_id = data.get("agency_id", "")

    print(f"📞 Transfer request | Agency: {agency_id}")

    # TODO: Fetch agency from database
    # agency = await db_service.get_agency(agency_id)
    # transfer_number = agency["transfer_number"]

    # Placeholder number for now
    transfer_number = "+8801XXXXXXXXX"

    return {
        "status": "success",
        "transfer_number": transfer_number,
        "agency_id": agency_id
    }


# ============================================
# TEST ENDPOINT
# Purpose : Check if tools router is working
# URL     : GET /tools/test
# ============================================
@router.get("/test")
async def tools_test():
    """
    Purpose : Confirm tools router is running
    """
    return {
        "router": "tools",
        "status": "ready",
        "endpoints": [
            "POST /tools/book-appointment",
            "POST /tools/qualify-lead",
            "POST /tools/transfer-number"
        ]
    }