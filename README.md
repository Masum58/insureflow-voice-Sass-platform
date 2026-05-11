# InsureFlow AI - Voice Assistant Backend

InsureFlow AI is a powerful AI-driven voice assistant designed specifically for the insurance industry. It enables agencies to automate lead qualification, appointment booking, and knowledge-based customer support using advanced Voice AI and Retrieval-Augmented Generation (RAG).

## 🚀 Key Features

- **Voice AI Integration**: Seamlessly connects with **Vapi** and **Twilio** for high-quality voice interactions.
- **RAG Knowledge Base**: Uses **ChromaDB** and **OpenAI** to provide accurate answers from uploaded documents (PDF, CSV, XML, TXT).
- **Lead Qualification**: Automatically detects customer intent and updates lead status in **GoHighLevel (GHL)**.
- **Appointment Booking**: Handles meeting requests and integrates with scheduling tools.
- **Multilingual Support**: Supports English and Bengali for diverse customer bases.
- **Scalable Architecture**: Built with **FastAPI**, **Redis**, and **Celery** for high-performance background processing.

---

## 🛠️ Tech Stack

- **Backend**: FastAPI (Python)
- **Database (Vector)**: ChromaDB
- **AI/ML**: OpenAI (Embeddings & GPT-4)
- **Voice Platform**: Vapi.ai
- **Telephony**: Twilio
- **CRM Integration**: GoHighLevel (GHL)
- **Task Queue**: Redis & Celery

---

## ⚙️ Setup Instructions

### 1. Prerequisites
- Python 3.10+
- Redis (installed and running)

### 2. Clone the Repository
```bash
git clone <repository-url>
cd insureflow-ai
```

### 3. Create Virtual Environment
```bash
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Environment Variables
Copy the `.env.example` file to `.env` and fill in your credentials:
```bash
cp .env.example .env
```

### 6. Run the Application
```bash
uvicorn app.main:app --reload
```
The server will start at `http://127.0.0.1:8000`.

---

## 📖 API Documentation

Access the interactive API docs:
- **Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

### Key Endpoints

| Category | Endpoint | Method | Description |
|----------|----------|--------|-------------|
| **Knowledge Base** | `/knowledge-base/upload` | POST | Upload PDF/CSV/XML/TXT to RAG |
| **Knowledge Base** | `/knowledge-base/files` | GET | List all uploaded documents |
| **Tools** | `/tools/book-appointment` | POST | Book customer meetings |
| **Tools** | `/tools/qualify-lead` | POST | Update lead status based on call |
| **Webhooks** | `/webhooks/vapi` | POST | Handle Vapi Voice AI events |

---

## 📂 Project Structure

```text
insureflow-ai/
├── app/
│   ├── main.py           # Entry point
│   ├── config.py         # Configuration settings
│   ├── routers/          # API Route handlers
│   ├── services/         # Business logic & integrations
│   └── workers/          # Background tasks (Celery)
├── chroma_db/            # Vector database storage
├── test_data/            # Sample files for testing
├── requirements.txt      # Python dependencies
└── .env                  # Secrets (git-ignored)
```

---

## 🛡️ License
This project is licensed under the MIT License.
