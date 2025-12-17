---
layout: default
title: Pediatric Fever Chatbot API
nav_order: 1
---

# Pediatric Fever Chatbot API

Welcome to the documentation for the **Fever Model** of **Docokids**. This system uses a state-of-the-art **LangGraph** agent to perform pediatric fever triage based on international clinical guidelines.

## Key Features

- **Clinical Triage Graph**: A structured state machine (LangGraph) that guides the conversation from data collection to recommendation.
- **Urgency Detection**: Real-time analysis of red flags (e.g., convulsions, breathing difficulty) and risk factors (age < 3 months).
- **Checklist-Based**: Ensures all critical information (age, temperature, duration, hydration) is collected before making a recommendation.
- **FastAPI Integration**: Secure, high-performance API with streaming support.
- **PostgreSQL Persistence**: Stores conversation state and user feedback.

## Architecture

The system is built on **LangGraph**, where the conversation flow is modeled as a graph of nodes:

1.  **Receptor**: Extracts structured information (e.g., "39°C", "2 years") from user messages.
2.  **Triage Route**: Analyzes the state to decide the next step:
    *   **Urgency Recommendation**: Immediate advice if red flags are detected.
    *   **Recommendation**: Final advice if enough information is gathered.
    *   **Inquiry**: Ask follow-up questions if data is missing.
3.  **Nodes**: specialized Python functions that handle each step.

## Tech Stack

- **Framework**: FastAPI
- **Agent Orchestration**: LangGraph / LangChain
- **Database**: PostgreSQL (psycopg3)
- **Runtime**: Python 3.12+
- **Testing**: Pytest

## Getting Started

Check out the [Getting Started](getting-started.md) guide to set up the project locally.

## API Reference

Explore the endpoints in the [API Reference](api-reference.md).
