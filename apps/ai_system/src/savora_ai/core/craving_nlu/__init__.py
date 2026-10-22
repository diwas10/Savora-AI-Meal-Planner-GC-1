"""Structured Craving NLU: deterministic TemplateParser and QwenParser with schema validation.

Turns free-text craving or swap utterances into a validated `CravingRequest` (section 9.1).
Never imports backend modules, never trusts unvalidated model output, and never places
allergens mentioned in chat into `excludedIngredientIds` (allergies come only from the
user's confirmed profile).
"""

import json
import logging
import re
from collections.abc import Mapping
from pathlib import Path
from time import perf_counter
from typing import Literal, Protocol

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError
from pydantic.alias_generators import to_camel

from savora_ai.providers.qwen import FakeQwenClient, HttpxQwenClient, QwenClient
from savora_ai.schemas.craving import CravingIntent, CravingRequest, FlavorTag

logger = logging.getLogger(__name__)

PROMPT_VERSION = "craving-v1"
PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "craving_v1.md"

DEFAULT_CUISINE_IDS: dict[str, str] = {
    "AMERICAN": "American",
    "CHINESE": "Chinese",
    "INDIAN": "Indian",
    "ITALIAN": "Italian",
    "JAPANESE": "Japanese",
    "MEXICAN": "Mexican",
    "MIDDLE_EASTERN": "Middle Eastern",
    "NEPALI": "Nepali",
    "SPANISH": "Spanish",
    "THAI": "Thai",
}

CUISINE_LEXICON: dict[str, str] = {
    "american": "AMERICAN",
    "chinese": "CHINESE",
    "szechuan": "CHINESE",
    "sichuan": "CHINESE",
    "cantonese": "CHINESE",
    "hakka": "CHINESE",
    "indian": "INDIAN",
    "north indian": "INDIAN",
    "south indian": "INDIAN",
    "punjabi": "INDIAN",
    "desi": "INDIAN",
    "italian": "ITALIAN",
    "japanese": "JAPANESE",
    "mexican": "MEXICAN",
    "middle eastern": "MIDDLE_EASTERN",
    "middle-eastern": "MIDDLE_EASTERN",
    "levantine": "MIDDLE_EASTERN",
    "arabic": "MIDDLE_EASTERN",
    "mediterranean": "MIDDLE_EASTERN",
    "nepali": "NEPALI",
    "nepalese": "NEPALI",
    "newari": "NEPALI",
    "himalayan": "NEPALI",
    "spanish": "SPANISH",
    "thai": "THAI",
    # Nepali & Indian dish cues that imply cuisine when stated as a craving
    "momo": "NEPALI",
    "momos": "NEPALI",
    "thukpa": "NEPALI",
    "dal bhat": "NEPALI",
    "gundruk": "NEPALI",
    "sel roti": "NEPALI",
    "choila": "NEPALI",
    "aloo tama": "NEPALI",
    "kwati": "NEPALI",
    "bara": "NEPALI",
    "chatamari": "NEPALI",
    "biryani": "INDIAN",
    "tikka masala": "INDIAN",
    "masala dosa": "INDIAN",
    "dosa": "INDIAN",
    "idli": "INDIAN",
    "sambar": "INDIAN",
    "chana masala": "INDIAN",
    "palak paneer": "INDIAN",
    "paneer tikka": "INDIAN",
    "dal makhani": "INDIAN",
    "rajma": "INDIAN",
    "chole": "INDIAN",
    "khichdi": "INDIAN",
    "upma": "INDIAN",
    "poha": "INDIAN",
    "paratha": "INDIAN",
    "pad thai": "THAI",
    "tom yum": "THAI",
    "green curry": "THAI",
    "massaman": "THAI",
    "ramen": "JAPANESE",
    "teriyaki": "JAPANESE",
    "miso soup": "JAPANESE",
    "udon": "JAPANESE",
    "tacos": "MEXICAN",
    "taco": "MEXICAN",
    "burrito": "MEXICAN",
    "enchilada": "MEXICAN",
    "quesadilla": "MEXICAN",
    "risotto": "ITALIAN",
    "lasagna": "ITALIAN",
    "gnocchi": "ITALIAN",
    "paella": "SPANISH",
    "falafel": "MIDDLE_EASTERN",
    "shakshuka": "MIDDLE_EASTERN",
    "hummus": "MIDDLE_EASTERN",
    "shawarma": "MIDDLE_EASTERN",
    "kung pao": "CHINESE",
    "mapo tofu": "CHINESE",
    "chow mein": "CHINESE",
}

FLAVOR_LEXICON: dict[str, FlavorTag] = {
    "spicy": FlavorTag.SPICY,
    "hot": FlavorTag.SPICY,
    "fiery": FlavorTag.SPICY,
    "chili": FlavorTag.SPICY,
    "chilli": FlavorTag.SPICY,
    "chili-heavy": FlavorTag.SPICY,
    "peppery": FlavorTag.SPICY,
    "zesty": FlavorTag.SPICY,
    "sweet": FlavorTag.SWEET,
    "sugary": FlavorTag.SWEET,
    "honeyed": FlavorTag.SWEET,
    "caramelized": FlavorTag.SWEET,
    "sour": FlavorTag.SOUR,
    "tangy": FlavorTag.SOUR,
    "tart": FlavorTag.SOUR,
    "citrusy": FlavorTag.SOUR,
    "lemony": FlavorTag.SOUR,
    "vinegary": FlavorTag.SOUR,
    "smoky": FlavorTag.SMOKY,
    "smoked": FlavorTag.SMOKY,
    "charred": FlavorTag.SMOKY,
    "barbecue": FlavorTag.SMOKY,
    "bbq": FlavorTag.SMOKY,
    "tandoori": FlavorTag.SMOKY,
    "creamy": FlavorTag.CREAMY,
    "rich": FlavorTag.CREAMY,
    "velvety": FlavorTag.CREAMY,
    "buttery": FlavorTag.CREAMY,
    "cheesy": FlavorTag.CREAMY,
}

# Reuses PR #11 alias normalization ideas (brinjal -> EGGPLANT, capsicum -> BELL_PEPPER, etc.)
INGREDIENT_ALIASES: dict[str, str] = {
    "brinjal": "EGGPLANT",
    "brinjals": "EGGPLANT",
    "aubergine": "EGGPLANT",
    "aubergines": "EGGPLANT",
    "baingan": "EGGPLANT",
    "eggplant": "EGGPLANT",
    "eggplants": "EGGPLANT",
    "capsicum": "BELL_PEPPER",
    "capsicums": "BELL_PEPPER",
    "bell pepper": "BELL_PEPPER",
    "bell peppers": "BELL_PEPPER",
    "shimla mirch": "BELL_PEPPER",
    "coriander leaves": "CILANTRO",
    "fresh coriander": "CILANTRO",
    "dhaniya": "CILANTRO",
    "cilantro": "CILANTRO",
    "curd": "YOGURT",
    "dahi": "YOGURT",
    "yogurt": "YOGURT",
    "yoghurt": "YOGURT",
    "garbanzo beans": "CHICKPEAS",
    "garbanzo": "CHICKPEAS",
    "chana": "CHICKPEAS",
    "chickpea": "CHICKPEAS",
    "chickpeas": "CHICKPEAS",
    "bhindi": "OKRA",
    "ladyfinger": "OKRA",
    "okra": "OKRA",
    "aloo": "POTATO",
    "potato": "POTATO",
    "potatoes": "POTATO",
    "pyaaz": "ONION",
    "onion": "ONION",
    "onions": "ONION",
    "lahsun": "GARLIC",
    "garlic": "GARLIC",
    "mushroom": "MUSHROOM",
    "mushrooms": "MUSHROOM",
    "noodle": "NOODLES",
    "noodles": "NOODLES",
    "pasta": "PASTA",
    "rice": "RICE",
    "tofu": "TOFU",
    "paneer": "PANEER",
    "cottage cheese": "PANEER",
    "spinach": "SPINACH",
    "palak": "SPINACH",
    "tomato": "TOMATO",
    "tomatoes": "TOMATO",
    "coconut": "COCONUT",
    "chicken": "CHICKEN",
    "beef": "BEEF",
    "pork": "PORK",
    "bacon": "BACON",
    "shrimp": "SHRIMP",
    "prawns": "SHRIMP",
    "fish": "FISH",
    "egg": "EGG",
    "eggs": "EGG",
    "cheese": "CHEESE",
    "butter": "BUTTER",
    "cream": "CREAM",
    "milk": "MILK",
    "bean": "BEANS",
    "beans": "BEANS",
    "lentil": "LENTILS",
    "lentils": "LENTILS",
    "broccoli": "BROCCOLI",
    "cauliflower": "CAULIFLOWER",
    "gobi": "CAULIFLOWER",
    "cabbage": "CABBAGE",
    "carrot": "CARROT",
    "carrots": "CARROT",
    "pea": "PEAS",
    "peas": "PEAS",
    "matar": "PEAS",
    "corn": "CORN",
    "ginger": "GINGER",
}

_SWAP_RE = re.compile(
    r"\b(swap|replace|substitute|change|switch)\b",
    re.IGNORECASE,
)

_ALLERGY_RE = re.compile(
    r"\b(allergic|allergy|allergies|intolerant|intolerance|anaphylaxis|anaphylactic|celiac)\b",
    re.IGNORECASE,
)

_DAY_WORDS: dict[str, int] = {
    "monday": 1,
    "mon": 1,
    "tuesday": 2,
    "tue": 2,
    "tues": 2,
    "wednesday": 3,
    "wed": 3,
    "thursday": 4,
    "thu": 4,
    "thur": 4,
    "thurs": 4,
    "friday": 5,
    "fri": 5,
    "saturday": 6,
    "sat": 6,
    "sunday": 7,
    "sun": 7,
}

_MEAL_WORDS: dict[str, str] = {
    "breakfast": "BREAKFAST",
    "morning": "BREAKFAST",
    "brunch": "BREAKFAST",
    "lunch": "LUNCH",
    "midday": "LUNCH",
    "dinner": "DINNER",
    "supper": "DINNER",
    "evening": "DINNER",
}

_EXCLUSION_PATTERNS = (
    re.compile(
        r"\b(?:without\s+any|without|no|not\s+with|not|exclude|excluding|hold\s+the|skip\s+the|skip|avoid|avoiding|minus|free\s+of)\s+([a-z][a-z\s-]{1,50}?)(?=\s+(?:for|on|at|with|in|please|but|that|which)\b|[,.!?;]|$)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b([a-z][a-z-]{2,20})-free\b",
        re.IGNORECASE,
    ),
)


class CravingParse(BaseModel):
    model_config = ConfigDict(
        strict=True,
        frozen=True,
        extra="forbid",
        alias_generator=to_camel,
        populate_by_name=True,
    )

    request: CravingRequest
    parser: Literal["TEMPLATE", "QWEN"]
    prompt_version: str
    latency_ms: float
    clarification: str | None = None
    fallback_reason: str | None = None


class CravingParser(Protocol):
    def parse(self, text: str) -> CravingParse: ...


def _extract_slot(text_lower: str) -> tuple[str | None, bool]:
    """Return `(mealSlotId, partial_slot_mentioned)`."""
    direct = re.search(r"\bd([1-7])[_\s-]*([a-z]+)\b", text_lower)
    if direct:
        day_num = int(direct.group(1))
        meal_token = direct.group(2)
        if meal_token in _MEAL_WORDS:
            return f"D{day_num}_{_MEAL_WORDS[meal_token]}", False

    day_index: int | None = None
    day_match = re.search(r"\bday\s*([1-7])\b", text_lower)
    if day_match:
        day_index = int(day_match.group(1))
    else:
        for word, idx in _DAY_WORDS.items():
            if re.search(rf"\b{re.escape(word)}(?:'s)?\b", text_lower):
                day_index = idx
                break

    meal_type: str | None = None
    for word, mtype in _MEAL_WORDS.items():
        if re.search(rf"\b{re.escape(word)}\b", text_lower):
            meal_type = mtype
            break

    if day_index is not None and meal_type is not None:
        return f"D{day_index}_{meal_type}", False
    partial = (day_index is not None) or (meal_type is not None)
    return None, partial


def _extract_cuisines(text_lower: str, cuisine_map: Mapping[str, str]) -> tuple[str, ...]:
    found: list[str] = []
    # Check multi-word and specific lexicon entries longest-first
    for phrase, cid in sorted(CUISINE_LEXICON.items(), key=lambda item: -len(item[0])):
        if cid not in cuisine_map:
            continue
        if (
            re.search(rf"(?<!\w){re.escape(phrase)}(?:s|es)?(?!\w)", text_lower)
            and cid not in found
        ):
            found.append(cid)
    # Also check direct cuisine_map names
    for cid, name in cuisine_map.items():
        n_low = name.lower()
        if re.search(rf"(?<!\w){re.escape(n_low)}(?!\w)", text_lower) and cid not in found:
            found.append(cid)
    return tuple(found[:10])


def _extract_flavors(text_lower: str) -> tuple[FlavorTag, ...]:
    found: list[FlavorTag] = []
    for word, tag in sorted(FLAVOR_LEXICON.items(), key=lambda item: -len(item[0])):
        # Avoid matching negated flavor like "not spicy" or "no spicy"
        negated = re.search(
            rf"\b(?:not|no|without|never|less)\s+(?:too\s+|very\s+)?{re.escape(word)}\b",
            text_lower,
        )
        if negated:
            continue
        if re.search(rf"(?<!\w){re.escape(word)}(?!\w)", text_lower) and tag not in found:
            found.append(tag)
    return tuple(found)


def _normalize_ingredient_candidate(raw: str) -> list[str]:
    cleaned = re.sub(r"[^a-z\s-]", " ", raw.lower()).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    if not cleaned:
        return []
    parts = re.split(r"\b(?:or|and|nor)\b|,", cleaned)
    results: list[str] = []
    for part in parts:
        token = part.strip()
        token = re.sub(r"^(?:any|the|some|extra|much|more)\s+", "", token).strip()
        if not token:
            continue
        if token in INGREDIENT_ALIASES:
            canonical = INGREDIENT_ALIASES[token]
            if canonical not in results:
                results.append(canonical)
            continue
        # Check if any known alias phrase appears inside token
        matched_alias = False
        for phrase, canonical in sorted(
            INGREDIENT_ALIASES.items(), key=lambda item: -len(item[0])
        ):
            if re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", token):
                if canonical not in results:
                    results.append(canonical)
                matched_alias = True
        if (
            not matched_alias
            and len(token) >= 3
            and " " not in token
            and token
            not in {
                "food",
                "dish",
                "dishes",
                "meal",
                "meals",
                "recipe",
                "recipes",
                "something",
                "anything",
                "lunch",
                "dinner",
                "breakfast",
                "today",
                "tonight",
                "tomorrow",
                "spicy",
                "sweet",
                "sour",
                "smoky",
                "creamy",
                "gluten",
                "dairy",
                "meat",
                "oil",
                "sugar",
                "salt",
            }
        ):
            up = token.upper().replace("-", "_")
            if re.match(r"^[A-Z][A-Z0-9_]{0,63}$", up) and up not in results:
                results.append(up)
    return results


def _extract_exclusions(text_lower: str) -> tuple[str, ...]:
    found: list[str] = []
    for pattern in _EXCLUSION_PATTERNS:
        for match in pattern.finditer(text_lower):
            raw_chunk = match.group(1)
            for canonical in _normalize_ingredient_candidate(raw_chunk):
                if canonical not in found:
                    found.append(canonical)
    return tuple(found[:10])


class TemplateParser:
    """Deterministic lexicon and rule baseline for craving NLU."""

    def __init__(self, cuisine_ids: Mapping[str, str] | None = None) -> None:
        self._cuisine_ids = dict(cuisine_ids or DEFAULT_CUISINE_IDS)

    def parse(self, text: str) -> CravingParse:
        started = perf_counter()
        cleaned = " ".join(str(text).strip().split())
        text_lower = cleaned.lower()

        if not cleaned:
            req = CravingRequest(
                intent=CravingIntent.CRAVING_RECOMMEND,
                requires_clarification=True,
            )
            return CravingParse(
                request=req,
                parser="TEMPLATE",
                prompt_version=PROMPT_VERSION,
                latency_ms=round((perf_counter() - started) * 1000, 3),
                clarification=(
                    "What kind of dish are you craving? Try naming a cuisine (e.g. Nepali, "
                    "Indian, Thai) or a flavor (e.g. spicy, creamy)."
                ),
            )

        is_swap = bool(_SWAP_RE.search(text_lower))
        intent = CravingIntent.SWAP_MEAL if is_swap else CravingIntent.CRAVING_RECOMMEND
        has_allergy_mention = bool(_ALLERGY_RE.search(text_lower))

        slot_id, _partial_slot = _extract_slot(text_lower)
        cuisines = _extract_cuisines(text_lower, self._cuisine_ids)
        flavors = _extract_flavors(text_lower)
        # Never populate excludedIngredientIds when an allergy/intolerance is mentioned in text
        exclusions = () if has_allergy_mention else _extract_exclusions(text_lower)

        requires_clarification = False
        clarification: str | None = None

        if has_allergy_mention:
            requires_clarification = True
            clarification = (
                "Allergies and intolerances cannot be applied from chat text alone. "
                "Please update and confirm your allergies in your User Profile so they "
                "are enforced across all recommendations."
            )
        elif intent is CravingIntent.SWAP_MEAL and slot_id is None:
            requires_clarification = True
            clarification = (
                "Which saved meal slot would you like to swap? Please specify both the "
                "day and meal (for example, 'Tuesday lunch' or 'D2_LUNCH')."
            )
        elif (
            intent is CravingIntent.CRAVING_RECOMMEND
            and not cuisines
            and not flavors
            and not exclusions
            and slot_id is None
        ):
            requires_clarification = True
            clarification = (
                "Could you share a cuisine (like Indian, Chinese, Nepali, Thai) or "
                "a flavor tag (spicy, sweet, sour, smoky, creamy) to narrow down recipes?"
            )

        req = CravingRequest(
            intent=intent,
            cuisine_ids=cuisines,
            flavor_tags=flavors,
            excluded_ingredient_ids=exclusions,
            meal_slot_id=slot_id,
            requires_clarification=requires_clarification,
        )
        return CravingParse(
            request=req,
            parser="TEMPLATE",
            prompt_version=PROMPT_VERSION,
            latency_ms=round((perf_counter() - started) * 1000, 3),
            clarification=clarification,
        )


def load_prompt_text() -> str:
    base = PROMPT_PATH.read_text(encoding="utf-8")
    schema_json = json.dumps(CravingRequest.model_json_schema(by_alias=True), indent=2)
    return f"{base}\n\n## JSON Schema\n{schema_json}\n"


class QwenParser:
    """Qwen NLU parser with strict `CravingRequest.model_validate_json` and template fallback."""

    def __init__(
        self,
        client: QwenClient | None,
        *,
        model: str = "Qwen/Qwen2.5-7B-Instruct",
        timeout_s: float = 8.0,
        template_fallback: TemplateParser | None = None,
    ) -> None:
        self._client = client
        self._model = model
        self._timeout_s = timeout_s
        self._fallback = template_fallback or TemplateParser()
        self._system_prompt = load_prompt_text()

    def parse(self, text: str) -> CravingParse:
        started = perf_counter()
        cleaned = " ".join(str(text).strip().split())
        if not cleaned:
            return self._fallback.parse(text)

        # Safety invariant: allergy mentions in free text must NEVER trust model exclusions
        if _ALLERGY_RE.search(cleaned):
            return self._fallback.parse(text)

        if self._client is None or (
            isinstance(self._client, HttpxQwenClient) and not self._client.is_configured
        ):
            fb = self._fallback.parse(text)
            return fb.model_copy(update={"fallback_reason": "QWEN_UNCONFIGURED"})

        try:
            raw_output = self._client.complete(
                system_prompt=self._system_prompt,
                user_text=cleaned,
                model=self._model,
                timeout_s=self._timeout_s,
            )
            request = CravingRequest.model_validate_json(raw_output.strip())
        except TimeoutError as exc:
            logger.warning("Qwen NLU timed out after %ss: %s", self._timeout_s, exc)
            fb = self._fallback.parse(text)
            return fb.model_copy(
                update={
                    "latency_ms": round((perf_counter() - started) * 1000, 3),
                    "fallback_reason": "QWEN_TIMEOUT",
                }
            )
        except httpx.TimeoutException as exc:
            logger.warning("Qwen HTTP request timed out: %s", exc)
            fb = self._fallback.parse(text)
            return fb.model_copy(
                update={
                    "latency_ms": round((perf_counter() - started) * 1000, 3),
                    "fallback_reason": "QWEN_TIMEOUT",
                }
            )
        except ValidationError as exc:
            logger.warning("Qwen NLU output failed schema validation: %s", exc)
            fb = self._fallback.parse(text)
            return fb.model_copy(
                update={
                    "latency_ms": round((perf_counter() - started) * 1000, 3),
                    "fallback_reason": "QWEN_INVALID_SCHEMA",
                }
            )
        except Exception as exc:
            logger.warning("Qwen NLU call failed (%s): %s", type(exc).__name__, exc)
            fb = self._fallback.parse(text)
            return fb.model_copy(
                update={
                    "latency_ms": round((perf_counter() - started) * 1000, 3),
                    "fallback_reason": "QWEN_ERROR",
                }
            )

        clarification: str | None = None
        if request.requires_clarification:
            if request.intent is CravingIntent.SWAP_MEAL and request.meal_slot_id is None:
                clarification = (
                    "Which saved meal slot would you like to swap? Please specify both the "
                    "day and meal (for example, 'Tuesday lunch' or 'D2_LUNCH')."
                )
            else:
                clarification = (
                    "Could you share a cuisine (like Indian, Chinese, Nepali, Thai) or "
                    "a flavor tag (spicy, sweet, sour, smoky, creamy) to narrow down recipes?"
                )

        return CravingParse(
            request=request,
            parser="QWEN",
            prompt_version=PROMPT_VERSION,
            latency_ms=round((perf_counter() - started) * 1000, 3),
            clarification=clarification,
        )


def parse_craving(
    text: str,
    *,
    parser: CravingParser | None = None,
) -> CravingParse:
    """Parse free-text craving input using the supplied parser (defaults to TemplateParser)."""
    active_parser = parser or TemplateParser()
    return active_parser.parse(text)


__all__ = [
    "DEFAULT_CUISINE_IDS",
    "INGREDIENT_ALIASES",
    "PROMPT_VERSION",
    "CravingParse",
    "CravingParser",
    "FakeQwenClient",
    "HttpxQwenClient",
    "QwenClient",
    "QwenParser",
    "TemplateParser",
    "load_prompt_text",
    "parse_craving",
]
