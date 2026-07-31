# Vaidya AI — Pre-Consultation Medical Intake

AI-powered pre-consultation intake system that collects patient symptoms before they see the doctor. Saves doctor's time, reduces patient waiting experience, and provides structured clinical summaries.

## How It Works

```
Hospital registers patient → AI conducts intake (5 questions) → Structured summary sent to doctor
```

1. Hospital system calls `/register-patient` with patient name, ID, and specialty
2. AI greets the patient by name and asks specialty-specific questions
3. After 5 questions, AI provides safe self-care advice and ends the session
4. Structured clinical summary is generated and sent to the hospital's endpoint

## Tech Stack

- **Backend:** Python 3.11+, FastAPI, AWS Bedrock (Claude Haiku 4.5)
- **Frontend:** React, TanStack Router, Tailwind CSS (WhatsApp-style chat UI)
- **LLM:** Amazon Bedrock — `global.anthropic.claude-haiku-4-5-20251001-v1:0`
- **Architecture:** In-memory sessions (DB integration planned)

## Supported Specialties

- General Physician (MD)
- Cardiologist
- Neurologist
- Dermatologist
- Gastroenterologist
- Orthopedic
- ENT (Ear, Nose & Throat)
- Gynecologist

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/register-patient` | POST | Register patient, get first AI message |
| `/api/v1/chat` | POST | Send patient message, get AI response |
| `/api/v1/session/{id}/status` | GET | Check session status |
| `/api/v1/session/{id}/summary` | GET | Get clinical summary (after completion) |
| `/api/v1/session/{id}/history` | GET | Get conversation transcript |
| `/api/v1/hospital/{id}/sessions` | GET | List all sessions for a hospital |
| `/health` | GET | Health check |

## Quick Start

### Backend

```bash
cd backend
pip install -e .
cp .env.example .env   # Add your AWS credentials
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
node node_modules/vite/bin/vite.js dev
```

Open `http://localhost:8080` for the chat UI.
Open `http://localhost:8000/docs` for the API docs.

## Environment Variables

Create `backend/.env`:

```
AWS_ACCESS_KEY_ID=your-key
AWS_SECRET_ACCESS_KEY=your-secret
AWS_REGION=ap-south-1
BEDROCK_MODEL_ID=global.anthropic.claude-haiku-4-5-20251001-v1:0
APP_ENV=development
```

## Project Structure

```
Vaidya-AI/
├── README.md
├── .gitignore
├── backend/
│   ├── pyproject.toml
│   ├── .env.example
│   └── app/
│       ├── main.py                 # FastAPI app entry point
│       ├── config.py               # Settings (loads .env)
│       ├── api/routes/
│       │   ├── registration.py     # POST /register-patient
│       │   ├── chat.py             # POST /chat
│       │   ├── sessions.py         # GET session status/summary/history
│       │   └── hospital.py         # GET hospital sessions list
│       ├── services/
│       │   ├── bedrock_service.py  # AWS Bedrock Converse API wrapper
│       │   ├── conversation_service.py  # Chat logic
│       │   ├── prompt_service.py   # 8 specialty prompts
│       │   ├── session_manager.py  # Session CRUD + 30min timeout
│       │   ├── summary_service.py  # Clinical summary generation
│       │   └── callback_service.py # POST summary to hospital endpoint
│       └── models/
│           └── session.py          # Session dataclass
│
└── frontend/
    ├── package.json
    ├── vite.config.ts
    └── src/
        ├── routes/index.tsx         # Registration form + chat page
        ├── components/chat/
        │   ├── ChatWindow.tsx       # Chat UI component
        │   └── MessageBubble.tsx    # Message bubble component
        └── lib/chat-data.ts         # Types + API config
```

## Features

- 8 specialty-specific AI prompts with targeted clinical questions
- 5-question hard cap (fast intake, under 2 minutes)
- Emergency detection (chest pain, stroke signs, etc.) — alerts staff immediately
- Sensitive topic handling (no direct pregnancy questions, neutral framing)
- Information gap flagging in summaries (doctor knows what to explore further)
- Multi-language detection (English, Hindi, Hinglish, regional)
- Safe self-care advice at session end
- Session timeout (30 min inactivity → auto-expire with partial summary)
- Hospital callback (auto-POST summary to hospital endpoint)

## License

Private — Internal use only.
