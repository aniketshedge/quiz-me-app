from app.providers.clients import _to_openai_strict_schema


def test_to_openai_strict_schema_adds_additional_properties_false_for_objects():
    schema = {
        "type": "object",
        "properties": {
            "quiz_id": {"type": "string"},
            "source": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "page_id": {"type": "integer"},
                },
                "required": ["title"],
            },
            "distractor_feedback": {
                "type": "object",
                "additionalProperties": {"type": "string"},
            },
        },
        "required": ["quiz_id"],
    }

    converted = _to_openai_strict_schema(schema)

    assert converted["additionalProperties"] is False
    assert set(converted["required"]) == {"quiz_id", "source", "distractor_feedback"}

    source_schema = converted["properties"]["source"]
    assert source_schema["additionalProperties"] is False
    assert set(source_schema["required"]) == {"title", "page_id"}

    # Preserve dict-like schema for map fields.
    feedback_schema = converted["properties"]["distractor_feedback"]
    assert isinstance(feedback_schema["additionalProperties"], dict)
