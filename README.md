# AI Career Coach 🚀

> Intelligent career assessment and growth platform powered by AI.

## 📌 Overview

AI Career Coach analyzes candidate profiles, GitHub repositories, and resumes to generate deep skill assessments, identify strengths and knowledge gaps, and recommend tailored learning roadmaps.

## 🏗️ Architecture & Tech Stack

- **Backend**: FastAPI / Python, SQLAlchemy, Groq LLM integration
- **Frontend**: React + Vite, Tailwind CSS, Lucide icons
- **Database**: SQLite (local) / PostgreSQL (production)
- **AI / LLM Engine**: Groq API (Qwen / GPT-OSS models) with schema validation and fallback handling

For detailed architectural specifications, please refer to [`ai_career_coach_architecture.md`](./ai_career_coach_architecture.md).

---

## ⚡ Quick Start

### 1. Backend Setup

```bash
# Navigate to backend
cd backend

# Install dependencies
pip install -r ../requirements.txt

# Configure environment variables
cp ../.env.example ../.env
# Edit .env with your GROQ_API_KEY and other credentials

# Start the FastAPI server
uvicorn app.main:app --reload --port 8000
```

### 2. Frontend Setup

```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# Run the development server
npm run dev
```

---

## 🧪 Verification & Tests

Run test verifications from the `backend/` directory:
```bash
python verify_level1.py
python verify_level2.py
python verify_level3.py
python verify_level4.py
python verify_level5.py
python verify_llm.py
```
