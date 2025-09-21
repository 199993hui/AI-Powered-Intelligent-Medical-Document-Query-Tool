# services/bedrock_service.py
import os, json, boto3
from botocore.config import Config

# Use on-demand (serverless) Bedrock. No Provisioned Throughput / ModelUnits.
BEDROCK_REGION = os.getenv("BEDROCK_REGION", "us-east-1")  # Nova Pro available in us-east-1
# Try Nova Pro first, fallback to Claude if needed
MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "us.amazon.nova-pro-v1:0")  # Nova Pro inference profile
# Alternative: "anthropic.claude-3-sonnet-20240229-v1:0"

def get_bedrock_client():
    return boto3.client("bedrock-runtime", config=Config(region_name=BEDROCK_REGION))

def build_prompt(question: str, snippets: list[str]) -> str:
    """
    We do manual citations: [1], [2], ... mapped to our retrieved chunks.
    Keep it concise and force the model to ONLY use provided context.
    """
    numbered = "\n\n".join([f"[{i+1}] {s}" for i, s in enumerate(snippets)])
    sys = (
        "You are a clinical document assistant. "
        "Answer ONLY using the provided context snippets. "
        "If the answer is not present, reply exactly: 'Insufficient evidence in the provided documents.' "
        "Write concise, clinician-friendly answers. Include inline citations like [1], [2] "
        "that refer to the numbered context snippets.\n"
    )
    user = f"Question: {question}\n\nContext snippets:\n{numbered}\n\nAnswer:"
    return sys + "\n" + user

def generate_answer(question: str, snippets: list[str], temperature: float = 0.2, max_tokens: int = 600) -> str:
    """
    Calls Nova Pro via bedrock-runtime InvokeModel with a basic text prompt.
    """
    client = get_bedrock_client()
    prompt = build_prompt(question, snippets)

    body = {
        "inputText": prompt,
        "textGenerationConfig": {
            "temperature": temperature,
            "topP": 0.9,
            "maxTokenCount": max_tokens
        }
    }

    resp = client.invoke_model(
        modelId=MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body)
    )
    payload = json.loads(resp["body"].read().decode("utf-8"))
    # Nova returns an array of candidates; pick the first
    out = (payload.get("results") or [{}])[0].get("outputText", "").strip()
    return out or "Insufficient evidence in the provided documents."
