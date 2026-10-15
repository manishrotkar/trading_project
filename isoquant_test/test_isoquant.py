import os
from openai import OpenAI


api_key = os.getenv("ISOQUANT_API_KEY")

if not api_key:
    raise RuntimeError("ISOQUANT_API_KEY is not loaded.")


client = OpenAI(
    api_key=api_key,
    base_url="https://api.isoquant.ai/v1"
)


response = client.chat.completions.create(
    model="glm-5.3-flash",
    messages=[
        {
            "role": "user",
            "content": "Explain what a stock market index is in simple English."
        }
    ],
    max_tokens=500,
    extra_headers={
        "Isoquant-ZDR": "required"
    }
)


print("REQUEST COMPLETED")

print("MESSAGE:")
print(response.choices[0].message)

print("CONTENT:")
print(repr(response.choices[0].message.content))

print("FINISH REASON:")
print(response.choices[0].finish_reason)

print("USAGE:")
print(response.usage)
