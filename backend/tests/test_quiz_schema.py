from app.schemas import QuizModel


def test_quiz_distribution_validation():
    payload = {
        "quiz_id": "quiz-1",
        "topic": "Demo",
        "source": {
            "wikipedia_title": "Demo",
            "wikipedia_url": "https://example.com",
            "page_id": 1,
            "extract_used": "context",
        },
        "questions": [],
    }

    for idx in range(1, 11):
        payload["questions"].append(
            {
                "id": f"q{idx:02d}",
                "type": "mcq_single",
                "stem": "Question stem long enough",
                "explanation": "Explanation long enough",
                "options": [
                    {"id": "a", "text": "A"},
                    {"id": "b", "text": "B"},
                    {"id": "c", "text": "C"},
                    {"id": "d", "text": "D"},
                ],
                "correct_option_ids": ["a"],
                "distractor_feedback": {"b": "x", "c": "x", "d": "x"},
            }
        )

    for idx in range(11, 13):
        payload["questions"].append(
            {
                "id": f"q{idx:02d}",
                "type": "mcq_multi",
                "stem": "Question stem long enough",
                "explanation": "Explanation long enough",
                "options": [
                    {"id": "a", "text": "A"},
                    {"id": "b", "text": "B"},
                    {"id": "c", "text": "C"},
                    {"id": "d", "text": "D"},
                ],
                "correct_option_ids": ["a", "b"],
                "distractor_feedback": {"c": "x", "d": "x"},
            }
        )

    for idx in range(13, 16):
        payload["questions"].append(
            {
                "id": f"q{idx:02d}",
                "type": "short_text",
                "stem": "Question stem long enough",
                "explanation": "Explanation long enough",
                "expected_answers": ["answer"],
                "grading_context": "context",
            }
        )

    parsed = QuizModel.model_validate(payload)
    assert len(parsed.questions) == 15
