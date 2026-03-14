# Agent Documentation

## Overview

This agent is a CLI tool that connects to an LLM (Large Language Model) and returns structured JSON responses. It serves as the foundation for a more advanced agentic system with tools and domain knowledge.

## Architecture

```
User question → agent.py → LLM API → JSON answer
```

### Components

1. **CLI Parser** — Reads the question from command-line arguments
2. **Environment Loader** — Loads LLM configuration from `.env.agent.secret`
3. **HTTP Client** — Sends requests to the LLM API using `httpx`
4. **Response Formatter** — Outputs structured JSON to stdout

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

Create `.env.agent.secret` in the project root:

```bash
cp .env.agent.example .env.agent.secret
```

Edit the file with your credentials:

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

> **Security:** Never commit `.env.agent.secret` to git. It is gitignored.

## Usage

### Basic Usage

```bash
uv run agent.py "What does REST stand for?"
```

### Output

The agent outputs a single JSON line to stdout:

```json
{"answer": "Representational State Transfer.", "tool_calls": []}
```

- `answer` — The LLM's response text
- `tool_calls` — Empty array for Task 1 (will be populated in Tasks 2–3)

### Debug Output

All debug and error messages go to stderr:

```bash
# See debug output
uv run agent.py "Your question" 2>&1

# Only JSON output (stdout)
uv run agent.py "Your question" 2>/dev/null
```

## System Prompt

The agent uses a minimal system prompt for Task 1:

```
You are a helpful assistant that answers questions concisely and accurately.
Provide direct, factual answers without unnecessary elaboration.
```

This prompt will be expanded in Tasks 2–3 to include tool instructions and domain knowledge.

## Error Handling

| Error Type              | Exit Code | Output                    |
| ----------------------- | --------- | ------------------------- |
| Missing arguments       | 1         | Usage message to stderr   |
| Missing env variables   | 1         | Error message to stderr   |
| HTTP error (4xx/5xx)    | 1         | Status code + response    |
| Request timeout         | 1         | Error message to stderr   |
| Success                 | 0         | JSON to stdout            |

## Timeout

The agent has a **60-second timeout** for LLM responses. If the LLM takes longer, the request fails with an error.

## Dependencies

- `httpx` — HTTP client for API requests
- `python-dotenv` — Load environment variables from `.env` file
- Python 3.10+

## Testing

Run the agent with a simple question:

```bash
uv run agent.py "What is 2 + 2?"
```

Expected output:

```json
{"answer": "2 + 2 = 4.", "tool_calls": []}
```

## Future Enhancements (Tasks 2–3)

- **Tool Integration** — Add `read_file`, `list_files`, `query_api` tools
- **Agentic Loop** — Implement tool selection and iterative reasoning
- **Domain Knowledge** — Add system prompt with project context
- **Wiki Access** — Enable reading project documentation via tools

## Troubleshooting

### "Connection refused"

- Ensure your VM is running and accessible
- Check that the Qwen Code API container is running: `docker ps`
- Verify the IP address and port in `.env.agent.secret`

### "No credentials found"

- The Qwen Code API proxy on your VM needs authentication
- Run `qwen auth` on your VM to authenticate
- Or set `QWEN_API_KEY` in `~/qwen-code-oai-proxy/.env` on your VM

### "Missing environment variables"

- Ensure `.env.agent.secret` exists in the project root
- Check that `LLM_API_KEY`, `LLM_API_BASE`, and `LLM_MODEL` are set
