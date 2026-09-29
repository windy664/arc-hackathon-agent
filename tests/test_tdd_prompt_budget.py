import ast
import pathlib
import unittest

from agents.context.prompts.test_driven_developer import get_system_prompt, get_user_prompt


ROOT = pathlib.Path(__file__).resolve().parents[1]


class TDDPromptBudgetTests(unittest.TestCase):
    def test_prompts_match_the_runtime_budget_and_stop_on_exhaustion(self):
        module = ast.parse((ROOT / "core" / "phases.py").read_text(encoding="utf-8"))
        budget = next(
            node.value.value
            for node in module.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "TDD_RUN_TESTS_BUDGET" for target in node.targets)
            and isinstance(node.value, ast.Constant)
        )
        system = get_system_prompt()
        user = get_user_prompt(
            node_id="REQ-1-1-1",
            dynamic_context="",
            test_files=["backend/tests/example.test.js"],
            test_type="Unit",
            node_tests=[{"type": "Unit", "file_path": "backend/tests/example.test.js"}],
        )

        self.assertIn(f"at most {budget} run_tests calls", system)
        self.assertIn(f"budget of {budget} calls", user)
        self.assertIn("immediately return", user)
        self.assertNotIn("budget of 10 calls", user)


if __name__ == "__main__":
    unittest.main()
