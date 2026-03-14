# Task 2: The Documentation Agent - Implementation Plan

## Overview

Extend the Task 1 agent with two tools (`read_file`, `list_files`) and an agentic loop that allows the LLM to iteratively query the project wiki before answering.

## Tool Definitions

### `read_file`

**Purpose:** Read contents of a file from the project repository.

**Schema (OpenAI function calling format):**
```json
{
  "name": "read_file",
  "description": "Read a file from the project repository",
  "parameters": {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "Relative path from project root (e.g., 'wiki/git.md')"
      }
    },
    "required": ["path"]
  }
}
```

**Implementation:**
- Use Python's `pathlib.Path` to resolve the path
- Security: Reject paths containing `..` or absolute paths
- Return file contents as string, or error message if file doesn't exist

### `list_files`

**Purpose:** List files and directories at a given path.

**Schema:**
```json
{
  "name": "list_files",
  "description": "List files and directories in a directory",
  "parameters": {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "Relative directory path from project root (e.g., 'wiki')"
      }
    },
    "required": ["path"]
  }
}
```

**Implementation:**
- Use `os.listdir()` or `pathlib.Path.iterdir()`
- Security: Reject paths containing `..` or absolute paths
- Return newline-separated listing

## Agentic Loop

```
1. Build initial messages: [system_prompt, user_question] + tool_definitions
2. Send to LLM
3. Parse response:
   - If tool_calls present:
     a. Execute each tool
     b. Append tool results as "tool" role messages
     c. Go to step 2
   - If no tool_calls (final answer):
     a. Extract answer and source from response
     b. Output JSON and exit
4. Max 10 tool calls per question (safety limit)
```

**Message format for tool calls (OpenAI-compatible):**
```json
{
  "role": "assistant",
  "content": null,
  "tool_calls": [
    {
      "id": "call_1",
      "type": "function",
      "function": {
        "name": "read_file",
        "arguments": "{\"path\": \"wiki/git.md\"}"
      }
    }
  ]
}
```

**Tool result message format:**
```json
{
  "role": "tool",
  "tool_call_id": "call_1",
  "content": "file contents here"
}
```

## System Prompt Strategy

The system prompt should instruct the LLM to:
1. Use `list_files` to discover wiki files when unsure where to look
2. Use `read_file` to read relevant files
3. Include the source reference (file path + section anchor) in the final answer
4. Only call tools when needed; give final answer when confident

Example system prompt:
```
You are a helpful assistant with access to a project wiki.
Use list_files to discover files in the wiki directory.
Use read_file to read specific files and find answers.
Always include the source file path and section anchor in your answer.
Example source format: wiki/git-workflow.md#resolving-merge-conflicts
```

## Path Security

**Validation rules:**
1. Reject paths starting with `/` (absolute paths)
2. Reject paths containing `..` (directory traversal)
3. Resolve path and verify it's within project root
4. Use `os.path.realpath()` to resolve symlinks and check boundaries

**Implementation:**
```python
def is_safe_path(path: str) -> bool:
    if path.startswith('/') or '..' in path:
        return False
    resolved = (PROJECT_ROOT / path).resolve()
    return str(resolved).startswith(str(PROJECT_ROOT))
```

## Output Format

```json
{
  "answer": "The final answer text",
  "source": "wiki/git-workflow.md#resolving-merge-conflicts",
  "tool_calls": [
    {
      "tool": "list_files",
      "args": {"path": "wiki"},
      "result": "git-workflow.md\n..."
    },
    {
      "tool": "read_file",
      "args": {"path": "wiki/git-workflow.md"},
      "result": "file contents..."
    }
  ]
}
```

## Testing Strategy

**Test 1:** Question about merge conflicts
- Input: `"How do you resolve a merge conflict?"`
- Expected: `read_file` in tool_calls, `wiki/git-workflow.md` in source

**Test 2:** Question about wiki structure
- Input: `"What files are in the wiki?"`
- Expected: `list_files` in tool_calls

## Dependencies

- No new dependencies needed (using stdlib `pathlib`, `os`)
- LLM must support function calling (OpenAI-compatible API)

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Infinite loop | Max 10 tool calls limit |
| Path traversal | Validate paths before reading |
| LLM doesn't call tools | Improve system prompt |
| Source extraction fails | Ask LLM to include source in a specific format |
