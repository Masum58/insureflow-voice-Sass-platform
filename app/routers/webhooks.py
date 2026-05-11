"""
File Name : webhooks.py

What this file does:
- Receives and processes all call events from Vapi
- Handles both:
  - Inbound calls (customer calls your AI)
  - Outbound calls (AI calls customers)

Who calls this file:
- Vapi system automatically
- Triggered when calls start or end

Connected with:
- vapi_service.py
- db_service.py
- ghl_service.py
"""

from fastapi import APIRouter, Request, HTTPException
from app import config

router = APIRouter()


# ============================================
# MAIN WEBHOOK ENDPOINT
#
# Purpose:
# All Vapi events come to this API
#
# URL:
# POST /webhooks/vapi
#
# Important:
# This URL must be added inside Vapi Dashboard
# ============================================

@router.post("/vapi")
async def vapi_webhook(request: Request):
    """
    Purpose:
    Receives all call events from Vapi

    Receives:
    JSON payload from Vapi

    Returns:
    Success or error response

    Workflow:
    Detects event type
    Sends event to the correct handler function
    """

    # Read JSON data from Vapi
    try:
        payload = await request.json()
    except:
        payload= {}

    # Get event information
    message = payload.get("message", {})
    event_type = message.get("type")

    # Get call type
    call = message.get("call", {})
    call_type = call.get("type")

    print(f"Event: {event_type} | Type: {call_type}")


    # ============================================
    # CALL STARTED EVENT
    #
    # Triggered when a call starts
    # ============================================

    if event_type == "call-start":

        if call_type == "inboundPhoneCall":
            return await handle_inbound_started(call)

        elif call_type == "outboundPhoneCall":
            return await handle_outbound_started(call)


    # ============================================
    # CALL ENDED EVENT
    #
    # Triggered when a call ends
    # ============================================

    elif event_type == "end-of-call-report":

        if call_type == "inboundPhoneCall":
            return await handle_inbound_ended(message)

        elif call_type == "outboundPhoneCall":
            return await handle_outbound_ended(message)


    # ============================================
    # UNKNOWN EVENT
    # ============================================

    else:
        print(f"Unknown event: {event_type}")

        return {
            "status": "ignored"
        }



# ============================================
# INBOUND CALL STARTED
#
# Triggered when:
# Customer calls the AI system
#
# Purpose:
# Save call start information
# ============================================

async def handle_inbound_started(call: dict):
    """
    Purpose:
    Creates inbound call record

    Receives:
    Call object from Vapi

    Returns:
    Success message

    Future Use:
    Will save data using db_service.py
    """

    call_id = call.get("id")
    customer_number = call.get("customer", {}).get("number")

    print(
        f"Inbound call started | "
        f"Call ID: {call_id} | "
        f"From: {customer_number}"
    )

    # TODO:
    # Save call data into database

    return {
        "status": "success",
        "type": "inbound_started"
    }



# ============================================
# INBOUND CALL ENDED
#
# Triggered when:
# Inbound call finishes
#
# Purpose:
# Save transcript and call duration
# Update CRM lead information
# ============================================

async def handle_inbound_ended(message: dict):
    """
    Purpose:
    Saves inbound call data

    Receives:
    Full message object from Vapi

    Returns:
    Success message

    Future Use:
    Will connect with:
    - db_service.py
    - ghl_service.py
    """

    call = message.get("call", {})
    call_id = call.get("id")

    transcript = message.get("transcript", "")
    duration = message.get("durationSeconds", 0)

    print(
        f"Inbound call ended | "
        f"Call ID: {call_id} | "
        f"Duration: {duration}s"
    )

    # TODO:
    # Save transcript and update CRM

    return {
        "status": "success",
        "type": "inbound_ended"
    }



# ============================================
# OUTBOUND CALL STARTED
#
# Triggered when:
# AI calls a lead and call connects
#
# Purpose:
# Save outbound call start information
# ============================================

async def handle_outbound_started(call: dict):
    """
    Purpose:
    Creates outbound call record

    Receives:
    Call object from Vapi

    Returns:
    Success message

    Future Use:
    Will save data using db_service.py
    """

    call_id = call.get("id")
    customer_number = call.get("customer", {}).get("number")

    print(
        f"Outbound call started | "
        f"Call ID: {call_id} | "
        f"To: {customer_number}"
    )

    # TODO:
    # Save outbound call data into database

    return {
        "status": "success",
        "type": "outbound_started"
    }



# ============================================
# OUTBOUND CALL ENDED
#
# Triggered when:
# Outbound call finishes
#
# Purpose:
# Save transcript, intent, and duration
# Update CRM lead status
# ============================================

async def handle_outbound_ended(message: dict):
    """
    Purpose:
    Saves outbound call data

    Receives:
    Full message object from Vapi

    Returns:
    Success message

    Future Use:
    Will connect with:
    - db_service.py
    - ghl_service.py
    """

    call = message.get("call", {})
    call_id = call.get("id")

    transcript = message.get("transcript", "")
    duration = message.get("durationSeconds", 0)

    print(
        f"Outbound call ended | "
        f"Call ID: {call_id} | "
        f"Duration: {duration}s"
    )

    # TODO:
    # Save transcript and update CRM

    return {
        "status": "success",
        "type": "outbound_ended"
    }



# ============================================
# TEST ENDPOINT
#
# Purpose:
# Check if webhook router is working
#
# URL:
# GET /webhooks/test
# ============================================

@router.get("/test")
async def webhooks_test():
    """
    Purpose:
    Confirms webhook router is running
    """

    return {
        "router": "webhooks",
        "status": "ready"
    }