from app.providers.clients import _looks_like_gemini_schema_error, _to_gemini_schema


def test_to_gemini_schema_inlines_defs_and_refs():
    schema = {
        "type": "object",
        "properties": {
            "quiz_id": {"type": "string"},
            "source": {"$ref": "#/$defs/Source"},
            "image_url": {
                "anyOf": [
                    {"type": "string"},
                    {"type": "null"},
                ]
            },
        },
        "required": ["quiz_id", "source"],
        "$defs": {
            "Source": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "page_id": {"type": "integer"},
                },
                "required": ["title", "page_id"],
            }
        },
    }

    converted = _to_gemini_schema(schema)

    assert "$defs" not in converted
    source_schema = converted["properties"]["source"]
    assert "$ref" not in source_schema
    assert source_schema["type"] == "OBJECT"
    assert source_schema["properties"]["page_id"]["type"] == "INTEGER"

    image_url_schema = converted["properties"]["image_url"]
    assert image_url_schema["type"] == "STRING"
    assert image_url_schema["nullable"] is True


def test_looks_like_gemini_schema_error_detects_defs_in_response_schema():
    response_text = (
        '{"error":{"code":400,"message":"Invalid JSON payload received. '
        'Unknown name \\"$defs\\" at \'generation_config.response_schema\': Cannot find field."}}'
    )
    assert _looks_like_gemini_schema_error(response_text) is True
