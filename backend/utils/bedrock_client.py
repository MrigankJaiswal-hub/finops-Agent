# backend/utils/bedrock_client.py
# AI (Bedrock) interaction logic with conditional JSON mode + safe fallbacks.

import os
import json
import logging
from typing import Tuple, Optional

import boto3
from botocore.exceptions import ClientError, UnknownServiceError, NoRegionError

logger = logging.getLogger("bedrock-client")

MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-sonnet-20240229-v1:0")
REGION = (
    os.getenv("BEDROCK_REGION")
    or os.getenv("AWS_REGION")
    or os.getenv("AWS_DEFAULT_REGION")
    or "us-east-1"
)
AWS_PROFILE = os.getenv("AWS_PROFILE")


def _bedrock_client():
    """
    Create a Bedrock Runtime client honoring AWS_PROFILE (SSO) if set.
    """
    if AWS_PROFILE:
        logger.info("Attempting AWS profile: %s", AWS_PROFILE)
        session = boto3.Session(profile_name=AWS_PROFILE, region_name=REGION)
    else:
        session = boto3.Session(region_name=REGION)
    # Will raise UnknownServiceError if botocore is too old or region not supported
    return session.client("bedrock-runtime")


def _supports_json_mode(model_id: str) -> bool:
    """
    Claude JSON mode (response_format) is available on newer Anthropic models on Bedrock
    (e.g., Claude 3.5 family). Claude 3 Sonnet 20240229 generally rejects response_format.
    """
    m = model_id.lower()
    return ("claude-3-5" in m) or ("sonnet-20241022" in m) or ("haiku-20241022" in m)


def _build_messages_body(prompt: str, max_tokens: int, use_json_mode: bool) -> dict:
    """
    Build Anthropic Messages request body for Bedrock. JSON mode is gated by model support.
    """
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": int(max_tokens),
        "messages": [
            {
                "role": "user",
                "content": [{"type": "text", "text": prompt}],
            }
        ],
        "system": (
            "You are FinOps+ assistant. You MUST return a single valid JSON object when asked. "
            "Do not include markdown, code fences, or commentary."
        ),
        "temperature": 0.2,
    }
    if use_json_mode and _supports_json_mode(MODEL_ID):
        body["response_format"] = {"type": "json_object"}
    return body


def _parse_bedrock_response(resp) -> str:
    """
    Extract concatenated text from the Claude Messages response.
    Handles both payload['content'] and payload['output']['content'] variations.
    """
    # Body can be streaming wrapper or plain bytes; standardize to JSON first
    raw = resp["body"]
    if hasattr(raw, "read"):
        raw = raw.read()
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    payload = json.loads(raw)

    blocks = payload.get("content")
    if isinstance(blocks, list):
        for blk in blocks:
            if blk.get("type") == "text":
                return blk.get("text", "").strip()

    out = payload.get("output", {}) if isinstance(payload.get("output"), dict) else {}
    blocks2 = out.get("content", [])
    if isinstance(blocks2, list):
        for blk in blocks2:
            if blk.get("type") == "text":
                return blk.get("text", "").strip()

    return json.dumps(payload)


def get_ai_recommendation(
    prompt: str,
    max_tokens: int = 600,
    json_mode: bool = False,
) -> Tuple[str, str]:
    """
    Calls Anthropic Messages API via Bedrock.
    Returns (text, source_tag).
    If json_mode=True and the model rejects 'response_format', we retry without JSON mode.
    """
    try:
        client = _bedrock_client()
    except (UnknownServiceError, NoRegionError) as e:
        # Graceful signal to caller to fallback to rules
        logger.error("Bedrock unavailable: %s", e)
        raise

    logger.info(
        "[bedrock] provider=bedrock region=%s model=%s profile=%s",
        REGION,
        MODEL_ID,
        AWS_PROFILE or "env/default",
    )

    def _invoke(use_json: bool) -> Tuple[str, str]:
        body = _build_messages_body(prompt, max_tokens, use_json)
        # Bedrock expects bytes for body
        resp = client.invoke_model(
            modelId=MODEL_ID,
            body=json.dumps(body).encode("utf-8"),
            contentType="application/json",
            accept="application/json",
        )
        txt = _parse_bedrock_response(resp)
        return txt, ("bedrock-json" if use_json else "bedrock")

    try:
        # First attempt (possibly JSON mode)
        return _invoke(json_mode)
    except ClientError as e:
        msg = str(e)
        if "response_format" in msg or "Extra inputs are not permitted" in msg:
            logger.warning("Bedrock rejected response_format; retrying without JSON mode.")
            return _invoke(False)
        raise


def get_ai_json(prompt: str, max_tokens: int = 600, retries: int = 1):
  """
  Attempts to obtain JSON. If Bedrock is unavailable or output isn't JSON,
  return a safe value so the app can fallback to rule-based actions without 500s.
  Returns (parsed_dict_or_None, source_tag).
  """

  def _try(use_json_mode: bool):
      out, src = get_ai_recommendation(
          prompt, max_tokens=max_tokens, json_mode=use_json_mode
      )
      try:
          js = json.loads(out)
          return js, src
      except Exception:
          return {"_raw": out}, src

  try:
      js, src = _try(True)
      if isinstance(js, dict) and ("actions" in js or "_raw" not in js):
          return js, src
      return _try(False)
  except (UnknownServiceError, NoRegionError):
      logger.error("Bedrock client not available in this environment; falling back.")
      return None, "bedrock-unavailable"
  except Exception:
      if retries > 0:
          logger.exception("get_ai_json failed once; retrying without JSON mode.")
          try:
              return _try(False)
          except Exception:
              logger.exception("Second attempt failed.")
              return None, "bedrock-error"
      logger.exception("get_ai_json fatal.")
      return None, "bedrock-error"
