from __future__ import annotations
import json
import re
import time
from pathlib import Path
from typing import Iterable, TypeVar, Type
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel
from .schemas import QAExample, RunRecord

load_dotenv()
client = OpenAI()

T = TypeVar("T", bound=BaseModel)

def normalize_answer(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text

def load_dataset(path: str | Path) -> list[QAExample]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return [QAExample.model_validate(item) for item in raw]

def save_jsonl(path: str | Path, records: Iterable[RunRecord]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(record.model_dump_json() + "\n")

def call_openai_text(system_prompt: str, user_prompt: str, temperature: float = 0.0) -> tuple[str, int, int]:
    """Gọi OpenAI trả về Text bình thường. Return: (content_string, tokens, latency_ms)"""
    start_time = time.time()
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=temperature
    )
    latency_ms = int((time.time() - start_time) * 1000)
    tokens = response.usage.total_tokens if response.usage else 0
    return response.choices[0].message.content or "", tokens, latency_ms

def call_openai_json(system_prompt: str, user_prompt: str, response_format: Type[T], temperature: float = 0.0) -> tuple[T, int, int]:
    """Gọi OpenAI ép trả về JSON theo Pydantic schema. Return: (Pydantic_Object, tokens, latency_ms)"""
    start_time = time.time()
    response = client.beta.chat.completions.parse(
        model="gpt-4.1-nano",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        response_format=response_format,
        temperature=temperature
    )
    latency_ms = int((time.time() - start_time) * 1000)
    tokens = response.usage.total_tokens if response.usage else 0
    
    parsed_obj = response.choices[0].message.parsed
    if parsed_obj is None:
        raise ValueError("Failed to parse JSON response from OpenAI")
        
    return parsed_obj, tokens, latency_ms
