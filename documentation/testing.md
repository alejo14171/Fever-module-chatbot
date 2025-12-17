---
layout: default
title: Testing Guide
nav_order: 7
---

# Testing Guide

The **Fever Model** uses **pytest** for testing the LangGraph agent and the routing logic.

## Test Structure

Tests are located in `tests/fever_routing/`:

- `test_urgency.py`: Tests the urgency assessment logic (red flags, age/temp criteria).
- `test_graph.py`: Tests the construction and execution of the LangGraph agent.

## Running Tests

We recommend using `uv` to run tests:

```bash
# Run all tests
uv run pytest -v

# Run specific test file
uv run pytest tests/fever_routing/test_urgency.py -v
```

## Critical Safety Tests

The most important tests are in `test_urgency.py`. These verify that the system correctly identifies:
- **Critical Red Flags**: Convulsions, respiratory distress, etc.
- **Urgent Age Criteria**: Infants < 3 months with fever.
- **High Fever**: Temperature ≥ 40°C.

These tests ensure the safety of the triage recommendations.

## Adding New Tests

When modifying the routing logic (`src/fever_routing/routes/triage/route.py`), you **MUST** add corresponding tests in `test_urgency.py` to verify the new behavior and ensure no regressions in safety checks.
