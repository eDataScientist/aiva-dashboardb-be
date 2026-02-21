#!/usr/bin/env python3
"""Generate schema-aligned conversation grades using OpenRouter via OpenAI SDK.

Input format expected from `conversations_by_phone_by_day.json`:
{
  "<phone_number>": {
    "<YYYY-MM-DD>": [
      {"sender": "customer|agent", "message": "..."},
      ...
    ]
  }
}
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import random
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from openai import AsyncOpenAI
except ImportError as exc:  # pragma: no cover - runtime dependency guard
    raise SystemExit(
        "Missing dependency: openai. Install with `pip install openai`."
    ) from exc

try:
    from tqdm.asyncio import tqdm_asyncio
except ImportError:  # pragma: no cover - optional dependency
    tqdm_asyncio = None


SCHEMA_COLUMNS: list[str] = [
    "id",
    "phone_number",
    "grade_date",
    "created_at",
    "relevancy_score",
    "relevancy_reasoning",
    "accuracy_score",
    "accuracy_reasoning",
    "completeness_score",
    "completeness_reasoning",
    "clarity_score",
    "clarity_reasoning",
    "tone_score",
    "tone_reasoning",
    "resolution",
    "resolution_reasoning",
    "repetition_score",
    "repetition_reasoning",
    "loop_detected",
    "loop_detected_reasoning",
    "satisfaction_score",
    "satisfaction_reasoning",
    "frustration_score",
    "frustration_reasoning",
    "user_relevancy",
    "user_relevancy_reasoning",
    "escalation_occurred",
    "escalation_occurred_reasoning",
    "escalation_type",
    "escalation_type_reasoning",
    "intent_label",
    "intent_reasoning",
]

SCORE_FIELDS: set[str] = {
    "relevancy_score",
    "accuracy_score",
    "completeness_score",
    "clarity_score",
    "tone_score",
    "repetition_score",
    "satisfaction_score",
    "frustration_score",
}

BOOL_FIELDS: set[str] = {
    "resolution",
    "loop_detected",
    "user_relevancy",
    "escalation_occurred",
}

ENUM_FIELDS: dict[str, set[str]] = {
    "escalation_type": {"Natural", "Failure", "None"},
}

PROMPT_ORDER: list[str] = [
    "ai_performance",
    "conversation_health",
    "user_signals",
    "escalation",
    "intent",
]


@dataclass(frozen=True)
class PromptSpec:
    template_file: str
    output_fields: tuple[str, ...]
    include_system_prompt: bool = False


PROMPT_SPECS: dict[str, PromptSpec] = {
    "ai_performance": PromptSpec(
        template_file="ai_performance_judge.md",
        output_fields=(
            "relevancy_score",
            "relevancy_reasoning",
            "accuracy_score",
            "accuracy_reasoning",
            "completeness_score",
            "completeness_reasoning",
            "clarity_score",
            "clarity_reasoning",
            "tone_score",
            "tone_reasoning",
        ),
        include_system_prompt=True,
    ),
    "conversation_health": PromptSpec(
        template_file="conversation_health.md",
        output_fields=(
            "resolution",
            "resolution_reasoning",
            "repetition_score",
            "repetition_reasoning",
            "loop_detected",
            "loop_detected_reasoning",
        ),
    ),
    "user_signals": PromptSpec(
        template_file="user-signals.md",
        output_fields=(
            "satisfaction_score",
            "satisfaction_reasoning",
            "frustration_score",
            "frustration_reasoning",
            "user_relevancy",
            "user_relevancy_reasoning",
        ),
    ),
    "escalation": PromptSpec(
        template_file="escalation.md",
        output_fields=(
            "escalation_occurred",
            "escalation_occurred_reasoning",
            "escalation_type",
            "escalation_type_reasoning",
        ),
        include_system_prompt=True,
    ),
    "intent": PromptSpec(
        template_file="intent.md",
        output_fields=("intent_label", "intent_reasoning"),
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run 5 AI judge prompts per daily conversation and emit a schema-aligned table."
        )
    )
    parser.add_argument(
        "--input-json",
        default="conversations_by_phone_by_day.json",
        help="Path to nested conversation JSON file.",
    )
    parser.add_argument(
        "--output-csv",
        default="conversation_grades.csv",
        help="Path to output CSV table.",
    )
    parser.add_argument(
        "--output-json",
        default=None,
        help="Optional path to write the output rows as JSON.",
    )
    parser.add_argument(
        "--errors-json",
        default="conversation_grades_errors.json",
        help="Path for prompt-level errors and retries info.",
    )
    parser.add_argument(
        "--prompts-dir",
        default=".",
        help="Directory containing the 5 prompt files and system_prompt.md.",
    )
    parser.add_argument(
        "--system-prompt-file",
        default="system_prompt.md",
        help="System prompt file used for prompts that include {{system_prompt}}.",
    )
    parser.add_argument(
        "--dotenv",
        default=".env",
        help="Optional .env file path (loaded if present).",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="OpenRouter API key. If omitted, uses OPENROUTER_API_KEY or OPENAI_API_KEY.",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="OpenRouter base URL. Defaults to OPENROUTER_BASE_URL or https://openrouter.ai/api/v1",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model slug for OpenRouter, e.g. openai/gpt-4o-mini.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=25,
        help="Max number of in-flight conversations (semaphore).",
    )
    parser.add_argument(
        "--max-conversations",
        type=int,
        default=None,
        help="Optional cap for debugging/smoke tests.",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Retry attempts per prompt call.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="Model temperature for grading calls.",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=25,
        help="Log progress every N processed conversations.",
    )
    parser.add_argument(
        "--disable-tqdm",
        action="store_true",
        help="Disable tqdm_asyncio progress bar for the outer conversations loop.",
    )
    parser.add_argument(
        "--disable-response-format",
        action="store_true",
        help="Disable response_format=json_object. Useful for models that reject it.",
    )
    parser.add_argument(
        "--http-referer",
        default=None,
        help="Optional OpenRouter HTTP-Referer header value.",
    )
    parser.add_argument(
        "--x-title",
        default=None,
        help="Optional OpenRouter X-Title header value.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip API calls and emit rows with null metric fields.",
    )
    return parser.parse_args()


def load_dotenv_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def read_required_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Missing required file: {path}")
    return path.read_text(encoding="utf-8")


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=SCHEMA_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in SCHEMA_COLUMNS})


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=2)


def flatten_conversations(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, Mapping):
        raise ValueError("Input JSON root must be an object keyed by phone number.")

    entries: list[dict[str, Any]] = []
    for phone_number, by_date in raw.items():
        if not isinstance(by_date, Mapping):
            continue
        for grade_date, messages in by_date.items():
            if not isinstance(messages, list):
                continue
            entries.append(
                {
                    "phone_number": str(phone_number),
                    "grade_date": str(grade_date),
                    "messages": messages,
                }
            )
    entries.sort(key=lambda item: (item["phone_number"], item["grade_date"]))
    return entries


def format_conversation(messages: Sequence[Any]) -> str:
    lines: list[str] = []
    for index, item in enumerate(messages, start=1):
        if not isinstance(item, Mapping):
            continue
        sender = str(item.get("sender", "unknown")).strip() or "unknown"
        message = str(item.get("message", "")).strip()
        lines.append(f"{index}. {sender}: {message}")
    return "\n".join(lines).strip()


def build_prompt(
    template: str,
    conversation_text: str,
    system_prompt_text: str,
) -> str:
    prompt = template.replace("{{conversation}}", conversation_text)
    prompt = prompt.replace("{{system_prompt}}", system_prompt_text)
    prompt += "\n\nReturn only valid JSON. Do not include markdown, prose, or code fences."
    return prompt


def extract_completion_text(response: Any) -> str:
    choices = getattr(response, "choices", None)
    if not choices:
        raise ValueError("Model response has no choices.")
    message = choices[0].message
    content = getattr(message, "content", None)
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for chunk in content:
            if isinstance(chunk, str):
                parts.append(chunk)
                continue
            text = None
            if isinstance(chunk, Mapping):
                text = chunk.get("text") or chunk.get("content")
            else:
                text = getattr(chunk, "text", None)
            if text is not None:
                parts.append(str(text))
        return "".join(parts).strip()
    return str(content).strip()


def parse_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("Empty model response.")

    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].lstrip()

    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    for idx, ch in enumerate(cleaned):
        if ch != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(cleaned[idx:])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue

    raise ValueError(f"Could not parse JSON object from model output: {text[:400]}")


def coerce_score(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be integer 1..10, got bool.")
    if isinstance(value, (int, float)):
        score = int(value)
    elif isinstance(value, str):
        score = int(float(value.strip()))
    else:
        raise ValueError(f"{field} must be numeric 1..10, got {type(value).__name__}.")
    if score < 1 or score > 10:
        raise ValueError(f"{field} out of range 1..10: {score}")
    return score


def coerce_bool(value: Any, field: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "1"}:
            return True
        if lowered in {"false", "no", "0"}:
            return False
    raise ValueError(f"{field} must be boolean, got {value!r}")


def coerce_enum(value: Any, field: str, allowed: set[str]) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be string enum, got {type(value).__name__}.")
    lookup = {item.lower(): item for item in allowed}
    normalized = lookup.get(value.strip().lower())
    if normalized is None:
        raise ValueError(f"{field} must be one of {sorted(allowed)}, got {value!r}")
    return normalized


def normalize_prompt_output(prompt_key: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    spec = PROMPT_SPECS[prompt_key]
    out: dict[str, Any] = {}
    for field in spec.output_fields:
        if field not in payload:
            raise ValueError(f"{prompt_key} response missing required field '{field}'.")
        raw_value = payload[field]
        if field in SCORE_FIELDS:
            out[field] = coerce_score(raw_value, field)
        elif field in BOOL_FIELDS:
            out[field] = coerce_bool(raw_value, field)
        elif field in ENUM_FIELDS:
            out[field] = coerce_enum(raw_value, field, ENUM_FIELDS[field])
        else:
            out[field] = "" if raw_value is None else str(raw_value).strip()
    return out


def make_row_stub(phone_number: str, grade_date: str) -> dict[str, Any]:
    row = {column: None for column in SCHEMA_COLUMNS}
    row["id"] = str(uuid.uuid5(uuid.NAMESPACE_URL, f"conversation-grade:{phone_number}:{grade_date}"))
    row["phone_number"] = phone_number
    row["grade_date"] = grade_date
    row["created_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return row


async def evaluate_prompt(
    *,
    client: AsyncOpenAI,
    prompt_key: str,
    prompt_text: str,
    model: str,
    retries: int,
    temperature: float,
    use_response_format: bool,
) -> dict[str, Any]:
    response_format_enabled = use_response_format
    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            request_args: dict[str, Any] = {
                "model": model,
                "messages": [{"role": "user", "content": prompt_text}],
                "temperature": temperature,
            }
            if response_format_enabled:
                request_args["response_format"] = {"type": "json_object"}

            completion = await client.chat.completions.create(**request_args)
            text = extract_completion_text(completion)
            payload = parse_json_object(text)
            return normalize_prompt_output(prompt_key, payload)
        except Exception as exc:
            last_error = exc
            message = str(exc).lower()
            if response_format_enabled and "response_format" in message and (
                "not supported" in message or "invalid parameter" in message
            ):
                response_format_enabled = False

            if attempt < retries:
                delay = (2 ** (attempt - 1)) + random.uniform(0.0, 0.35)
                await asyncio.sleep(delay)

    assert last_error is not None
    raise RuntimeError(
        f"{prompt_key} failed after {retries} attempts: {last_error}"
    ) from last_error


async def process_conversation(
    *,
    client: AsyncOpenAI,
    entry: Mapping[str, Any],
    system_prompt_text: str,
    prompt_templates: Mapping[str, str],
    model: str,
    retries: int,
    temperature: float,
    use_response_format: bool,
    dry_run: bool,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    phone_number = str(entry["phone_number"])
    grade_date = str(entry["grade_date"])
    messages = entry.get("messages", [])
    conversation_text = format_conversation(messages if isinstance(messages, list) else [])

    row = make_row_stub(phone_number, grade_date)
    errors: list[dict[str, Any]] = []

    if dry_run:
        return row, errors

    tasks: dict[str, asyncio.Task[dict[str, Any]]] = {}
    for prompt_key in PROMPT_ORDER:
        spec = PROMPT_SPECS[prompt_key]
        template = prompt_templates[prompt_key]
        current_system_prompt = system_prompt_text if spec.include_system_prompt else ""
        prompt_text = build_prompt(
            template=template,
            conversation_text=conversation_text,
            system_prompt_text=current_system_prompt,
        )
        tasks[prompt_key] = asyncio.create_task(
            evaluate_prompt(
                client=client,
                prompt_key=prompt_key,
                prompt_text=prompt_text,
                model=model,
                retries=retries,
                temperature=temperature,
                use_response_format=use_response_format,
            )
        )

    for prompt_key, task in tasks.items():
        try:
            prompt_result = await task
            row.update(prompt_result)
        except Exception as exc:
            errors.append(
                {
                    "phone_number": phone_number,
                    "grade_date": grade_date,
                    "prompt": prompt_key,
                    "error": str(exc),
                }
            )

    return row, errors


def resolve_runtime_config(args: argparse.Namespace) -> dict[str, Any]:
    load_dotenv_file(Path(args.dotenv))

    api_key = args.api_key or os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key and not args.dry_run:
        raise ValueError(
            "Missing API key. Provide --api-key or set OPENROUTER_API_KEY/OPENAI_API_KEY."
        )

    base_url = args.base_url or os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1"
    model = args.model or os.getenv("OPENROUTER_MODEL") or "openai/gpt-4o-mini"
    http_referer = args.http_referer or os.getenv("OPENROUTER_HTTP_REFERER")
    x_title = args.x_title or os.getenv("OPENROUTER_X_TITLE")

    return {
        "api_key": api_key,
        "base_url": base_url,
        "model": model,
        "http_referer": http_referer,
        "x_title": x_title,
    }


async def run(args: argparse.Namespace) -> int:
    config = resolve_runtime_config(args)

    prompts_dir = Path(args.prompts_dir)
    input_path = Path(args.input_json)
    output_csv_path = Path(args.output_csv)
    output_json_path = Path(args.output_json) if args.output_json else None
    errors_json_path = Path(args.errors_json)

    prompt_templates: dict[str, str] = {}
    for prompt_key, spec in PROMPT_SPECS.items():
        prompt_templates[prompt_key] = read_required_text(prompts_dir / spec.template_file)
    system_prompt_text = read_required_text(prompts_dir / args.system_prompt_file)

    raw_data = read_json(input_path)
    entries = flatten_conversations(raw_data)
    if args.max_conversations is not None:
        entries = entries[: args.max_conversations]

    if not entries:
        write_csv(output_csv_path, [])
        write_json(errors_json_path, [])
        if output_json_path:
            write_json(output_json_path, [])
        print("No conversations found in input.")
        return 0

    conversation_semaphore = asyncio.Semaphore(max(1, args.concurrency))
    headers: dict[str, str] = {}
    if config["http_referer"]:
        headers["HTTP-Referer"] = config["http_referer"]
    if config["x_title"]:
        headers["X-Title"] = config["x_title"]

    if args.dry_run:
        client = AsyncOpenAI(
            api_key="dry-run",
            base_url=config["base_url"],
            default_headers=headers or None,
        )
    else:
        client = AsyncOpenAI(
            api_key=config["api_key"],
            base_url=config["base_url"],
            default_headers=headers or None,
            max_retries=0,
        )

    async def process_with_limit(entry: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        async with conversation_semaphore:
            return await process_conversation(
                client=client,
                entry=entry,
                system_prompt_text=system_prompt_text,
                prompt_templates=prompt_templates,
                model=config["model"],
                retries=max(1, args.retries),
                temperature=args.temperature,
                use_response_format=not args.disable_response_format,
                dry_run=args.dry_run,
            )
    tasks = [asyncio.create_task(process_with_limit(entry)) for entry in entries]

    rows: list[dict[str, Any]] = []
    all_errors: list[dict[str, Any]] = []
    total = len(tasks)

    if tqdm_asyncio is not None and not args.disable_tqdm:
        pending_iter = tqdm_asyncio.as_completed(
            tasks,
            total=total,
            desc="Processing daily conversations",
            unit="conv",
        )
        for pending in pending_iter:
            row, errors = await pending
            rows.append(row)
            all_errors.extend(errors)
    else:
        for index, pending in enumerate(asyncio.as_completed(tasks), start=1):
            row, errors = await pending
            rows.append(row)
            all_errors.extend(errors)
            if index % max(1, args.progress_every) == 0 or index == total:
                print(f"Processed {index}/{total} daily conversations...")

    rows.sort(key=lambda item: (item["phone_number"], item["grade_date"]))
    write_csv(output_csv_path, rows)
    write_json(errors_json_path, all_errors)
    if output_json_path:
        write_json(output_json_path, rows)

    print(f"Wrote {len(rows)} rows to {output_csv_path}")
    if output_json_path:
        print(f"Wrote JSON rows to {output_json_path}")
    if all_errors:
        print(
            f"Completed with {len(all_errors)} prompt-level errors. "
            f"See {errors_json_path}."
        )
        return 2

    print("Completed with no prompt-level errors.")
    return 0


def main() -> int:
    args = parse_args()
    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        print("Interrupted by user.")
        return 130
    except Exception as exc:
        print(f"Failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
