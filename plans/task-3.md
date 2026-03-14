# Task 3: The System Agent - Implementation Plan

## Overview

Extend the Task 2 agent with a `query_api` tool to interact with the deployed backend API. This enables the agent to answer both static system questions (framework, ports) and data-dependent queries (item count, scores).

## Tool Definition: `query_api`

**Purpose:** Call the deployed backend API with authentication.

**Schema (OpenAI function calling format):**
```json
{
  "name": "query_api",
  "description": "Call the backend API to query data or test endpoints",
  "parameters": {
    "type": "object",
    "properties": {
      "method": {
        "type": "string",
        "description": "HTTP method (GET, POST, PUT, DELETE, etc.)",
        "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"]
      },
      "path": {
        "type": "string",
        "description": "API path starting with / (e.g., '/items/', '/analytics/completion-rate')"
      },
      "body": {
        "type": "string",
        "description": "Optional JSON request body for POST/PUT/PATCH requests"
      }
    },
    "required": ["method", "path"]
  }
}
```

**Implementation:**
- Read `LMS_API_KEY` from environment (via `.env.docker.secret`)
- Read `AGENT_API_BASE_URL` from environment (default: `http://localhost:42002`)
- Make HTTP request with `Authorization: Bearer {LMS_API_KEY}` header
- Return JSON response with `status_code` and `body`

## Environment Variables

The agent must read all configuration from environment variables:

| Variable | Purpose | Source | Required |
|----------|---------|--------|----------|
| `LLM_API_KEY` | LLM provider API key | `.env.agent.secret` | Yes |
| `LLM_API_BASE` | LLM API endpoint URL | `.env.agent.secret` | Yes |
| `LLM_MODEL` | Model name | `.env.agent.secret` | Yes |
| `LMS_API_KEY` | Backend API key for query_api | `.env.docker.secret` | Yes |
| `AGENT_API_BASE_URL` | Base URL for query_api | Optional, defaults to `http://localhost:42002` | No |

**Important:** The autochecker injects its own values. Never hardcode these.

## System Prompt Update

The system prompt should guide the LLM to choose the right tool:

- **Wiki questions** (how to, workflow, concepts) → use `list_files` and `read_file`
- **System facts** (framework, ports, status codes) → use `query_api` or `read_file` on source code
- **Data queries** (how many items, scores) → use `query_api`
- **Bug diagnosis** → use `query_api` to reproduce error, then `read_file` to find the bug

Example guidance:
```
For questions about:
- Project documentation or workflows: use list_files and read_file on wiki/
- Source code or framework: use read_file on backend/ or frontend/
- Live data or API behavior: use query_api
- Errors or bugs: first use query_api to reproduce, then read_file to diagnose
```

## Agentic Loop

The loop remains the same as Task 2, just with an additional tool available:

1. Send question + tool definitions to LLM
2. If tool_calls present → execute tools, append results, go to step 1
3. If no tool_calls → extract answer and source, output JSON
4. Max 10 tool calls

## Output Format

```json
{
  "answer": "The backend uses FastAPI framework.",
  "source": "",  // Empty for system questions without wiki source
  "tool_calls": [
    {
      "tool": "read_file",
      "args": {"path": "backend/app/main.py"},
      "result": "from fastapi import FastAPI..."
    }
  ]
}
```

Note: `source` is now optional - system questions may not have a wiki source.

## Benchmark Strategy

Run `run_eval.py` and iterate:

1. Run initial evaluation
2. For each failure:
   - Check if wrong tool was used
   - Check if tool returned an error
   - Check if system prompt needs clarification
3. Fix and re-run until all 10 questions pass

Expected failures and fixes:
- **Q4 (items count)**: Agent may not know to call `/items/` → improve system prompt
- **Q5 (status code)**: Agent may not know to omit auth header → clarify in prompt
- **Q6-7 (bug diagnosis)**: Agent needs to chain query_api + read_file → ensure loop works
- **Q8-9 (LLM judge)**: Need comprehensive answers → improve system prompt for thoroughness

## Initial Benchmark Results

**Status:** Backend needs to be running for full evaluation.

Manual testing shows:
- Agent correctly selects `read_file` for framework questions ✓
- Agent correctly selects `query_api` for data questions ✓
- Agent correctly chains tools (query_api → read_file for debugging) ✓

**Next steps:**
1. Start the backend with `docker compose up -d`
2. Run `uv run run_eval.py` to evaluate all 10 questions
3. Iterate on failures

## Security

- `query_api` must authenticate with `LMS_API_KEY`
- Never expose API keys in tool results
- Validate API paths (no arbitrary URL fetching)

## Testing

Add 2 regression tests:
1. `"What framework does the backend use?"` → expects `read_file` in tool_calls
2. `"How many items are in the database?"` → expects `query_api` in tool_calls

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Agent doesn't call query_api | Improve tool description and system prompt |
| API authentication fails | Verify LMS_API_KEY is loaded correctly |
| Agent confuses LLM_API_KEY and LMS_API_KEY | Clear variable naming, separate files |
| Tool returns too much data | Truncate large responses |
