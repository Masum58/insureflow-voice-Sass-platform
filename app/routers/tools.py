"""
ফাইলের নাম  : tools.py
ফাইলের কাজ  : Call চলাকালীন Vapi এর সব request handle করে
কে call করে : Vapi (call এর ভেতর থেকে automatically)
সংযুক্ত     : calendly_service.py, django_service.py
"""

from fastapi import APIRouter, Request
from app.services import db_service, calendly_service, django_service
from app.routers.agencies import AGENCY_STORE

router = APIRouter()


# ============================================
# BOOK APPOINTMENT
# URL : POST /tools/book-appointment
# ============================================
@router.post("/book-appointment")
async def book_appointment(request: Request):
    """
    কাজ  : Customer meeting book করে
    করে  : Calendly sync + Django তে booking পাঠায়
    """
    try:
        data = await request.json()
    except:
        data = {}

    customer_name = data.get("customer_name", "Customer")
    datetime_str  = data.get("datetime", "")
    lead_id       = data.get("lead_id", "")
    business_id   = data.get("business_id", "")
    timezone      = data.get("timezone", "Asia/Dhaka")

    print(f"📅 Booking | Name: {customer_name} | Time: {datetime_str} | Lead: {lead_id}")

    # Lead এর email নাও
    lead  = await db_service.get_lead(lead_id)
    email = lead.get("email", "test@example.com") if lead else "test@example.com"

    # Calendly তে book করো
    calendly_res = await calendly_service.create_invitee(
        customer_name= customer_name,
        email        = email,
        start_time   = datetime_str,
        timezone     = timezone
    )

    meeting_link = "https://calendly.com/insureflow/meeting"
    if calendly_res:
        meeting_link = calendly_res.get("resource", {}).get("scheduling_url", meeting_link)

    # Django তে booking পাঠাও
    if business_id and lead_id:
        await django_service.send_booking(
            business_id  = business_id,
            booking_data = {
                "lead_id"       : lead_id,
                "meeting_date"  : datetime_str.split("T")[0] if "T" in datetime_str else datetime_str,
                "meeting_time"  : datetime_str.split("T")[1][:8] if "T" in datetime_str else "10:00:00",
                "meeting_link"  : meeting_link,
                "status"        : "scheduled",
                "customer_name" : customer_name,
                "customer_email": email,
                "customer_phone": ""
            }
        )

    print(f"✅ Booking confirmed | {customer_name} | {datetime_str}")

    return {
        "result": f"Appointment booked for {customer_name} on {datetime_str}. Invitation sent to {email}."
    }


# ============================================
# QUALIFY LEAD
# URL : POST /tools/qualify-lead
# ============================================
@router.post("/qualify-lead")
async def qualify_lead(request: Request):
    """
    কাজ  : Lead এর intent অনুযায়ী status update করে
    করে  : DB update only — Django CRM handle করবে
    """
    try:
        data = await request.json()
    except:
        data = {}

    lead_id = data.get("lead_id", "")
    intent  = data.get("intent", "")

    print(f"🎯 Qualify Lead | Lead: {lead_id} | Intent: {intent}")

    if lead_id:
        await db_service.update_lead(lead_id, {"status": intent})

    return {"result": f"Lead status updated to {intent}"}


# ============================================
# GET TRANSFER NUMBER
# URL : POST /tools/transfer-number
# ============================================
@router.post("/transfer-number")
async def get_transfer_number(request: Request):
    """
    কাজ  : Agency র agent number দেয় Vapi কে
    """
    try:
        data = await request.json()
    except:
        data = {}

    business_id     = data.get("business_id", "")
    agency          = AGENCY_STORE.get(business_id, {})
    transfer_number = agency.get("human_agent_phone", "+8801322158015")

    print(f"✅ Transfer to: {transfer_number}")

    return {
        "result"         : f"Transfer to {transfer_number}",
        "transfer_number": transfer_number
    }


# ============================================
# HANDLE TOOL CALLS (CENTRAL HANDLER)
# ============================================
async def handle_tool_calls(message: dict):
    """
    কাজ  : Tool call এর type দেখে সঠিক logic run করে
    """
    tool_calls = message.get("toolCalls", [])
    if not tool_calls:
        return {"results": []}

    # AGENCY_STORE থেকে business খোঁজো
    call         = message.get("call") or {}
    phone_obj    = message.get("phoneNumber") or {}
    called_number= phone_obj.get("number", "")

    business_id = None
    agency      = {}
    for bid, data in AGENCY_STORE.items():
        if data.get("twilio_number") == called_number:
            business_id = bid
            agency      = data
            break

    if not business_id:
        metadata    = call.get("metadata") or {}
        business_id = metadata.get("business_id", "default")

    results = []

    for tool_call in tool_calls:
        tool_id  = tool_call.get("id")
        function = tool_call.get("function", {})
        name     = function.get("name")
        args     = function.get("arguments", {})

        print(f"🛠️ Tool Call | Name: {name} | ID: {tool_id} | Business: {business_id}")

        # --- CASE 1: Book Appointment ---
        if name == "bookAppointment":
            customer_name = args.get("customer_name", "Customer")
            datetime_str  = args.get("datetime", "")
            lead_id       = args.get("lead_id", "1")

            res = await book_appointment_internal(
                customer_name= customer_name,
                datetime_str = datetime_str,
                lead_id      = lead_id,
                business_id  = business_id
            )
            results.append({"toolCallId": tool_id, "result": res})

        # --- CASE 2: Search Knowledge Base ---
        elif name == "searchKnowledgeBase":
            query = args.get("query", "")
            print(f"🔍 RAG Search | Query: {query} | Business: {business_id}")

            from app.services import rag_service
            res = await rag_service.build_context(
                agency_id= business_id,
                query    = query
            )
            results.append({
                "toolCallId": tool_id,
                "result"    : res if res else "No specific information found."
            })

        # --- CASE 3: Transfer Call ---
        elif name == "transferCall":
            transfer_number = agency.get("human_agent_phone", "+8801322158015")
            print(f"🔄 Transfer | Number: {transfer_number}")

            results.append({
                "toolCallId"    : tool_id,
                "result"        : f"Transferring to {transfer_number}",
                "transfer_number": transfer_number
            })

        # --- DEFAULT ---
        else:
            results.append({
                "toolCallId": tool_id,
                "result"    : f"Tool {name} not found."
            })

    return {"results": results}


# ============================================
# INTERNAL HELPER
# ============================================
async def book_appointment_internal(
    customer_name: str,
    datetime_str : str,
    lead_id      : str,
    business_id  : str = ""
):
    """
    কাজ  : Calendly + Django তে booking করে
    """
    try:
        lead  = await db_service.get_lead(lead_id)
        email = lead.get("email", "customer@example.com") if lead else "customer@example.com"

        calendly_res = await calendly_service.create_invitee(
            customer_name= customer_name,
            email        = email,
            start_time   = datetime_str
        )

        meeting_link = "https://calendly.com/insureflow/meeting"
        if calendly_res:
            meeting_link = calendly_res.get("resource", {}).get("scheduling_url", meeting_link)

        # Django তে booking পাঠাও
        if business_id and lead_id:
            await django_service.send_booking(
                business_id  = business_id,
                booking_data = {
                    "lead_id"       : lead_id,
                    "meeting_date"  : datetime_str.split("T")[0] if "T" in datetime_str else datetime_str,
                    "meeting_time"  : datetime_str.split("T")[1][:8] if "T" in datetime_str else "10:00:00",
                    "meeting_link"  : meeting_link,
                    "status"        : "scheduled",
                    "customer_name" : customer_name,
                    "customer_email": email,
                    "customer_phone": ""
                }
            )

        return f"Successfully booked for {customer_name} on {datetime_str}."

    except Exception as e:
        print(f"❌ Booking Error: {str(e)}")
        return "Failed to book appointment. Please try again."


# ============================================
# TEST ENDPOINT
# ============================================
@router.get("/test")
async def tools_test():
    return {"router": "tools", "status": "ready"}