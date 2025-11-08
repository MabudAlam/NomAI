
<div align="center">
  <img src="https://github.com/user-attachments/assets/e19e3402-96be-4280-9dd6-57ef31996429" alt="NomAI Logo" width="200"/>

# **NomAI**


Analyze food, chat with AI, and receive real-time nutrition insights using NomAI

</div>

---

## ⚡ Overview

NomAI is a powerful Agent that brings nutrition and food intelligence to life using AI. Whether you're analyzing meals through images or chatting with an AI assistant about health, NomAI handles the heavy lifting.

---

## ✨ Features

* 🧠 **AI Nutrition Analysis** — Understand food composition from text or food description.
* 💬 **Conversational AI Chatbot** — Talk about food, health, and lifestyle.
* 🔗 **RESTful APIs** — Simple and scalable endpoints for frontend integration.
* 🛢️ **Database-Driven** — PostgreSQL for  chat storage.

---

## 🚀 Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/Pavel401/nomai-backend.git
cd nomai-backend
```

### 2. Install Dependencies

```bash
uv sync
```

### 3. Set Up Environment

```bash
cp env_template .env
```

Fill in the values:

```
OPENAI_API_KEY=your_openai_key
POSTGRESQL_DB_URL=your_db_url
DB_KEY=your_db_secret
SUPABASE_URL=your_supabase_url
PROD=false  # use true for production
```

### 4. Run the Server

```bash
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```

---

## 🔌 API Endpoints

### 🥗 Nutrition

* `POST /nutrition/get`
  → Analyze food input (image or text) and return nutritional breakdown.

### 💬 Chat

* `GET /chat/`
  → Web-based chat interface (TypeScript powered).

* `GET /chat/messages`
  → Fetch chat history (stored in Supabase).

* `POST /chat/messages`
  → Send and store a new chat message.



## 🏗️ Folder Structure

```
nomai-backend/
├── app/
│   ├── agent/         # Core AI agent logic
│   ├── config/        # App settings & env
│   ├── endpoints/     # API route handlers
│   ├── exceptions/    # Custom error handling
│   ├── middleware/    # FastAPI middleware
│   ├── models/        # Pydantic data models
│   ├── services/      # Business logic layer
│   ├── static/        # Frontend files (HTML, TypeScript)
│   ├── tools/         # AI tools & utilities
│   └── utils/         # Helpers and shared utilities
├── main.py            # App entrypoint
├── env_template       # Sample env vars
├── Procfile           # Heroku deployment
├── runtime.txt        # Python runtime version
├── railway.json       # Railway deployment config
└── README.md          # Project documentation
```

---


## 👨‍💻 Tech Stack

| Tech             | Use Case                         |
| ---------------- | -------------------------------- |
| **FastAPI**      | API framework                    |
| **OpenAI GPT-4** | Chat & nutrition analysis        |
| **Pydantic-AI**  | Agent management & orchestration |
| **PostgreSQL**   | Primary database                 |
| **Supabase**     | Chat message storage             |
| **TypeScript**   | Chat frontend                    |
| **Python 3.13+** | Core backend language            |

---





