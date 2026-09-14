import os
from dotenv import load_dotenv
load_dotenv()

import langfuse
print(f"Langfuse SDK version: {langfuse.__version__}")

from langfuse import Langfuse

lf = Langfuse(
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    host=os.getenv("LANGFUSE_HOST"),
)

print(f"Auth check: {lf.auth_check()}")

# 1. Test trace creation (exactly how chat.py does it)
print("\n--- Test 1: trace() ---")
try:
    trace = lf.trace(
        name="api-verification",
        user_id="u_test123456789abc",
        session_id="s_test12345678",
        input="Who teaches Machine Learning?",
        metadata={
            "role": "Student",
            "email_domain": "dau.ac.in",
            "history_turns": 3,
            "client": "web-chat",
        },
        tags=["web-chat"],
    )
    print(f"  trace() OK - id: {trace.id}")
except Exception as e:
    print(f"  trace() FAILED: {e}")

print("\n--- Test 2: trace.generation() ---")
try:
    generation = trace.generation(
        name="gemini",
        model="gemini-2.5-flash",
        input={
            "system_instruction": "You are a helpful assistant..."[:500],
            "user_message": "Who teaches Machine Learning?"[:500],
            "history_turns": 3,
        },
        metadata={"temperature": 0.3, "max_output_tokens": 4000},
    )
    print(f"  generation() OK - id: {generation.id}")
except Exception as e:
    print(f"  generation() FAILED: {e}")

print("\n--- Test 3: generation.span() (tool call) ---")
try:
    tool_span = generation.span(
        name="tool:search_faculty",
        input={"name": "search_faculty", "args": {"query": "Machine Learning"}},
    )
    print(f"  span() OK - id: {tool_span.id}")
except Exception as e:
    print(f"  span() FAILED: {e}")

print("\n--- Test 4: span.end(output=...) ---")
try:
    tool_span.end(output={"result": '{"name": "Dr. Smith", "department": "CS"}'[:2000]})
    print("  span.end() OK")
except Exception as e:
    print(f"  span.end() FAILED: {e}")

# 5. Test generation.end() with usage dict (the exact format our code uses)
print("\n--- Test 5: generation.end(output=..., usage=...) ---")
try:
    generation.end(
        output="Dr. Smith teaches Machine Learning in the CS department.",
        usage={
            "input": 150,
            "output": 45,
            "total": 195,
            "unit": "TOKENS",
        },
    )
    print("  generation.end() OK")
except Exception as e:
    print(f"  generation.end() FAILED: {e}")

# 6. Test generation.end() with status_message (used in error/exhaustion paths)
print("\n--- Test 6: generation.end(status_message=...) ---")
try:
    gen2 = trace.generation(name="gemini-error-test", model="gemini-2.5-flash")
    gen2.end(
        output="Error occurred",
        status_message="error",
        metadata={"error": "test error"},
    )
    print("  generation.end(status_message) OK")
except Exception as e:
    print(f"  generation.end(status_message) FAILED: {e}")

# 7. Test trace.update() (used in chat.py after getting response)
print("\n--- Test 7: trace.update() ---")
try:
    trace.update(
        output="Dr. Smith teaches Machine Learning in the CS department.",
        tags=["web-chat", "gemini"],
    )
    print("  trace.update() OK")
except Exception as e:
    print(f"  trace.update() FAILED: {e}")

# 8. Test trace.update() with timed_out metadata (timeout path)
print("\n--- Test 8: trace.update(metadata={timed_out}) ---")
try:
    trace2 = lf.trace(name="timeout-test", input="test")
    trace2.update(
        output="Timed out",
        metadata={"timed_out": True},
        tags=["web-chat", "timeout"],
    )
    print("  trace.update(timeout) OK")
except Exception as e:
    print(f"  trace.update(timeout) FAILED: {e}")

# 9. Test fallback span on trace (used in chat.py for NLP fallback)
print("\n--- Test 9: trace.span() (fallback) ---")
try:
    fb_span = trace.span(
        name="local-nlp-fallback",
        input="What is the timetable?",
    )
    fb_span.end(output="Here is the timetable..."[:500])
    print("  fallback span OK")
except Exception as e:
    print(f"  fallback span FAILED: {e}")

# 10. Flush and verify
print("\n--- Test 10: flush() ---")
try:
    lf.flush()
    print("  flush() OK")
except Exception as e:
    print(f"  flush() FAILED: {e}")

print("\n=== ALL TESTS COMPLETE ===")
print("Check http://localhost:3000 -> Traces for 'api-verification' and 'timeout-test' traces")
