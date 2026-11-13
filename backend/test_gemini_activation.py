"""Safe opt-in check for the Member 4 Gemini integration.

Run from any directory with the backend interpreter:
    python backend/test_gemini_activation.py

The script never prints the API key or SDK exception message. Live requests are
made only when a non-placeholder key is configured.
"""

import os
import sys
import logging
from unittest.mock import patch

from gemini_copilot import GEMINI_MODEL, SortingRule, extract_rule_from_multimodal


def main() -> int:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    configured = bool(key and key != "your_gemini_key_here" and len(key) >= 15)
    print(f"GEMINI_API_KEY configured: {configured}")

    try:
        from google import genai
        from google.genai import types
        from importlib.metadata import version

        print(f"google-genai version: {version('google-genai')}")
        supported = hasattr(genai, "Client") and "response_schema" in types.GenerateContentConfig.__annotations__
        print(f"SDK structured response support: {supported}")
        if not supported:
            return 2
    except Exception as exc:
        print(f"SDK check failed: {type(exc).__name__}")
        return 2

    print(f"Configured model: {GEMINI_MODEL}")

    # Exercise the sanitized exception path without making a request or using a
    # real credential. The sentinel must never appear in captured log output.
    if configured:
        print("Error path check skipped while a live credential is configured.")
    else:
        class Capture(logging.Handler):
            def __init__(self):
                super().__init__()
                self.messages = []

            def emit(self, record):
                self.messages.append(self.format(record))

        capture = Capture()
        logger = logging.getLogger("gemini_copilot")
        logger.addHandler(capture)
        try:
            with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key-value-long-enough"}), \
                    patch("google.genai.Client", side_effect=RuntimeError("SECRET_SENTINEL")):
                error_rule = extract_rule_from_multimodal(text_instruction="Reject yellow bricks with black side stripes")
        except Exception as exc:
            print(f"Simulated error path failed: {type(exc).__name__}")
            return 1
        finally:
            logger.removeHandler(capture)
        safe_error = not any("SECRET_SENTINEL" in line for line in capture.messages)
        print(f"Simulated API error falls back to valid SortingRule: {isinstance(error_rule, SortingRule)}")
        print(f"Simulated API error log is sanitized: {safe_error}")
        if not isinstance(error_rule, SortingRule) or not safe_error:
            return 1

    if not configured:
        rule = extract_rule_from_multimodal(text_instruction="Reject yellow bricks with black side stripes")
        print(f"Offline fallback produces valid SortingRule: {isinstance(rule, SortingRule)}")
        print(f"Fallback rule: {rule.rule_id}; {rule.target_brick_color}; {rule.action_on_match}")
        print("Live Gemini check skipped: no usable credential is configured.")
        return 0 if isinstance(rule, SortingRule) else 1

    try:
        rule = extract_rule_from_multimodal(text_instruction="Reject yellow bricks with black side stripes")
        # The integration intentionally falls back on API errors. Recognize that
        # outcome so a successful heuristic response is not reported as live.
        if rule.reasoning.startswith("Generated from operator multimodal prompt:"):
            print("Live Gemini call failed; integration returned its offline fallback.")
            return 1
        print(f"Live response is valid SortingRule: {isinstance(rule, SortingRule)}")
        print(f"Rule: {rule.rule_id}; {rule.target_brick_color}; {rule.action_on_match}")
        return 0 if isinstance(rule, SortingRule) else 1
    except Exception as exc:
        print(f"Live Gemini check failed: {type(exc).__name__}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
