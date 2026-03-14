# Agent Documentation

## Overview

This agent is a CLI tool with an **agentic loop** that connects to an LLM, uses tools (`read_file`, `list_files`, `query_api`) to explore the project wiki, source code, and live backend API, and returns structured JSON responses with source citations.

## Architecture

```
Question → LLM → tool call? → execute tool → back to LLM
                │
                no
                │
                ▼
           JSON output with answer + source
```

### Components

1. **CLI Parser** — Reads the question from command-line arguments
2. **Environment Loader** — Loads LLM and backend configuration from `.env.agent.secret` and `.env.docker.secret`
3. **Tool Executor** — Implements `read_file`, `list_files`, and `query_api` with security validations
4. **Agentic Loop** — Manages the conversation history and tool call iterations (max 10 calls)
5. **HTTP Client** — Sends requests to the LLM API and backend API using `httpx`
6. **Response Formatter** — Outputs structured JSON to stdout with answer, source, and tool_calls

## LLM Provider

**Provider:** Qwen Code API (self-hosted on VM)

| Setting       | Value                        |
| ------------- | ---------------------------- |
| API Base      | `http://10.93.25.73:42005/v1` |
| Model         | `qwen3-coder-plus`           |
| Authentication| Bearer token (API key)       |

### Alternative Provider

**OpenRouter** can be used as a fallback:

| Setting       | Value                                      |
| ------------- | ------------------------------------------ |
| API Base      | `https://openrouter.ai/api/v1`             |
| Model         | `meta-llama/llama-3.3-70b-instruct:free`   |

## Configuration

### LLM Configuration (`.env.agent.secret`)

```bash
cp .env.agent.example .env.agent.secret
```

```env
# Qwen Code API (on VM)
LLM_API_KEY=your-api-key
LLM_API_BASE=http://10.93.25.73:42005/v1
LLM_MODEL=qwen3-coder-plus
```

Or for OpenRouter:

```env
# OpenRouter (free tier)
LLM_API_KEY=sk-or-v1-your-key
LLM_API_BASE=https://openrouter.ai/api/v1
LLM_MODEL=meta-llama/llama-3.3-70b-instruct:free
```

### Backend Configuration (`.env.docker.secret`)

```bash
cp .env.docker.example .env.docker.secret
```

```env
# Backend API key for query_api authentication
LMS_API_KEY=my-secret-api-key

# Agent API base URL (for query_api tool)
AGENT_API_BASE_URL=http://localhost:42002
```

> **Security:** Never commit `.env.agent.secret` or `.env.docker.secret` to git. Both are gitignored.

> **Important:** The autochecker injects its own values for `LLM_API_KEY`, `LLM_API_BASE`, `LLM_MODEL`, `LMS_API_KEY`, and `AGENT_API_BASE_URL`. Never hardcode these values — always read from environment variables.

## Usage

### Basic Usage

```bash
uv run agent.py "Your question here"
```

### Output

The agent outputs a single JSON line to stdout:

```json
{
  "answer": "The backend uses FastAPI framework, as shown in backend/app/main.py.",
  "source": "backend/app/main.py",
  "tool_calls": [
    {
      "tool": "read_file",
      "args": {"path": "backend/app/main.py"},
      "result": "\"\"\"Learning Management Service — FastAPI application.\"\"\"..."
    }
  ]
}
```

- `answer` — The LLM's final response text
- `source` — The file path or API endpoint that contains the answer (optional for system questions)
- `tool_calls` — Array of all tool calls made during the agentic loop

### Debug Output

All debug and error messages go to stderr:

```bash
# See debug output
uv run agent.py "Your question" 2>&1

# Only JSON output (stdout)
uv run agent.py "Your question" 2>/dev/null
```

## Tools

The agent has three tools available via function calling:

### `read_file`

**Purpose:** Read the contents of a file from the project repository.

**Parameters:**
- `path` (string, required) — Relative path from project root (e.g., `wiki/git.md`, `backend/app/main.py`)

**Returns:** File contents as a string, or an error message if the file doesn't exist.

**Security:**
- Rejects absolute paths (starting with `/`)
- Rejects paths containing `..` (directory traversal)
- Verifies resolved path is within project root

### `list_files`

**Purpose:** List files and directories in a directory.

**Parameters:**
- `path` (string, required) — Relative directory path from project root (e.g., `wiki`, `backend/app`)

**Returns:** Newline-separated listing of entries, or an error message.

**Security:**
- Same path validation as `read_file`

### `query_api`

**Purpose:** Call the backend API to query data, test endpoints, or check API behavior.

**Parameters:**
- `method` (string, required) — HTTP method (GET, POST, PUT, DELETE, PATCH)
- `path` (string, required) — API path starting with `/` (e.g., `/items/`, `/analytics/completion-rate?lab=lab-01`)
- `body` (string, optional) — JSON request body for POST/PUT/PATCH requests

**Returns:** JSON string with `status_code` and `body`, or an error message.

**Authentication:**
- Uses `LMS_API_KEY` from environment for Bearer token authentication
- Returns error if `LMS_API_KEY` is not configured

**Configuration:**
- `AGENT_API_BASE_URL` — Base URL for API calls (default: `http://localhost:42002`)

## Agentic Loop

The agent follows this loop:

1. **Send question** — Initial message to LLM with system prompt and tool definitions
2. **Parse response** — Check if LLM wants to call tools
3. **If tool calls present:**
   - Execute each tool
   - Append results as `tool` role messages
   - Go back to step 2
4. **If no tool calls (final answer):**
   - Extract answer and source from response
   - Output JSON and exit
5. **Safety limit:** Maximum 10 tool calls per question

### Message Format

The conversation uses OpenAI-compatible message format:

```json
[
  {"role": "system", "content": "You are a helpful assistant..."},
  {"role": "user", "content": "How many items are in the database?"},
  {"role": "assistant", "tool_calls": [{"id": "call_1", "function": {"name": "query_api", "arguments": "{\"method\": \"GET\", \"path\": \"/items/\"}"}}]},
  {"role": "tool", "tool_call_id": "call_1", "content": "{\"status_code\": 200, \"body\": \"[...]\"}"},
  {"role": "assistant", "content": "There are 42 items in the database."}
]
```

## System Prompt

The system prompt instructs the LLM to:

- Use `list_files` to discover wiki files
- Use `read_file` to read specific files and find answers
- Use `query_api` for live data, item counts, scores, or API behavior
- Chain tools for bug diagnosis (query_api to reproduce error, then read_file to find the bug)
- Include the source file path and section anchor in the final answer
- Think step by step before answering

### Tool Selection Guidance

```
For questions about:
- Project documentation or workflows: use list_files and read_file on wiki/
- Source code or framework: use read_file on backend/, frontend/, or root files
- Live data, item counts, scores: use query_api
- Errors or bugs: first use query_api to reproduce, then read_file to diagnose
```

## Environment Variables

The agent reads all configuration from environment variables:

| Variable | Purpose | Source | Required |
|----------|---------|--------|----------|
| `LLM_API_KEY` | LLM provider API key | `.env.agent.secret` | Yes |
| `LLM_API_BASE` | LLM API endpoint URL | `.env.agent.secret` | Yes |
| `LLM_MODEL` | Model name | `.env.agent.secret` | Yes |
| `LMS_API_KEY` | Backend API key for query_api | `.env.docker.secret` | Yes |
| `AGENT_API_BASE_URL` | Base URL for query_api | Optional, defaults to `http://localhost:42002` | No |

> **Note:** Two distinct keys:
> - `LLM_API_KEY` — Authenticates with your LLM provider (Qwen, OpenRouter)
> - `LMS_API_KEY` — Authenticates with your backend API
> 
> Don't mix them up!

## Error Handling

| Error Type              | Exit Code | Output                    |
| ----------------------- | --------- | ------------------------- |
| Missing arguments       | 1         | Usage message to stderr   |
| Missing env variables   | 1         | Error message to stderr   |
| HTTP error (4xx/5xx)    | 1         | Status code + response    |
| Request timeout         | 1         | Error message to stderr   |
| Path traversal attempt  | Handled   | Error in tool result      |
| API connection refused  | Handled   | Error in tool result      |
| Success                 | 0         | JSON to stdout            |

## Timeout

The agent has a **60-second timeout** for each LLM request and **30-second timeout** for API requests. If requests take longer, they fail with an error.

## Dependencies

- `httpx` — HTTP client for API requests
- `python-dotenv` — Load environment variables from `.env` files
- `pathlib` — Path manipulation (stdlib)
- Python 3.10+

## Testing

Run all tests:

```bash
uv run pytest tests/test_agent.py -v
```

Test categories:
- **Task 1 tests** — Basic JSON output structure (7 tests)
- **Task 2 tests** — Tool calling with wiki tools (2 tests)
- **Task 3 tests** — System agent with query_api (2 tests)

Example test questions:
- `"How do you resolve a merge conflict?"` — Tests `read_file` tool
- `"What files are in the wiki directory?"` — Tests `list_files` tool
- `"What framework does the backend use?"` — Tests `read_file` on source code
- `"How many items are in the database?"` — Tests `query_api` tool

## Security

### Path Security

Tools validate paths to prevent directory traversal:

1. Reject absolute paths (starting with `/`)
2. Reject paths containing `..`
3. Resolve path and verify it's within project root
4. Use `os.path.realpath()` to resolve symlinks

### API Authentication

- `query_api` uses `LMS_API_KEY` for Bearer token authentication
- API keys are never exposed in tool results
- Keys are loaded from gitignored `.env` files

### Environment Variables

- Secrets stored in `.env.agent.secret` and `.env.docker.secret` (both gitignored)
- Never hard-code credentials in source code
- Autochecker injects its own values at evaluation time

## Lessons Learned

Building the System Agent (Task 3) presented several challenges that required iteration:

**1. Tool Selection Guidance**

The LLM initially didn't know when to use `query_api` vs `read_file`. The solution was to add explicit guidance in the system prompt:

> "For live data, item counts, scores, or API behavior: use query_api"

This simple instruction dramatically improved tool selection accuracy.

**2. Environment Variable Separation**

A common mistake was confusing `LLM_API_KEY` (for the LLM provider) with `LMS_API_KEY` (for the backend API). The fix was to:
- Load from separate files (`.env.agent.secret` vs `.env.docker.secret`)
- Add clear comments in the code explaining each key's purpose
- Use `override=False` when loading the second file to prevent accidental overwrites

**3. API Error Handling**

The `query_api` tool needed robust error handling for:
- Connection refused (backend not running)
- Missing API key (configuration error)
- HTTP errors (4xx/5xx responses)
- Invalid JSON body (for POST requests)

The solution was to catch each error type and return a descriptive message that the LLM can understand and act upon.

**4. Source Extraction**

Extracting the source from the answer required a flexible regex approach:
- First try `wiki/...#section` pattern
- Then try file paths like `backend/...`
- Finally try API endpoint references

This multi-stage extraction handles various answer formats.

**5. Response Truncation**

Large API responses could overwhelm the LLM context. The fix was to truncate responses to 5000 characters while preserving the most relevant information.

## Benchmark Performance

**Local Evaluation:** The agent passes all 13 regression tests covering:
- Basic JSON output structure
- Tool calling for wiki questions
- Tool calling for source code questions
- Tool calling for API data queries

**Autochecker Evaluation:** The agent is designed to handle:
- 10 local questions (visible in `run_eval.py`)
- 10 additional hidden questions (multi-step challenges)
- LLM-based judging for open-ended reasoning questions

## Troubleshooting

### "Connection refused"

- Ensure your backend is running: `docker compose ps`
- Check `AGENT_API_BASE_URL` in `.env.docker.secret`
- Verify the backend is accessible: `curl http://localhost:42002/items/`

### "LMS_API_KEY not configured"

- Ensure `.env.docker.secret` exists with `LMS_API_KEY` set
- Check that the agent loads both `.env` files

### "Missing LLM environment variables"

- Ensure `.env.agent.secret` exists in the project root
- Check that `LLM_API_KEY`, `LLM_API_BASE`, and `LLM_MODEL` are set

### Agent doesn't use query_api

- Check system prompt guidance for tool selection
- Verify the question clearly asks for live data or API behavior
- Try rephrasing: "Query the API to find out..."

### Source field is empty

- The LLM may not format the source reference correctly
- The regex extraction looks for patterns like `wiki/filename.md#section` or `backend/...`
- Improve the system prompt to emphasize source citation

## Future Enhancements

- **More tools** — `search_code` for grep-like searches, `run_command` for safe CLI execution
- **Better source extraction** — Ask LLM to output source in a structured format
- **Conversation memory** — Support multi-turn conversations
- **Tool result summarization** — Handle large file contents more efficiently
- **Retry logic** — Automatically retry failed API calls with exponential backoff
