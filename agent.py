#!/usr/bin/env python3
"""
CLI agent that calls an LLM and returns structured JSON response.

Usage:
    uv run agent.py "Your question here"

Output:
    JSON with "answer" and "tool_calls" fields to stdout.
    All debug output goes to stderr.
"""

import os
import sys
import json
import httpx
from dotenv import load_dotenv

# Load environment variables from .env.agent.secret
load_dotenv('.env.agent.secret')

# System prompt for Task 1 - minimal, will expand in Tasks 2-3
SYSTEM_PROMPT = (
    "You are a helpful assistant that answers questions concisely and accurately. "
    "Provide direct, factual answers without unnecessary elaboration."
)


def main() -> None:
    """Main entry point for the agent CLI."""
    # Parse command line argument
    if len(sys.argv) != 2:
        print("Usage: uv run agent.py \"your question\"", file=sys.stderr)
        sys.exit(1)

    question = sys.argv[1]
    print(f"Question: {question}", file=sys.stderr)

    # Get configuration from environment
    api_key = os.getenv('LLM_API_KEY')
    api_base = os.getenv('LLM_API_BASE')
    model = os.getenv('LLM_MODEL')

    if not all([api_key, api_base, model]):
        print("Error: Missing required environment variables (LLM_API_KEY, LLM_API_BASE, LLM_MODEL)", file=sys.stderr)
        print("Check .env.agent.secret file", file=sys.stderr)
        sys.exit(1)

    # Prepare API request
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }

    payload = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user', 'content': question}
        ],
        'temperature': 0.7
    }

    try:
        # Send request to LLM
        print(f"Sending request to {api_base}", file=sys.stderr)
        response = httpx.post(
            f"{api_base}/chat/completions",
            headers=headers,
            json=payload,
            timeout=60.0
        )
        response.raise_for_status()

        # Parse response
        result = response.json()
        answer = result['choices'][0]['message']['content']

        # Output JSON to stdout
        output = {
            'answer': answer.strip(),
            'tool_calls': []
        }
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
