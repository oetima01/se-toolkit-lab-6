# Task 1: Call an LLM from Code - Implementation Plan

## LLM Provider Choice
- Provider: Qwen Code API (on VM)
- Model: qwen3-coder-plus
- Rationale: Free (1000 requests/day), reliable, good for Russia

## Implementation Approach
1. Load configuration from `.env.agent.secret`
2. Parse command-line argument (question)
3. Make HTTP request to OpenAI-compatible API
4. Parse response and extract answer
5. Output JSON with required fields
6. All debug output to stderr

## File Structure
- `agent.py` - main CLI application
- `.env.agent.secret` - configuration (not committed)
- `AGENT.md` - documentation

## Testing Strategy
- One regression test using subprocess
- Test with sample question
- Validate JSON output structure