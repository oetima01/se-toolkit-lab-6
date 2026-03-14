"""Regression tests for agent.py CLI.

These tests run agent.py as a subprocess and verify:
1. The output is valid JSON
2. The required fields (answer, tool_calls) are present
3. The answer is a non-empty string
4. tool_calls is an array

Run with: uv run pytest tests/test_agent.py -v
"""

import json
import subprocess
import sys
from pathlib import Path


def get_agent_path() -> Path:
    """Get the path to agent.py in the project root."""
    return Path(__file__).parent.parent / "agent.py"


def run_agent(question: str) -> subprocess.CompletedProcess:
    """Run agent.py with the given question and return the result."""
    agent_path = get_agent_path()
    return subprocess.run(
        [sys.executable, str(agent_path), question],
        capture_output=True,
        text=True,
        timeout=60,
    )


class TestAgentOutput:
    """Test that agent.py produces valid JSON output with required fields."""

    def test_output_is_valid_json(self):
        """Test that stdout contains valid JSON."""
        result = run_agent("What is 2 + 2?")
        
        # Should exit successfully
        assert result.returncode == 0, f"Agent failed: {result.stderr}"
        
        # Should produce valid JSON
        try:
            output = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise AssertionError(f"Output is not valid JSON: {result.stdout}") from e
        
        assert isinstance(output, dict), "Output should be a JSON object"

    def test_output_has_answer_field(self):
        """Test that output contains 'answer' field."""
        result = run_agent("What does API stand for?")
        
        assert result.returncode == 0, f"Agent failed: {result.stderr}"
        output = json.loads(result.stdout)
        
        assert "answer" in output, "Output must contain 'answer' field"

    def test_answer_is_non_empty_string(self):
        """Test that 'answer' is a non-empty string."""
        result = run_agent("What is Python?")
        
        assert result.returncode == 0, f"Agent failed: {result.stderr}"
        output = json.loads(result.stdout)
        
        assert isinstance(output["answer"], str), "'answer' must be a string"
        assert len(output["answer"].strip()) > 0, "'answer' must not be empty"

    def test_output_has_tool_calls_field(self):
        """Test that output contains 'tool_calls' field."""
        result = run_agent("What is 10 + 10?")
        
        assert result.returncode == 0, f"Agent failed: {result.stderr}"
        output = json.loads(result.stdout)
        
        assert "tool_calls" in output, "Output must contain 'tool_calls' field"

    def test_tool_calls_is_array(self):
        """Test that 'tool_calls' is an array."""
        result = run_agent("What is the capital of France?")
        
        assert result.returncode == 0, f"Agent failed: {result.stderr}"
        output = json.loads(result.stdout)
        
        assert isinstance(output["tool_calls"], list), "'tool_calls' must be an array"

    def test_output_has_source_field(self):
        """Test that output contains 'source' field for Task 2."""
        result = run_agent("How do you resolve a merge conflict?")
        
        assert result.returncode == 0, f"Agent failed: {result.stderr}"
        output = json.loads(result.stdout)
        
        assert "source" in output, "Output must contain 'source' field"

    def test_rest_question(self):
        """Test the specific REST question from the task description."""
        result = run_agent("What does REST stand for?")
        
        assert result.returncode == 0, f"Agent failed: {result.stderr}"
        output = json.loads(result.stdout)
        
        # Check structure
        assert "answer" in output
        assert "tool_calls" in output
        assert isinstance(output["answer"], str)
        assert isinstance(output["tool_calls"], list)
        
        # Check answer contains expected terms (case-insensitive)
        answer_lower = output["answer"].lower()
        assert "representational" in answer_lower or "rest" in answer_lower, \
            f"Answer should mention 'Representational' or 'REST': {output['answer']}"


class TestAgentErrors:
    """Test that agent.py handles errors correctly."""

    def test_missing_argument_returns_error(self):
        """Test that running without arguments returns non-zero exit code."""
        agent_path = get_agent_path()
        result = subprocess.run(
            [sys.executable, str(agent_path)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        assert result.returncode != 0, "Should fail without arguments"
        assert "Usage" in result.stderr, "Should show usage message"

    def test_debug_output_goes_to_stderr(self):
        """Test that debug output goes to stderr, not stdout."""
        result = run_agent("What is 2 + 2?")
        
        # stdout should only contain JSON (no debug messages)
        stdout_lines = result.stdout.strip().split("\n")
        assert len(stdout_lines) == 1, "stdout should contain only one line (JSON)"
        
        # Try to parse the single line as JSON
        json.loads(result.stdout)
        
        # stderr may contain debug messages (or be empty)
        # We just verify stdout is clean


class TestTask2DocumentationAgent:
    """Task 2 regression tests for the documentation agent with tools."""

    def test_merge_conflict_question_uses_read_file(self):
        """Test that merge conflict question triggers read_file tool."""
        result = run_agent("How do you resolve a merge conflict?")
        
        assert result.returncode == 0, f"Agent failed: {result.stderr}"
        output = json.loads(result.stdout)
        
        # Should have answer
        assert "answer" in output
        assert isinstance(output["answer"], str)
        assert len(output["answer"].strip()) > 0
        
        # Should have source (may be empty if LLM doesn't format it correctly)
        assert "source" in output
        
        # Should have tool calls
        assert "tool_calls" in output
        assert isinstance(output["tool_calls"], list)
        assert len(output["tool_calls"]) > 0, "Should have at least one tool call"
        
        # Should have used read_file (either directly or after list_files)
        tools_used = [call["tool"] for call in output["tool_calls"]]
        assert "read_file" in tools_used, "Should use read_file tool"
        
        # If source is present, it should reference git wiki
        if output.get("source"):
            assert "git" in output["source"].lower(), f"Source should reference git: {output['source']}"

    def test_wiki_files_question_uses_list_files(self):
        """Test that wiki files question triggers list_files tool."""
        result = run_agent("What files are in the wiki directory?")
        
        assert result.returncode == 0, f"Agent failed: {result.stderr}"
        output = json.loads(result.stdout)
        
        # Should have answer
        assert "answer" in output
        assert isinstance(output["answer"], str)
        assert len(output["answer"].strip()) > 0
        
        # Should have tool calls
        assert "tool_calls" in output
        assert isinstance(output["tool_calls"], list)
        assert len(output["tool_calls"]) > 0, "Should have at least one tool call"
        
        # Should have used list_files
        tools_used = [call["tool"] for call in output["tool_calls"]]
        assert "list_files" in tools_used, "Should use list_files tool"
        
        # The list_files call should have wiki as path
        list_files_calls = [c for c in output["tool_calls"] if c["tool"] == "list_files"]
        assert any(c["args"].get("path") == "wiki" for c in list_files_calls), \
            "list_files should be called with path='wiki'"


class TestTask3SystemAgent:
    """Task 3 regression tests for the system agent with query_api tool."""

    def test_framework_question_uses_read_file(self):
        """Test that framework question triggers read_file tool."""
        result = run_agent("What Python web framework does the backend use?")
        
        assert result.returncode == 0, f"Agent failed: {result.stderr}"
        output = json.loads(result.stdout)
        
        # Should have answer
        assert "answer" in output
        assert isinstance(output["answer"], str)
        assert len(output["answer"].strip()) > 0
        
        # Should have tool calls
        assert "tool_calls" in output
        assert isinstance(output["tool_calls"], list)
        assert len(output["tool_calls"]) > 0, "Should have at least one tool call"
        
        # Should have used read_file on backend code
        tools_used = [call["tool"] for call in output["tool_calls"]]
        assert "read_file" in tools_used, "Should use read_file tool"
        
        # Answer should mention FastAPI
        assert "fastapi" in output["answer"].lower(), \
            f"Answer should mention FastAPI: {output['answer'][:200]}"

    def test_api_query_question_uses_query_api(self):
        """Test that data query question triggers query_api tool."""
        result = run_agent("How many items are in the database? Query the API to find out.")
        
        assert result.returncode == 0, f"Agent failed: {result.stderr}"
        output = json.loads(result.stdout)
        
        # Should have answer
        assert "answer" in output
        assert isinstance(output["answer"], str)
        
        # Should have tool calls
        assert "tool_calls" in output
        assert isinstance(output["tool_calls"], list)
        assert len(output["tool_calls"]) > 0, "Should have at least one tool call"
        
        # Should have used query_api
        tools_used = [call["tool"] for call in output["tool_calls"]]
        assert "query_api" in tools_used, "Should use query_api tool"
        
        # The query_api call should use GET method and /items/ path
        query_api_calls = [c for c in output["tool_calls"] if c["tool"] == "query_api"]
        assert len(query_api_calls) > 0, "Should have at least one query_api call"
        assert any(
            c["args"].get("method") == "GET" and "/items" in c["args"].get("path", "")
            for c in query_api_calls
        ), "query_api should be called with GET /items/"
