# Agent Documentation

## Overview

This agent is a CLI tool with an **agentic loop** that connects to an LLM, uses tools (`read_file`, `list_files`) to explore the project wiki, and returns structured JSON responses with source citations.

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
2. **Environment Loader** — Loads LLM configuration from `.env.agent.secret`
3. **Tool Executor** — Implements `read_file` and `list_files` with path security
4. **Agentic Loop** — Manages the conversation history and tool call iterations
5. **HTTP Client** — Sends requests to the LLM API using `httpx`
6. **Response Formatter** — Outputs structured JSON to stdout

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
uv run agent.py "Your question here"
```

### Output

The agent outputs a single JSON line to stdout:

```json
{
  "answer": "A merge conflict occurs when two branches modify the same lines...",
  "source": "wiki/git.md#merge-conflict",
  "tool_calls": [
    {
      "tool": "list_files",
      "args": {"path": "wiki"},
      "result": "api.md\narchitectural-views.md\n..."
    },
    {
      "tool": "read_file",
      "args": {"path": "wiki/git.md"},
      "result": "# Git\n\n..."
    }
  ]
}
```

- `answer` — The LLM's final response text
- `source` — The wiki file and section that contains the answer (e.g., `wiki/git.md#merge-conflict`)
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

The agent has two tools available via function calling:

### `read_file`

**Purpose:** Read the contents of a file from the project repository.

**Parameters:**
- `path` (string, required) — Relative path from project root (e.g., `wiki/git.md`)

**Returns:** File contents as a string, or an error message if the file doesn't exist.

**Security:**
- Rejects absolute paths (starting with `/`)
- Rejects paths containing `..` (directory traversal)
- Verifies resolved path is within project root

### `list_files`

**Purpose:** List files and directories in a directory.

**Parameters:**
- `path` (string, required) — Relative directory path from project root (e.g., `wiki`)

**Returns:** Newline-separated listing of entries, or an error message.

**Security:**
- Same path validation as `read_file`

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
  {"role": "user", "content": "How do you resolve a merge conflict?"},
  {"role": "assistant", "tool_calls": [{"id": "call_1", "function": {"name": "list_files", "arguments": "{\"path\": \"wiki\"}"}}]},
  {"role": "tool", "tool_call_id": "call_1", "content": "file1.md\nfile2.md\n..."},
  {"role": "assistant", "tool_calls": [{"id": "call_2", "function": {"name": "read_file", "arguments": "{\"path\": \"wiki/git.md\"}"}}]},
  {"role": "tool", "tool_call_id": "call_2", "content": "# Git\n\n..."},
  {"role": "assistant", "content": "According to the wiki..."}
]
```

## System Prompt

The system prompt instructs the LLM to:

- Use `list_files` to discover wiki files
- Use `read_file` to read specific files and find answers
- Include the source file path and section anchor in the final answer
- Think step by step before answering

```
You are a helpful assistant with access to a project wiki.
You have two tools available:
1. list_files - List files in a directory
2. read_file - Read the contents of a file

When asked a question about the project:
- Use list_files to discover files in the wiki directory
- Use read_file to read specific files and find answers
- Always include the source file path and section anchor in your answer
- Format source as: wiki/filename.md#section-anchor

Think step by step. First explore what files exist, then read relevant files to find the answer.
Only give your final answer when you have found the information in the wiki.
```

## Error Handling

| Error Type              | Exit Code | Output                    |
| ----------------------- | --------- | ------------------------- |
| Missing arguments       | 1         | Usage message to stderr   |
| Missing env variables   | 1         | Error message to stderr   |
| HTTP error (4xx/5xx)    | 1         | Status code + response    |
| Request timeout         | 1         | Error message to stderr   |
| Path traversal attempt  | Handled   | Error in tool result      |
| Success                 | 0         | JSON to stdout            |

## Timeout

The agent has a **60-second timeout** for each LLM request. If the LLM takes longer, the request fails with an error.

## Dependencies

- `httpx` — HTTP client for API requests
- `python-dotenv` — Load environment variables from `.env` file
- `pathlib` — Path manipulation (stdlib)
- Python 3.10+

## Testing

Run all tests:

```bash
uv run pytest tests/test_agent.py -v
```

Test categories:
- **Task 1 tests** — Basic JSON output structure
- **Task 2 tests** — Tool calling and source extraction

Example test questions:
- `"How do you resolve a merge conflict?"` — Tests `read_file` tool
- `"What files are in the wiki directory?"` — Tests `list_files` tool

## Security

### Path Security

Tools validate paths to prevent directory traversal:

1. Reject absolute paths (starting with `/`)
2. Reject paths containing `..`
3. Resolve path and verify it's within project root
4. Use `os.path.realpath()` to resolve symlinks

### Environment Variables

- API keys stored in `.env.agent.secret` (gitignored)
- Never hard-code credentials in source code

## Troubleshooting

### "Connection refused"

- Ensure your VM is running and accessible
- Check that the Qwen Code API container is running: `docker ps`
- Verify the IP address and port in `.env.agent.secret`

### "No credentials found"

- The Qwen Code API proxy on your VM needs authentication
- Set `QWEN_API_KEY` in `~/qwen-code-oai-proxy/.env` on your VM
- Or use OpenRouter (no VM authentication needed)

### "Missing environment variables"

- Ensure `.env.agent.secret` exists in the project root
- Check that `LLM_API_KEY`, `LLM_API_BASE`, and `LLM_MODEL` are set

### Agent doesn't find the answer

- The LLM may need better system prompt guidance
- Check if the wiki contains the relevant information
- Verify the LLM is calling tools correctly (check debug output)

### Source field is empty

- The LLM may not format the source reference correctly
- The regex extraction looks for patterns like `wiki/filename.md#section`
- Improve the system prompt to emphasize source citation

## Future Enhancements (Task 3)

- **More tools** — `query_api`, `search_code`, etc.
- **Better source extraction** — Ask LLM to output source in a structured format
- **Conversation memory** — Support multi-turn conversations
- **Tool result summarization** — Handle large file contents more efficiently
