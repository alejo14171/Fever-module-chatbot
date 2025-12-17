---
layout: default
title: Prompt Engineering
nav_order: 8
---

# 🧠 Prompt Engineering System

## Overview

The Fever Model uses a **LangGraph-based** architecture where prompt engineering is distributed across specialized **nodes**. Instead of a single monolithic prompt, we use distinct prompts for specific tasks: **Extraction (Receptor)**, **Inquiry**, and **Recommendation**.

## Architecture

The system is composed of specialized agents (nodes), each with its own prompt engineering strategy:

### 1. Receptor Node (Extraction)

**Goal**: Extract structured data from unstructured user messages into the `State`.

- **Strategy**: One-shot extraction with complex JSON-like structure parsing.
- **Prompt**:
  - Contains definitions for all state fields (e.g., `patient_age_months`, `temperature`, `fever_duration_hours`).
  - Instructs the LLM to output *only* the fields found in the user's message.
  - Handles normalization (e.g., "dos años" -> "24" months).

### 2. Inquiry Node (Question Generation)

**Goal**: Ask the next most important question to complete the clinical checklist.

- **Strategy**: Context-aware question generation based on missing fields.
- **Prompt**:
  - Receives the list of *missing* critical and important fields.
  - Instructs the LLM to ask *one* clear, empathetic question to gather the missing info.
  - Prioritizes urgency (e.g., if age is missing, ask age first).

### 3. Recommendation Node (Advice)

**Goal**: Provide clinical advice based on the completed checklist.

- **Strategy**: Chain-of-thought reasoning based on guidelines.
- **Prompt**:
  - Receives the fully populated `State`.
  - Includes clinical guidelines (NICE/AAP) for fever management.
  - Generates a structured response: Assessment -> Home Care -> Warning Signs.

## Key Prompt Features

### State-Driven Context
Instead of relying on conversation history strings, we inject the **Structured State** into the prompt. This reduces hallucinations and ensures the LLM focuses on what is known vs. unknown.

### Safety Rails
- **Urgency Detection**: A deterministic Python function (`assess_urgency`) runs *before* the LLM to detect red flags (e.g., age < 3 months, temp > 40°C).
- **Red Flag Prompts**: If red flags are detected, the system bypasses standard inquiry and triggers the `UrgencyRecommendation` node with a prompt focused on immediate action (ER/911).

## Example: Receptor Prompt

```python
SYSTEM_PROMPT = """
You are an expert medical data extractor.
Your job is to update the patient state based on the user's message.

OUTPUT FORMAT:
field_name: value

FIELDS:
- patient_age_months: Age in months (convert years to months).
- temperature: Body temperature in Celsius.
- symptoms: Comma-separated list of symptoms.

RULES:
- Only output fields present in the message.
- Normalize values (e.g., "39.5 degrees" -> "39.5").
"""
```

## Example: Inquiry Prompt

```python
SYSTEM_PROMPT = """
You are a pediatric triage assistant.
Your goal is to complete the clinical checklist.

MISSING DATA:
{missing_fields}

INSTRUCTION:
Ask ONE clear, polite question to get the most important missing field.
Do not give medical advice yet.
"""
```

## Configuration

Prompts are located in:
- `src/fever_routing/nodes/receptor/prompt.py`
- `src/fever_routing/nodes/inquiry/prompt.py`
- `src/fever_routing/nodes/recommendation/prompt.py`
