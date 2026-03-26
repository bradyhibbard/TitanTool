import base64
import json
import re
from pathlib import Path


def encode_image_to_base64(img_path: Path) -> str:
    with open(img_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def extract_json(text: str) -> dict:
    text = text.strip()
    text = re.sub(r"^```json\s*", "", text)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group(0))

    raise ValueError(f"Could not parse JSON from model output:\n{text}")


def ask_model_for_json(client, image_path: Path, prompt: str, model: str):
    b64 = encode_image_to_base64(image_path)

    response = client.responses.create(
        model=model,
        input=[{
            "role": "user",
            "content": [
                {"type": "input_text", "text": prompt},
                {
                    "type": "input_image",
                    "image_url": f"data:image/png;base64,{b64}",
                    "detail": "high"
                }
            ]
        }]
    )

    raw = response.output_text.strip()
    print("\n--- MODEL RAW OUTPUT ---")
    print(raw)
    print("--- END OUTPUT ---\n")

    return extract_json(raw)