#!/usr/bin/env python3
"""
CLI agent with tools (read_file, list_files) and agentic loop.

Usage:
    uv run agent.py "Your question here"

Output:
    JSON with "answer", "source", and "tool_calls" fields to stdout.
    All debug output goes to stderr.
"""

import os
import sys
import json
import httpx
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env.agent.secret
load_dotenv('.env.agent.secret')

# Project root for file operations
PROJECT_ROOT = Path(__file__).parent.resolve()

# Maximum tool calls per question
MAX_TOOL_CALLS = 10

# System prompt for Task 2 - instructs LLM to use tools and cite sources
SYSTEM_PROMPT = """You are a helpful assistant with access to a project wiki.
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
"""

# Tool definitions for OpenAI-compatible function calling
TOOLS = [
    {
        "type": "function",
        "function": {
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
    },
    {
        "type": "function",
        "function": {
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
    }
]


def is_safe_path(path: str) -> bool:
    """Check if a path is safe to access (no directory traversal)."""
    # Reject absolute paths
    if path.startswith('/'):
        return False
    # Reject paths with ..
    if '..' in path:
        return False
    # Resolve and verify it's within project root
    try:
        resolved = (PROJECT_ROOT / path).resolve()
        return str(resolved).startswith(str(PROJECT_ROOT))
    except Exception:
        return False


def read_file(path: str) -> str:
    """Read a file from the project repository."""
    if not is_safe_path(path):
        return f"Error: Invalid path '{path}'. Path traversal is not allowed."
    
    file_path = PROJECT_ROOT / path
    if not file_path.exists():
        return f"Error: File '{path}' does not exist."
    if not file_path.is_file():
        return f"Error: '{path}' is not a file."
    
    try:
        return file_path.read_text()
    except Exception as e:
        return f"Error reading file: {e}"


def list_files(path: str) -> str:
    """List files and directories in a directory."""
    if not is_safe_path(path):
        return f"Error: Invalid path '{path}'. Path traversal is not allowed."
    
    dir_path = PROJECT_ROOT / path
    if not dir_path.exists():
        return f"Error: Directory '{path}' does not exist."
    if not dir_path.is_dir():
        return f"Error: '{path}' is not a directory."
    
    try:
        entries = [str(e.name) for e in dir_path.iterdir()]
        entries.sort()
        return '\n'.join(entries)
    except Exception as e:
        return f"Error listing directory: {e}"


def execute_tool(tool_name: str, args: dict) -> str:
    """Execute a tool and return the result."""
    print(f"Executing tool: {tool_name}({args})", file=sys.stderr)
    
    if tool_name == 'read_file':
        return read_file(args.get('path', ''))
    elif tool_name == 'list_files':
        return list_files(args.get('path', ''))
    else:
        return f"Error: Unknown tool '{tool_name}'"


def call_llm(messages: list, api_key: str, api_base: str, model: str, with_tools: bool = True) -> dict:
    """Call the LLM API and return the response."""
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        'model': model,
        'messages': messages,
        'temperature': 0.7
    }
    
    # Add tools if provided
    if with_tools:
        payload['tools'] = TOOLS
    
    response = httpx.post(
        f"{api_base}/chat/completions",
        headers=headers,
        json=payload,
        timeout=60.0
    )
    response.raise_for_status()
    
    return response.json()


def run_agentic_loop(question: str) -> dict:
    """Run the agentic loop: LLM → tool calls → execute → back to LLM."""
    # Get configuration from environment
    api_key = os.getenv('LLM_API_KEY')
    api_base = os.getenv('LLM_API_BASE')
    model = os.getenv('LLM_MODEL')
    
    if not all([api_key, api_base, model]):
        raise ValueError("Missing required environment variables")
    
    # Initialize message history
    messages = [
        {'role': 'system', 'content': SYSTEM_PROMPT},
        {'role': 'user', 'content': question}
    ]
    
    # Track all tool calls for output
    tool_calls_log = []
    tool_call_count = 0
    
    print(f"Starting agentic loop for: {question}", file=sys.stderr)
    
    while tool_call_count < MAX_TOOL_CALLS:
        print(f"--- Iteration {tool_call_count + 1} ---", file=sys.stderr)
        
        # Call LLM
        print("Calling LLM...", file=sys.stderr)
        response = call_llm(messages, api_key, api_base, model)
        
        # Parse response
        assistant_message = response['choices'][0]['message']
        print(f"LLM response: {assistant_message}", file=sys.stderr)
        
        # Add assistant message to history
        messages.append(assistant_message)
        
        # Check for tool calls
        tool_calls = assistant_message.get('tool_calls', [])
        
        if not tool_calls:
            # No tool calls - LLM provided final answer
            print("No tool calls - final answer received", file=sys.stderr)
            answer = assistant_message.get('content', '')
            
            # Extract source from answer (look for wiki/...#... pattern)
            source = ""
            import re
            source_match = re.search(r'(wiki/[\w\-/]+\.md#[\w\-]+)', answer)
            if source_match:
                source = source_match.group(1)
            else:
                # Try to find just the file path
                file_match = re.search(r'(wiki/[\w\-/]+\.md)', answer)
                if file_match:
                    source = file_match.group(1)
            
            return {
                'answer': answer.strip(),
                'source': source,
                'tool_calls': tool_calls_log
            }
        
        # Execute tool calls
        print(f"Executing {len(tool_calls)} tool call(s)...", file=sys.stderr)
        
        for tool_call in tool_calls:
            tool_call_id = tool_call['id']
            function = tool_call['function']
            tool_name = function['name']
            
            # Parse arguments
            try:
                args = json.loads(function['arguments'])
            except json.JSONDecodeError:
                args = {}
            
            # Execute tool
            result = execute_tool(tool_name, args)
            print(f"Tool result: {result[:200]}...", file=sys.stderr)
            
            # Log tool call
            tool_calls_log.append({
                'tool': tool_name,
                'args': args,
                'result': result
            })
            
            # Add tool result to messages
            messages.append({
                'role': 'tool',
                'tool_call_id': tool_call_id,
                'content': result
            })
            
            tool_call_count += 1
    
    # Max tool calls reached
    print("Max tool calls reached", file=sys.stderr)
    return {
        'answer': "I reached the maximum number of tool calls without finding a complete answer.",
        'source': "",
        'tool_calls': tool_calls_log
    }


def main() -> None:
    """Main entry point for the agent CLI."""
    # Parse command line argument
    if len(sys.argv) != 2:
        print("Usage: uv run agent.py \"your question\"", file=sys.stderr)
        sys.exit(1)
    
    question = sys.argv[1]
    print(f"Question: {question}", file=sys.stderr)
    
    try:
        # Run agentic loop
        output = run_agentic_loop(question)
        
        # Output JSON to stdout
        print(json.dumps(output))
        
    except httpx.HTTPStatusError as e:
        print(f"HTTP error: {e.response.status_code}", file=sys.stderr)
        print(f"Response: {e.response.text}", file=sys.stderr)
        sys.exit(1)
    except httpx.RequestError as e:
        print(f"Request error: {e}", file=sys.stderr)
        print("Check that your VM is running and the Qwen Code API is accessible", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
