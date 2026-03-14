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

    def test_tool_calls_is_empty_for_task_1(self):
        """Test that 'tool_calls' is empty for Task 1 (no tools yet)."""
        result = run_agent("What does REST stand for?")
        
        assert result.returncode == 0, f"Agent failed: {result.stderr}"
        output = json.loads(result.stdout)
        
        assert output["tool_calls"] == [], "'tool_calls' should be empty for Task 1"

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
