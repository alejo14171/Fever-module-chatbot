# 🤖 Pediatric Fever Chatbot API

[![Documentation Status](https://img.shields.io/badge/docs-online-success)](https://alejo14171.github.io/Fever-module-chatbot/)
[![License: GPL v3](https://img.shields.io/badge/license-GPL--3.0-blue.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/framework-FastAPI-green)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/agent-LangGraph-orange)](https://langchain-ai.github.io/langgraph/)

---

## 📌 Table of Contents

- [About](#about)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
- [Usage](#usage)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)

---

## 🔍 About

This repository contains the **Fever Model** of **Docokids**, an AI-driven solution for pediatric fever assessment operating via a conversational API. 

The system uses a **LangGraph** agent to guide caregivers through a structured triage process, ensuring all critical information (age, temperature, symptoms) is collected before providing recommendations based on international clinical guidelines (NICE, AAP).

**The chatbot handles conversations in Spanish.**

---

## 🌍 Architecture

The core of the system is a **LangGraph State Machine** with the following nodes:

```mermaid
graph TD
    Start --> Receptor
    Receptor --> TriageRoute
    TriageRoute -- Critical/Urgent --> UrgencyRecommendation
    TriageRoute -- Missing Data --> Inquiry
    TriageRoute -- Complete --> Recommendation
    Inquiry --> End
    Recommendation --> End
    UrgencyRecommendation --> End
```

1.  **Receptor**: Extracts structured data (JSON) from user messages into the `State`.
2.  **TriageRoute**: Evaluates the state for urgency (Red Flags) or missing information.
3.  **Inquiry**: Generates the next best question to ask.
4.  **Recommendation**: Provides clinical advice once the checklist is complete.
5.  **UrgencyRecommendation**: Provides immediate emergency advice if red flags are detected.

---

## 🏗️ Tech Stack

- **Runtime**: Python 3.12+
- **API Framework**: FastAPI
- **Agent Framework**: LangGraph / LangChain
- **LLM**: OpenAI / Anthropic / Gemini (via LangChain)
- **Database**: PostgreSQL (for Checkpoint and Feedback)
- **Testing**: Pytest
- **Package Manager**: uv

---

## 🏁 Getting Started

### Prerequisites
- Python 3.12+
- [uv](https://github.com/astral-sh/uv)

### Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/alejo14171/Fever-module-chatbot.git
    cd Fever-module-chatbot
    ```

2.  **Install dependencies**:
    ```bash
    uv sync
    ```

3.  **Configure Environment**:
    Create `.env` based on example:
    ```bash
    OPENAI_API_KEY=sk-...
    DB_URI=postgresql://user:pass@localhost:5432/db
    API_KEY_SECRET=secret
    ```

4.  **Run with Docker**:
    ```bash
    docker-compose up --build
    ```

---

## 🚀 Usage

### Authenticate
Obtain an API key via admin login or config.

### Send Message
```bash
curl -X POST "http://localhost:8000/chat/{session_id}" \
     -H "Content-Type: application/json" \
     -H "X-API-Key: YOUR_API_KEY" \
     -d '{"message": "Mi hijo tiene fiebre"}'
```

### Stream Response
```bash
curl -X POST "http://localhost:8000/chat/{session_id}/stream" \
     ...
```

For full API details, see the [API Reference](documentation/api-reference.md).

---

## 📚 Documentation

- **[Getting Started](documentation/getting-started.md)**: Setup guide.
- **[API Reference](documentation/api-reference.md)**: Endpoints and models.
- **[Prompt Engineering](documentation/prompt-engineering.md)**: How the agent thinks.
- **[Testing](documentation/testing.md)**: How to verify the logic.

---

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](documentation/contributing.md).

1. Fork & Clone
2. `uv sync`
3. Create branch
4. `uv run pytest`
5. Submit PR

---

## 📄 License

This project is licensed under the **GNU GPL v3.0**. See the [LICENSE](LICENSE) file for details.
