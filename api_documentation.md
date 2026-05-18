# Database Partner API Documentation

This document outlines the API endpoints required by the **InsureFlow AI** backend to communicate with the Database Partner service.

## 1. Overview
The InsureFlow AI backend acts as an orchestrator. It needs to fetch agency/lead information and save call/meeting logs to an external database. All requests will be sent in JSON format.

## 2. Authentication
All requests from the AI backend will include an API Key in the headers for security.
- **Header Name**: `X-Internal-Key`
- **Expected Value**: [To be shared securely]

---

## 3. Endpoints Table

| Category | Endpoint | Method | Purpose |
| :--- | :--- | :--- | :--- |
| **Agencies** | `/agencies/{id}` | GET | Fetch agency prompt, transfer number, and assistant ID |
| **Agencies** | `/agencies` | POST | Register a new insurance agency |
| **Agencies** | `/agencies/{id}` | PUT | Update agency settings (assistant_id, status, etc.) |
| **Leads** | `/leads` | GET | Fetch queued leads for a campaign (query: agency_id) |
| **Leads** | `/leads/{id}` | PUT | Update lead status/intent after a call |
| **Calls** | `/calls` | POST | Initialize a call record when a call starts |
| **Calls** | `/calls/{call_id}` | PUT | Save transcript, summary, duration, and intent after call ends |
| **Meetings** | `/meetings` | POST | Save booked appointment details (link, scheduled time) |

---

## 4. Detailed Data Schemas

### A. GET `/agencies/{id}`
**Response:**
```json
{
  "id": 1,
  "name": "ABC Insurance",
  "business_type": "health_insurance",
  "transfer_number": "+1234567890",
  "welcome_message": "Hello! How can I help?",
  "custom_prompt": "You are a professional assistant...",
  "vapi_assistant_id": "uuid-vapi-assistant-id",
  "twilio_number": "+1987654321",
  "status": "active"
}
```

### B. PUT `/leads/{id}`
**Request:**
```json
{
  "status": "contacted",
  "intent": "interested",
  "last_called_at": "2024-05-12T10:00:00Z"
}
```

### C. POST `/calls`
**Request:**
```json
{
  "call_id": "vapi_call_uuid",
  "lead_id": 101,
  "agency_id": 1,
  "status": "started",
  "started_at": "2024-05-12T10:00:00Z"
}
```

### D. PUT `/calls/{call_id}`
**Request:**
```json
{
  "status": "completed",
  "transcript": "Full call transcript here...",
  "summary": "Customer requested a quote for life insurance.",
  "duration_seconds": 125,
  "intent": "interested",
  "ended_at": "2024-05-12T10:05:00Z"
}
```

### E. POST `/meetings`
**Request:**
```json
{
  "call_id": "vapi_call_uuid",
  "lead_id": 101,
  "agency_id": 1,
  "meeting_link": "https://calendly.com/abc-insurance/meeting",
  "scheduled_at": "2024-05-15T09:00:00Z",
  "status": "booked"
}
```

---

## 5. Important Notes for DB Developer:
1. **Lead Table**: Please ensure the `leads` table has a `ghl_contact_id` (String) column to map CRM contacts.
2. **Date Format**: Use ISO 8601 format (`YYYY-MM-DDTHH:MM:SSZ`) for all timestamps.
3. **Async Support**: The AI backend uses `httpx` for asynchronous calls; ensure your API can handle concurrent requests efficiently.
