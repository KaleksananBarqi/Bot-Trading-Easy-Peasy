from openai import OpenAI
import httpx
try:
    print("Testing default OpenAI init...")
    client = OpenAI(api_key="sk-test")
    print("Default init success")
except Exception as e:
    print(f"Default init failed: {e}")

try:
    print("\nTesting Custom http_client init...")
    client = OpenAI(api_key="sk-test", http_client=httpx.Client())
    print("Custom http_client init success")
except Exception as e:
    print(f"Custom http_client init failed: {e}")
