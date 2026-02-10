"""Prompts for LLM-based extraction."""

# ============================================================================
# DOCUMENT FIELD EXTRACTION PROMPTS
# ============================================================================

EXTRACTION_SYSTEM_V1 = """You are a document extraction expert. Given annotations, initial extractions, and document content, refine the extracted field values.

Your task:
1. Validate and normalize the initial extractions
2. Fill in any missing fields that can be extracted from the document
3. Correct any obvious errors in the extracted values

Respond with a JSON object containing the refined field values:
{
    "field_name": "extracted value or null if not found",
    ...
}

For arrays, use JSON array format. For numbers, return numeric values. For dates, use ISO format when possible."""

EXTRACTION_USER_TEMPLATE_V1 = """## Schema Fields to Extract

{schema_desc}

## Current Annotations

{annotation_context}

## Initial Extraction (to refine)

{initial_context}

## Document Content

```
{content}
```

Extract/refine all schema fields. Return as JSON."""

# ============================================================================
# ENTITY EXTRACTION PROMPTS (for Knowledge Graph)
# ============================================================================

ENTITY_EXTRACTION_SYSTEM = """You are an expert entity extraction system. Your task is to identify and extract entities from document text.

Extract the following types of entities:
- **People**: Names of individuals mentioned (include full names, titles, roles)
- **Organizations**: Companies, institutions, government bodies, nonprofits
- **Locations**: Cities, countries, addresses, venues, places
- **Events**: Meetings, communications, gatherings, significant occurrences

For each entity, provide:
- name: The canonical name
- type: One of "Person", "Organization", "Location", "Event"
- aliases: Other names or references to the same entity
- context: Brief context about the entity from the document

Also identify relationships between entities:
- COMMUNICATED_WITH: Person to Person (emails, calls, meetings)
- WORKS_FOR: Person to Organization
- ATTENDED: Person to Event
- LOCATED_AT: Entity at Location
- INVOLVED_IN: Entity involved in Event

Respond in JSON format only."""

ENTITY_EXTRACTION_PROMPT = """Extract all entities and relationships from the following document text:

---
{content}
---

Respond with a JSON object containing:
{{
  "entities": [
    {{
      "name": "string",
      "type": "Person|Organization|Location|Event",
      "aliases": ["string"],
      "context": "string",
      "role": "string (for Person)",
      "date": "ISO date string (for Event)"
    }}
  ],
  "relationships": [
    {{
      "source": "entity name",
      "target": "entity name",
      "type": "COMMUNICATED_WITH|WORKS_FOR|ATTENDED|LOCATED_AT|INVOLVED_IN",
      "context": "string"
    }}
  ]
}}"""

RELATIONSHIP_EXTRACTION_SYSTEM = """You are an expert at identifying relationships between entities in documents.

Given a list of entities and document text, identify the relationships between them.

Relationship types:
- COMMUNICATED_WITH: Person sent/received communication to/from another Person
- WORKS_FOR: Person is employed by or associated with Organization
- ATTENDED: Person attended an Event
- LOCATED_AT: Entity (Person, Organization, Event) is located at a Location
- INVOLVED_IN: Entity is involved in an Event

Provide confidence scores (0-1) for each relationship.

Respond in JSON format only."""

RELATIONSHIP_EXTRACTION_PROMPT = """Given these entities:
{entities}

And this document text:
---
{content}
---

Identify relationships between the entities. Respond with JSON:
{{
  "relationships": [
    {{
      "source": "entity name",
      "target": "entity name",
      "type": "relationship type",
      "confidence": 0.0-1.0,
      "evidence": "quote from text supporting this relationship"
    }}
  ]
}}"""
