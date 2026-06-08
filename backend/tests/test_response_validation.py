"""Tests for response validation against the template (security: facts integrity)."""

import unittest

from app.domain.response_validation import (
    QuestionSpec,
    ResponseValidationError,
    validate_responses,
)

QS = [
    QuestionSpec("mfa_enabled", "single_select", {"options": [True, False]}),
    QuestionSpec("score", "number", {}),
    QuestionSpec("notes", "text", {}),
    QuestionSpec("controls", "multi_select", {"options": ["a", "b", "c"]}),
    QuestionSpec("doc", "file_upload", {}),
]


class TestResponseValidation(unittest.TestCase):
    def test_valid_responses_pass(self):
        validate_responses(
            QS,
            [
                {"key": "mfa_enabled", "value": False},
                {"key": "score", "value": 3},
                {"key": "notes", "value": "ok"},
                {"key": "controls", "value": ["a", "c"]},
                {"key": "doc", "value": "doc-123"},
            ],
        )

    def test_unknown_key_rejected(self):
        with self.assertRaises(ResponseValidationError):
            validate_responses(QS, [{"key": "ghost", "value": 1}])

    def test_number_type_enforced(self):
        with self.assertRaises(ResponseValidationError):
            validate_responses(QS, [{"key": "score", "value": "five"}])

    def test_bool_is_not_a_number(self):
        with self.assertRaises(ResponseValidationError):
            validate_responses(QS, [{"key": "score", "value": True}])

    def test_single_select_option_enforced(self):
        with self.assertRaises(ResponseValidationError):
            validate_responses(QS, [{"key": "mfa_enabled", "value": "maybe"}])

    def test_multi_select_must_be_list_of_options(self):
        with self.assertRaises(ResponseValidationError):
            validate_responses(QS, [{"key": "controls", "value": ["a", "z"]}])
        with self.assertRaises(ResponseValidationError):
            validate_responses(QS, [{"key": "controls", "value": "a"}])

    def test_partial_unanswered_allowed(self):
        validate_responses(QS, [{"key": "score", "value": None}])  # no error


if __name__ == "__main__":
    unittest.main()
