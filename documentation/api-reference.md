---
layout: default
title: API Reference
nav_order: 4
---

# API Reference

This document provides detailed information about the **Fever Model** of **Docokids** API endpoints. The system uses a **LangGraph** agent to handle pediatric fever triage.

**The chatbot and API are designed to handle conversations in Spanish.**

## Base URL

```
http://localhost:8000
```

## Authentication

The API uses two levels of authentication:

1.  **Admin Login**: Returns a JWT token and the shared API Key.
2.  **API Key**: Required for Chat and Feedback endpoints (Header: `X-API-Key`).

## Endpoints

### Authentication

#### Admin Login
```http
POST /api/admin/login
```

Login as administrator to obtain access tokens and the API key.

**Request Body**
```json
{
  "username": "admin",
  "password": "your_password"
}
```

**Response**
```json
{
  "access_token": "ey...",
  "token_type": "bearer",
  "expires_in": 604800,
  "api_key": "your_secret_api_key"
}
```

### Chat (LangGraph)

#### Send Message
```http
POST /chat/{chat_id}
```

Sends a user message to the LangGraph agent and receives the final response. The agent persists state using the `chat_id` (thread_id).

**Headers**
- `X-API-Key`: `your_secret_api_key`

**Request Body**
```json
{
  "message": "Hola, mi hijo tiene fiebre"
}
```

**Response**
```json
{
  "response": "Hola. Entiendo que tu hijo tiene fiebre. Para poder ayudarte mejor, ¿me podrías decir qué edad tiene?"
}
```

#### Stream Response
```http
POST /chat/{chat_id}/stream
```

Streams the agent's response token-by-token (Server-Sent Events).

**Headers**
- `X-API-Key`: `your_secret_api_key`

**Request Body**
```json
{
  "message": "Tiene 2 años"
}
```

**Response (SSE)**
```
data: Entiendo
data: ,
data: tiene
data: 2
data: años
...
```

### Feedback

#### Submit Feedback
```http
POST /submit-feedback
```

Submit user feedback about the triage experience.

**Headers**
- `X-API-Key`: `your_secret_api_key`

**Request Body**
```json
{
  "firstName": "Juan",
  "lastName": "Perez",
  "clarity": "Sí",
  "helpfulness": "Sí",
  "medicalGuidance": "Sí",
  "tone": "Sí",
  "confusion": "No",
  "recommendation": "Definitivamente sí",
  "improvements": "Ninguna",
  "sessionId": "chat_123"
}
```

#### Get All Feedback
```http
GET /feedback
```

Retrieves all feedback records.

**Headers**
- `X-API-Key`: `your_secret_api_key`

#### Get Feedback Stats
```http
GET /feedback/stats
```

Retrieves aggregated statistics.

**Headers**
- `X-API-Key`: `your_secret_api_key`

## Data Models

### Message
```json
{
  "message": "string"
}
```

### TokenResponse
```json
{
  "access_token": "string",
  "token_type": "string",
  "expires_in": "integer",
  "api_key": "string"
}
```

## Error Responses

The API uses standard HTTP status codes:

- `401 Unauthorized`: Invalid or missing API Key/Credentials.
- `422 Unprocessable Entity`: Invalid input data.
- `500 Internal Server Error`: Server processing error.
