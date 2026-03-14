from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from .utils import normalize_alias

SENTENCE_PATTERN = re.compile(r"[^.!?]+")
ENTITY_PATTERN = re.compile(r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b")
WORD_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9-]*")
COMPANY_HINTS = {"corp", "inc", "llc", "ltd", "labs", "systems"}
DROP_ENTITY_PREFIXES = {"customer", "client", "issue", "problem", "team"}
BOUNDARY_WORDS = {"a", "an", "and", "at", "by", "for", "from", "in", "of", "on", "or", "the", "to", "with"}


@dataclass(slots=True)
class ExtractedEntity:
    name: str
    entity_type: str


@dataclass(slots=True)
class ExtractedClaim:
    statement: str
    claim_type: str
    relation_type: str | None
    confidence: float
    entities: list[ExtractedEntity]


class Extractor(Protocol):
    def extract(self, content: str) -> list[ExtractedClaim]: ...


def canonicalize_statement(value: str) -> str:
    collapsed = re.sub(r"\s+", " ", value.strip())
    return collapsed.rstrip(".,;:!?")


def canonicalize_claim(claim: ExtractedClaim) -> tuple[str, str, str | None, tuple[str, ...]]:
    entity_aliases = tuple(sorted(normalize_alias(entity.name) for entity in claim.entities))
    return (
        canonicalize_statement(claim.statement).lower(),
        claim.claim_type,
        claim.relation_type,
        entity_aliases,
    )


class RuleBasedExtractor:
    def extract(self, content: str) -> list[ExtractedClaim]:
        claims: list[ExtractedClaim] = []
        seen: set[tuple[str, str, str | None, tuple[str, ...]]] = set()

        for sentence in self._split_sentences(content):
            entities = self._extract_entities(sentence)
            claim = ExtractedClaim(
                statement=canonicalize_statement(sentence),
                claim_type="relationship" if len(entities) >= 2 else "attribute",
                relation_type=self._relation_type(sentence),
                confidence=self._confidence(sentence, entities),
                entities=entities,
            )
            signature = canonicalize_claim(claim)
            if signature in seen:
                continue
            seen.add(signature)
            claims.append(claim)
        return claims

    def _split_sentences(self, content: str) -> list[str]:
        sentences = [item.strip() for item in SENTENCE_PATTERN.findall(content) if item.strip()]
        if not sentences and content.strip():
            return [content.strip()]
        return sentences

    def _extract_entities(self, sentence: str) -> list[ExtractedEntity]:
        seen: set[str] = set()
        entities: list[ExtractedEntity] = []

        for name in self._extract_company_candidates(sentence):
            entity = self._build_entity(name)
            if entity is None:
                continue
            alias = normalize_alias(entity.name)
            if alias in seen:
                continue
            seen.add(alias)
            entities.append(entity)

        for match in ENTITY_PATTERN.findall(sentence):
            entity = self._build_entity(match)
            if entity is None:
                continue
            alias = normalize_alias(entity.name)
            if alias in seen:
                continue
            seen.add(alias)
            entities.append(entity)

        return entities

    def _extract_company_candidates(self, sentence: str) -> list[str]:
        tokens = WORD_PATTERN.findall(sentence)
        candidates: list[str] = []
        for index, token in enumerate(tokens):
            if token.lower() not in COMPANY_HINTS:
                continue
            phrase = [token]
            previous = index - 1
            while previous >= 0 and len(phrase) < 4:
                candidate = tokens[previous]
                if candidate.lower() in BOUNDARY_WORDS:
                    break
                phrase.insert(0, candidate)
                previous -= 1
            if len(phrase) < 2:
                continue
            candidates.append(" ".join(phrase))
        return candidates

    def _build_entity(self, raw_name: str) -> ExtractedEntity | None:
        parts = raw_name.split()
        while parts and parts[0].lower() in DROP_ENTITY_PREFIXES:
            parts = parts[1:]
        name = " ".join(parts).strip()
        if not name:
            return None
        entity_type = self._classify_entity(name)
        return ExtractedEntity(
            name=self._normalize_entity_name(name, entity_type),
            entity_type=entity_type,
        )

    def _classify_entity(self, name: str) -> str:
        last = name.split()[-1].lower()
        if last in COMPANY_HINTS:
            return "company"
        if len(name.split()) >= 2:
            return "person"
        return "topic"

    def _normalize_entity_name(self, name: str, entity_type: str) -> str:
        words = name.split()
        if entity_type == "company":
            return " ".join(word.upper() if word.isupper() else word.capitalize() for word in words)
        if entity_type == "person":
            return " ".join(word.capitalize() for word in words)
        return name

    def _relation_type(self, sentence: str) -> str | None:
        lowered = sentence.lower()
        if "reported" in lowered:
            return "REPORTED"
        if any(phrase in lowered for phrase in ("requested", "requests", "needs", "wants", "asked for", "asks for")):
            return "REQUESTED"
        if "works at" in lowered or "from " in lowered:
            return "ASSOCIATED_WITH"
        return None

    def _confidence(self, sentence: str, entities: list[ExtractedEntity]) -> float:
        base = 0.45
        base += min(len(sentence.split()) / 20.0, 0.25)
        base += min(len(entities) * 0.12, 0.3)
        return round(min(base, 0.98), 2)
