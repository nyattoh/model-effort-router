"""Contract and safety tests for the provider-neutral router."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from model_effort_router import (
    RouterError,
    review_checkpoint,
    route,
    validate_checkpoint,
    validate_request,
)
from model_effort_router.router import (
    ABSTAIN,
    assignment_payload,
    decomposition_payload,
    extract_answers,
)


MODEL = {
    "id": "model-a",
    "provider": "example",
    "efforts": ["low", "high"],
    "capabilities": ["python", "tests"],
}


def input_document(*, first_dependencies: list[str] | None = None) -> dict[str, object]:
    return {
        "request": "Add an isolated feature",
        "constraints": {"runtime_dependencies": "none"},
        "candidates": [
            {
                "id": "candidate-a",
                "description": "A valid two-task graph",
                "tasks": [
                    {
                        "id": "implement",
                        "description": "Implement the change",
                        "depends_on": first_dependencies or [],
                        "requirements": ["python"],
                    },
                    {
                        "id": "verify",
                        "description": "Write focused tests",
                        "depends_on": ["implement"],
                        "requirements": ["tests"],
                    },
                ],
            }
        ],
        "models": [MODEL],
        "max_parallel": 2,
    }


def checkpoint_document() -> dict[str, object]:
    return {
        "task_id": "implement",
        "checkpoint": "after_tests",
        "status": "partial",
        "understanding": {
            "goal": "Fix the confirmed defect without unrelated refactoring.",
            "acceptance": ["Focused tests pass", "Public API remains stable"],
        },
        "completed": ["Focused tests"],
        "evidence": ["tests/test_contract.py: 13 passed"],
        "uncertainties": ["Live provider capability is not part of this fixture."],
        "blockers": [],
        "proposed_action": "continue",
    }


def documented_response(payload: dict[str, object], confidence: float = 0.9) -> dict[str, object]:
    answers = {}
    for question_id, question in payload["questions"].items():
        options = list(question["criteria"])
        selected = next(option for option in options if option != ABSTAIN)
        answers[question_id] = {
            "type": "choice",
            "choice": selected,
            "confidence": confidence,
            "probabilities": {
                option: 1.0 if option == selected else 0.0 for option in options
            },
        }
    return {
        "model": "jev-test",
        "answers": answers,
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }


class ValidationTests(unittest.TestCase):
    def test_accepts_acyclic_dependencies(self) -> None:
        validated = validate_request(input_document())
        self.assertEqual(validated["candidates"][0]["tasks"][1]["depends_on"], ["implement"])

    def test_rejects_unknown_dependency(self) -> None:
        with self.assertRaisesRegex(RouterError, "unknown_dependency"):
            validate_request(input_document(first_dependencies=["missing"]))

    def test_rejects_cycle(self) -> None:
        with self.assertRaisesRegex(RouterError, "cyclic_dependencies"):
            validate_request(input_document(first_dependencies=["verify"]))


class ChoicePayloadTests(unittest.TestCase):
    def test_decomposition_payload_uses_official_choice_shape(self) -> None:
        document = validate_request(input_document())
        payload = decomposition_payload(document, "jev-latest")
        question = payload["questions"]["decomposition"]
        self.assertEqual(question["type"], "choice")
        self.assertEqual(set(question["criteria"]), {"candidate-a", ABSTAIN})
        self.assertNotIn("TYPESAFE_API_KEY", json.dumps(payload))

    def test_assignment_payload_has_one_independent_question_per_task(self) -> None:
        document = validate_request(input_document())
        candidate = document["candidates"][0]
        payload = assignment_payload(document, candidate, "jev-latest")
        self.assertEqual(set(payload["questions"]), {"implement", "verify"})
        self.assertTrue(all(q["type"] == "choice" for q in payload["questions"].values()))

    def test_unknown_choice_response_fails_closed(self) -> None:
        document = validate_request(input_document())
        payload = decomposition_payload(document, "jev-latest")
        with self.assertRaisesRegex(RouterError, "unsupported_jev_response"):
            extract_answers({"answers": {"decomposition": {"type": "choice"}}}, payload)

    def test_usage_allows_forward_compatible_metadata(self) -> None:
        document = validate_request(input_document())
        payload = decomposition_payload(document, "jev-latest")
        response = documented_response(payload)
        response["usage"]["total_tokens"] = 15
        result = extract_answers(response, payload)
        self.assertEqual(result["usage"]["total_tokens"], 15)

    def test_huge_integer_probability_fails_as_router_error(self) -> None:
        document = validate_request(input_document())
        payload = decomposition_payload(document, "jev-latest")
        response = documented_response(payload)
        response["answers"]["decomposition"]["confidence"] = 10**400
        with self.assertRaisesRegex(RouterError, "unsupported_jev_response"):
            extract_answers(response, payload)


class CheckpointTests(unittest.TestCase):
    def test_checkpoint_validation_rejects_unknown_status(self) -> None:
        checkpoint = checkpoint_document()
        checkpoint["status"] = "unknown"
        with self.assertRaisesRegex(RouterError, "invalid_checkpoint_status"):
            validate_checkpoint(checkpoint)

    def test_checkpoint_without_key_returns_decision_payload(self) -> None:
        with patch.dict(os.environ, {"TYPESAFE_API_KEY": ""}, clear=False):
            result = review_checkpoint(checkpoint_document())
        self.assertEqual(result["status"], "decision_required")
        self.assertEqual(result["pre_dispatch_guard"], "human_review")
        self.assertFalse(result["jev_api_called"])
        self.assertEqual(set(result["checkpoint_payload"]["questions"]), {"next_action", "risk_class"})

    def test_checkpoint_signal_can_approve_continuation(self) -> None:
        result = review_checkpoint(checkpoint_document(), client=documented_response)
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["pre_dispatch_guard"], "pass")
        self.assertEqual(result["signal"]["answers"]["next_action"]["choice"], "continue")

    def test_checkpoint_low_confidence_requires_review(self) -> None:
        result = review_checkpoint(
            checkpoint_document(),
            client=lambda payload: documented_response(payload, confidence=0.2),
        )
        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(result["pre_dispatch_guard"], "human_review")
        self.assertEqual(set(result["unresolved_questions"]), {"next_action", "risk_class"})


class RoutingTests(unittest.TestCase):
    def test_cli_reports_key_presence_without_printing_key(self) -> None:
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
        environment["TYPESAFE_API_KEY"] = "configured-but-secret"
        completed = subprocess.run(
            [sys.executable, "-m", "model_effort_router", "--check-api-key"],
            text=True,
            capture_output=True,
            check=False,
            env=environment,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout), {"TYPESAFE_API_KEY_configured": True})
        self.assertNotIn(environment["TYPESAFE_API_KEY"], completed.stdout)

    def test_missing_key_never_opens_network(self) -> None:
        with patch.dict(os.environ, {"TYPESAFE_API_KEY": ""}, clear=False):
            with patch("model_effort_router.router.urllib.request.build_opener") as opener:
                result = route(input_document())
        opener.assert_not_called()
        self.assertEqual(result["mode"], "framework-only")
        self.assertEqual(result["status"], "decision_required")
        self.assertFalse(result["jev_api_called"])

    def test_dry_run_never_opens_network_even_with_key(self) -> None:
        with patch.dict(os.environ, {"TYPESAFE_API_KEY": "configured-but-unused"}, clear=False):
            with patch("model_effort_router.router.urllib.request.build_opener") as opener:
                result = route(input_document(), dry_run=True)
        opener.assert_not_called()
        self.assertEqual(result["reason"], "dry_run")
        self.assertFalse(result["jev_api_called"])

    def test_documented_responses_produce_a_dependency_safe_route(self) -> None:
        result = route(input_document(), client=documented_response)
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["waves"], [["implement"], ["verify"]])
        self.assertEqual(len(result["assignments"]), 2)
        self.assertEqual(result["signals"]["assignment"]["answers"]["verify"]["confidence"], 0.9)
        self.assertEqual(result["signals"]["assignment"]["usage"]["input_tokens"], 10)

    def test_low_confidence_stops_before_dispatch(self) -> None:
        result = route(
            input_document(),
            client=lambda payload: documented_response(payload, confidence=0.2),
        )
        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(result["assignments"], [])

    def test_cli_reads_json_from_standard_input(self) -> None:
        document = input_document()
        document["request"] = "譌･譛ｬ隱槭→噫繧貞性繧萓晞ｼ"
        environment = os.environ.copy()
        environment["TYPESAFE_API_KEY"] = ""
        environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
        environment["PYTHONIOENCODING"] = "cp932"
        completed = subprocess.run(
            [sys.executable, "-m", "model_effort_router"],
            input=json.dumps(document, ensure_ascii=True),
            text=True,
            capture_output=True,
            check=False,
            env=environment,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["status"], "decision_required")


if __name__ == "__main__":
    unittest.main()
