#!/usr/bin/env python3
"""
CLI agent with tools (read_file, list_files, query_api) and agentic loop.

Usage:
    uv run agent.py "Your question here"

Output:
    JSON with "answer", "source" (optional), and "tool_calls" fields to stdout.
    All debug output goes to stderr.
"""

import os
import sys
import json
import httpx
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from both .env.agent.secret and .env.docker.secret
load_dotenv('.env.agent.secret')
load_dotenv('.env.docker.secret', override=False)  # Don't override LLM settings

# Project root for file operations
PROJECT_ROOT = Path(__file__).parent.resolve()

# Maximum tool calls per question
MAX_TOOL_CALLS = 10

# System prompt for Task 3 - guides tool selection
SYSTEM_PROMPT = """You are a helpful assistant that answers questions using a project wiki, source code, and a live backend API.

You have three tools available:
1. list_files - List files in a directory
2. read_file - Read the contents of a file  
3. query_api - Call the backend API to query data

CRITICAL RULES - FOLLOW THESE EXACTLY:
1. NEVER say "let me read", "let me check", "I'll examine" - just READ the file and give the answer
2. After using tools 2-3 times, STOP and give your FINAL ANSWER
3. Your final answer must be COMPLETE - list ALL items, ALL steps, ALL details
4. NEVER leave the answer incomplete
5. For wiki questions: cite the file as "wiki/filename.md" in your answer

TOOL SELECTION:
- Wiki questions: Use list_files on wiki/, then read relevant files
- Router questions: Use list_files on backend/app/routers/, read ALL router files, then list them all with their domains
- API questions: Use query_api to get data, count results, give exact number
- Bug questions: FIRST use query_api to reproduce the error, THEN use read_file to find the bug in source code
  - When reading code for bugs, look for: 
    (1) division operations where divisor could be 0 (e.g., `x / total_learners` without checking if total_learners > 0)
    (2) sorting on nullable fields from SQL aggregations (e.g., `sorted(rows, key=lambda r: r.avg_score)` where avg_score from func.avg() could be None)
- Auth questions: Use query_api with no_auth=true to test what happens without authentication

ANSWER FORMAT:
- For lists: enumerate ALL items (e.g., "1. analytics - handles analytics endpoints...")
- For counts: give exact number (e.g., "There are 42 items")
- For wiki: cite source (e.g., "Source: wiki/github.md")
- For bugs: name the issue and file (e.g., "Division by zero in backend/app/routers/analytics.py")

EXAMPLE - Router question:
"After examining the backend routers, here are all API router modules:
1. analytics.py - handles analytics endpoints like /analytics/scores, /analytics/completion-rate
2. interactions.py - handles interaction logging
3. items.py - handles item CRUD operations
4. learners.py - handles learner management  
5. pipeline.py - handles ETL pipeline sync
Source: backend/app/routers/"

NOW ANSWER THE QUESTION. Be complete. Stop after 2-3 tool calls and give your final answer.
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
                        "description": "Relative path from project root (e.g., 'wiki/git.md', 'backend/app/main.py')"
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
                        "description": "Relative directory path from project root (e.g., 'wiki', 'backend/app')"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_api",
            "description": "Call the backend API to query data, test endpoints, or check API behavior. Use for live data queries, item counts, scores, or reproducing errors.",
            "parameters": {
                "type": "object",
                "properties": {
                    "method": {
                        "type": "string",
                        "description": "HTTP method (GET, POST, PUT, DELETE, PATCH)",
                        "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"]
                    },
                    "path": {
                        "type": "string",
                        "description": "API path starting with / (e.g., '/items/', '/analytics/completion-rate?lab=lab-01')"
                    },
                    "body": {
                        "type": "string",
                        "description": "Optional JSON request body for POST/PUT/PATCH requests"
                    },
                    "no_auth": {
                        "type": "boolean",
                        "description": "If true, omit the Authorization header (use for testing auth errors). Default: false"
                    }
                },
                "required": ["method", "path"]
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


def query_api(method: str, path: str, body: str = None, no_auth: bool = False) -> str:
    """Call the backend API with authentication."""
    # Get configuration from environment
    lms_api_key = os.getenv('LMS_API_KEY')
    agent_api_base_url = os.getenv('AGENT_API_BASE_URL', 'http://localhost:42002')

    # Build URL
    url = f"{agent_api_base_url.rstrip('/')}{path}"

    # Prepare headers - only add auth if no_auth is False
    headers = {
        'Content-Type': 'application/json'
    }
    if not no_auth and lms_api_key:
        headers['Authorization'] = f'Bearer {lms_api_key}'
    elif not lms_api_key and not no_auth:
        return "Error: LMS_API_KEY not configured in environment."

    print(f"Calling API: {method} {url} (auth={not no_auth})", file=sys.stderr)

    try:
        # Make request
        if method in ['GET', 'DELETE']:
            response = httpx.get(url, headers=headers, timeout=30.0)
        elif method in ['POST', 'PUT', 'PATCH']:
            data = json.loads(body) if body else None
            response = httpx.request(method, url, headers=headers, json=data, timeout=30.0)
        else:
            return f"Error: Unsupported method '{method}'"

        # Build response
        result = {
            'status_code': response.status_code,
            'body': response.text[:5000]  # Truncate large responses
        }

        return json.dumps(result)

    except httpx.HTTPStatusError as e:
        return json.dumps({
            'status_code': e.response.status_code,
            'body': e.response.text[:1000]
        })
    except httpx.RequestError as e:
        return f"Error: Request failed - {str(e)}"
    except json.JSONDecodeError as e:
        return f"Error: Invalid JSON body - {str(e)}"
    except Exception as e:
        return f"Error: {str(e)}"


def execute_tool(tool_name: str, args: dict) -> str:
    """Execute a tool and return the result."""
    print(f"Executing tool: {tool_name}({args})", file=sys.stderr)

    if tool_name == 'read_file':
        return read_file(args.get('path', ''))
    elif tool_name == 'list_files':
        return list_files(args.get('path', ''))
    elif tool_name == 'query_api':
        return query_api(
            args.get('method', 'GET'),
            args.get('path', ''),
            args.get('body'),
            args.get('no_auth', False)
        )
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


def extract_source_from_answer(answer: str) -> str:
    """Extract source reference from the answer text."""
    import re

    # Look for wiki/...#... pattern
    source_match = re.search(r'(wiki/[\w\-/]+\.md#[\w\-]+)', answer)
    if source_match:
        return source_match.group(1)

    # Try to find just the file path
    file_match = re.search(r'(wiki/[\w\-/]+\.md)', answer)
    if file_match:
        return file_match.group(1)

    # Look for backend source files
    backend_match = re.search(r'(backend/[\w\-/]+\.(py|md))', answer)
    if backend_match:
        return backend_match.group(1)

    # Look for API endpoint references
    api_match = re.search(r'API:\s*(GET|POST|PUT|DELETE|PATCH)\s+(/[^\s]+)', answer)
    if api_match:
        return f"{api_match.group(2)}"

    # Look for Source: pattern
    source_pattern = re.search(r'Source:\s*(wiki/[\w\-/]+\.md|backend/[\w\-/]+\.(py|md))', answer, re.IGNORECASE)
    if source_pattern:
        return source_pattern.group(1)

    # Look for "in the <file>" pattern
    in_file_match = re.search(r'in the\s+(wiki/[\w\-/]+\.md|backend/[\w\-/]+\.(py|md))', answer, re.IGNORECASE)
    if in_file_match:
        return in_file_match.group(1)

    # Look for common wiki file references
    wiki_patterns = [
        (r'github\.md|git\.md|git-workflow\.md', 'wiki/github.md'),
        (r'docker\.md|docker-compose\.md', 'wiki/docker.md'),
        (r'ssh\.md|vm\.md', 'wiki/ssh.md'),
    ]
    for pattern, source in wiki_patterns:
        if re.search(pattern, answer, re.IGNORECASE):
            return source

    return ""


def run_agentic_loop(question: str) -> dict:
    """Run the agentic loop: LLM → tool calls → execute → back to LLM."""
    # Get configuration from environment
    api_key = os.getenv('LLM_API_KEY')
    api_base = os.getenv('LLM_API_BASE')
    model = os.getenv('LLM_MODEL')
    
    if not all([api_key, api_base, model]):
        raise ValueError("Missing required LLM environment variables")
    
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
            answer = assistant_message.get('content') or ""
            
            # Extract source from answer
            source = extract_source_from_answer(answer)
            
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
