import httpx, asyncio, json
import config
from pipeline.agents import CLASSIFIER_PROMPT, AGENT_PROMPTS

HEADERS = {
    "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
    "Content-Type": "application/json",
}


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(text)


async def _call_vision(client, img_b64: str, system: str, user_text: str, sem) -> dict:
    async with sem:
        payload = {
            "model": config.VISION_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
                    {"type": "text", "text": user_text}
                ]}
            ],
            "max_tokens": 4000,
            "temperature": 0,
        }
        for attempt in range(3):
            try:
                r = await client.post(config.OPENROUTER_BASE, json=payload, headers=HEADERS, timeout=120)
                r.raise_for_status()
                return _parse_json(r.json()["choices"][0]["message"]["content"])
            except Exception as e:
                if attempt == 2:
                    raise
                await asyncio.sleep(2 ** attempt)


async def extract_one(client: httpx.AsyncClient, img: dict, sem: asyncio.Semaphore) -> dict:
    b64 = img["image_b64"]

    # Step 1: Classify
    classification = await _call_vision(client, b64, CLASSIFIER_PROMPT, "Classify this image.", sem)
    img_type = classification.get("image_type", "other")
    if img_type not in AGENT_PROMPTS:
        img_type = "other"

    # Step 2: Extract with specialized agent
    agent_prompt = AGENT_PROMPTS[img_type]
    try:
        data = await _call_vision(client, b64, agent_prompt, "Extract all data from this image.", sem)
    except Exception as e:
        return {"source_file": img["file"], "source_path": img.get("path", ""), "error": str(e)}

    data["image_type"] = img_type
    data["classifier_confidence"] = classification.get("confidence", 0)
    data["source_file"] = img["file"]
    data["source_path"] = img.get("path", "")

    # Normalize: ensure products/contact/key_info exist
    data.setdefault("products", [])
    data.setdefault("contact", {})
    data.setdefault("key_info", [])
    data.setdefault("raw_text", "")
    data.setdefault("company", None)
    data.setdefault("title", "")

    return data


async def extract_batch(images: list, on_progress=None) -> list:
    sem = asyncio.Semaphore(config.MAX_WORKERS)
    results = []
    async with httpx.AsyncClient() as client:
        tasks = [extract_one(client, img, sem) for img in images]
        for i, coro in enumerate(asyncio.as_completed(tasks)):
            result = await coro
            results.append(result)
            if on_progress:
                on_progress(i + 1, len(images), result.get("source_file", ""))
    return sorted(results, key=lambda x: x.get("source_file", ""))
