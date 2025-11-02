import boto3
import json
import os
from dotenv import load_dotenv

load_dotenv()

region = os.getenv("AWS_REGION", "us-east-2")
model_id = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-sonnet-20240229-v1:0")

print(f"Testing Bedrock access in region: {region}")
print(f"Model ID: {model_id}")

try:
    client = boto3.client("bedrock-runtime", region_name=region)
    prompt = "Explain FinOps in one sentence."
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 100,
        "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
    }
    response = client.invoke_model(
        modelId=model_id,
        body=json.dumps(body),
    )
    response_body = json.loads(response["body"].read())
    print("\n✅ Bedrock Response:\n")
    print(response_body["content"][0]["text"])

except Exception as e:
    print("\n❌ Bedrock Test Failed:\n", e)
