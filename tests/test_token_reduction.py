"""Reproducibility checks for the checked-in token measurement and chart."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
HAS_TIKTOKEN = importlib.util.find_spec("tiktoken") is not None


@unittest.skipUnless(HAS_TIKTOKEN, "install the benchmark extra to validate token counts")
class TokenReductionTests(unittest.TestCase):
    def test_checked_in_measurement_matches_script(self) -> None:
        from scripts.measure_token_reduction import measure, render_svg

        document = json.loads((ROOT / "examples" / "request.json").read_text(encoding="utf-8"))
        expected = json.loads(
            (ROOT / "docs" / "token-reduction-results.json").read_text(encoding="utf-8")
        )
        measured = measure(document)
        self.assertEqual(measured, expected)
        ET.fromstring(render_svg(measured))


if __name__ == "__main__":
    unittest.main()
