---
layout: default
title: Getting Started
nav_order: 3
---

# Getting Started

This guide will help you set up and run the **Fever Model** of **Docokids** locally. The system is built with **FastAPI** and **LangGraph**.

## Prerequisites

- Python 3.12 or higher
- [uv](https://github.com/astral-sh/uv) (recommended package manager)
- Docker and Docker Compose (optional, for DB/prod)

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/alejo14171/Fever-module-chatbot.git
cd Fever-module-chatbot
```

### 2. Configure Environment

Create a `.env` file in the root directory:

```env
# API Security
API_KEY_SECRET=your_super_secret_api_key
JWT_SECRET_KEY=your_jwt_secret_key
ADMIN_USERNAME=admin
ADMIN_PASSWORD=secure_password

# Database (PostgreSQL)
DB_URI=postgresql://user:password@localhost:5432/fever_db

# LLM Providers
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# LangSmith (Optional, for tracing)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2-...
```

### 3. Install Dependencies (using uv)

```bash
uv pip install -r requirements.txt
# OR if using uv directly
uv sync
```

### 4. Run with Docker Compose (Recommended)

This starts the API and a PostgreSQL database.

```bash
docker-compose up --build
```

The API will be available at `http://localhost:8000`.

### 5. Run Manually

If you have a local PostgreSQL running:

```bash
# Activate virtualenv
source .venv/bin/activate

# Run FastAPI
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

## API Usage

1.  **Get API Key**:
    ```bash
    curl -X POST "http://localhost:8000/api/admin/login" \
         -H "Content-Type: application/json" \
         -d '{"username": "admin", "password": "secure_password"}'
    ```
    Copy the `api_key` from the response.

2.  **Start Chat**:
    ```bash
    curl -X POST "http://localhost:8000/chat/session_1" \
         -H "Content-Type: application/json" \
         -H "X-API-Key: YOUR_API_KEY" \
         -d '{"message": "Hola, mi bebé tiene fiebre"}'
    ```

## Development

### Project Structure

```
src/
├── api/              # FastAPI endpoints (main.py, auth.py)
├── fever_routing/    # LangGraph Logic
│   ├── agent.py      # Graph definition
│   ├── state.py      # State schema
│   ├── nodes/        # Graph nodes (Receptor, Inquiry, etc.)
│   └── routes/       # Routing logic
```

### Running Tests

```bash
# Install test dependencies
uv pip install pytest

# Run tests
uv run pytest
```
