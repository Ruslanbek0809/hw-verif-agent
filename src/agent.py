# Core verification agent loop.

# Pattern: DUT intake → LLM call → testbench generation → iverilog compile →
# error parsing → iterative refinement → repeat until pass or max iterations.

# Architecture follows learn-claude-code s01 (agent loop) + s05 (skills loading).

import logging
import time
import tempfile
from pathlib import Path
from dataclasses import dataclass, field

from src.llm_client import LLMClient
from src.skill_loader import SkillLoader
from src.prompts import (
    build_system_prompt,
    build_generation_prompt,
    build_refinement_prompt,
)
from tools.iverilog import iverilog_compile, vvp_simulate

logger = logging.getLogger(__name__)


@dataclass
class TaskResult:
    task_name: str
    success: bool
    iterations: int
    compile_pass: bool = False
    functional_pass: bool = False
    final_testbench: str = ""
    error_log: list[str] = field(default_factory=list)
    token_usage: list[dict] = field(default_factory=list)


# Autonomous testbench generation agent.
class VerificationAgent:
    # The agent takes a Verilog DUT, generates a testbench via LLM, compiles it with iverilog, and iteratively refines on errors.
    # Skills are loaded on-demand into the LLM context during refinement (Layer 2 injection per learn-claude-code s05 pattern).

    def __init__(
        self,
        llm_client: LLMClient,
        skill_loader: SkillLoader | None = None,
        max_iterations: int = 5,
        timeout_seconds: int = 120,
        work_dir: Path | None = None,
        iverilog_path: str = "iverilog",
        vvp_path: str = "vvp",
    ):
        self.llm = llm_client
        self.skills = skill_loader
        self.max_iterations = max_iterations
        self.timeout_seconds = timeout_seconds
        self.work_dir = work_dir or Path(tempfile.mkdtemp(prefix="hwverif_"))
        self.iverilog_path = iverilog_path
        self.vvp_path = vvp_path

    # Run the full verification loop for a single DUT. Returns a TaskResult with pass/fail status and details.
    def verify_design(
        self,
        task_name: str, # Identifier for this task (e.g., "Prob001_zero").
        dut_code: str, # Verilog source of the design under test.
        prompt_description: str, # Natural language description of the DUT.
        reference_testbench: str | None = None, # Optional golden testbench for evaluation. 
    ) -> TaskResult:
        result = TaskResult(task_name=task_name, success=False, iterations=0)
        task_dir = self.work_dir / task_name
        task_dir.mkdir(parents=True, exist_ok=True)
        start_time = time.time()

        # Detect circuit type for skill selection
        circuit_type = self._detect_circuit_type(dut_code)

        system_prompt = build_system_prompt(
            skill_descriptions=self.skills.get_descriptions() if self.skills else ""
        )

        # Load relevant skill content (Layer 2: on-demand injection)
        skill_context = self._load_relevant_skills(circuit_type)

        # Step 1: Initial testbench generation
        logger.info(f"[{task_name}] Starting testbench generation (type={circuit_type})...")
        gen_prompt = build_generation_prompt(
            dut_description=prompt_description,
            dut_code=dut_code,
            skill_context=skill_context,
        )

        response = self._safe_llm_call(system_prompt, gen_prompt)
        if response is None:
            result.error_log.append("LLM call failed during initial generation.")
            return result
        if response.usage:
            result.token_usage.append(response.usage)

        testbench_code = self._extract_verilog(response.text)
        if not testbench_code:
            result.error_log.append("Failed to extract Verilog from LLM response.")
            return result

        # Step 2: Iterative compile-and-refine loop
        for iteration in range(1, self.max_iterations + 1):
            # Check timeout
            elapsed = time.time() - start_time
            if elapsed > self.timeout_seconds:
                result.error_log.append(
                    f"Agent timeout ({self.timeout_seconds}s) at iteration {iteration}."
                )
                logger.warning(f"[{task_name}] Timeout after {elapsed:.1f}s")
                break

            result.iterations = iteration
            logger.info(f"[{task_name}] Iteration {iteration}/{self.max_iterations}")

            # Compile
            compile_result = iverilog_compile(
                testbench_code=testbench_code,
                dut_code=dut_code,
                work_dir=task_dir / f"iter_{iteration}",
                iverilog_path=self.iverilog_path,
            )

            if not compile_result.success:
                result.error_log.append(
                    f"Iter {iteration} compile error: {compile_result.output}"
                )
                logger.info(f"[{task_name}] Compile failed, refining...")

                # Load error-debug skill for refinement context
                debug_skill = self._load_skill("error-debug")

                refine_prompt = build_refinement_prompt(
                    dut_description=prompt_description,
                    dut_code=dut_code,
                    current_testbench=testbench_code,
                    error_message=compile_result.output,
                    error_type="compilation",
                    skill_context=debug_skill,
                )
                response = self._safe_llm_call(system_prompt, refine_prompt)
                if response is None:
                    result.error_log.append(f"Iter {iteration}: LLM call failed.")
                    break
                if response.usage:
                    result.token_usage.append(response.usage)

                testbench_code = self._extract_verilog(response.text)
                if not testbench_code:
                    result.error_log.append(
                        f"Iter {iteration}: Failed to extract Verilog from refinement."
                    )
                    break
                continue

            # Compilation passed
            result.compile_pass = True
            logger.info(f"[{task_name}] Compilation passed at iteration {iteration}.")

            # Simulate
            sim_result = vvp_simulate(
                binary_path=compile_result.binary_path,
                vvp_path=self.vvp_path,
            )

            if sim_result.success:
                result.functional_pass = True
                result.success = True
                result.final_testbench = testbench_code
                logger.info(f"[{task_name}] Functional pass at iteration {iteration}!")
                break

            # Simulation ran but had mismatches or other issues
            result.error_log.append(
                f"Iter {iteration} sim output: {sim_result.output[:500]}"
            )
            logger.info(
                f"[{task_name}] Simulation issues (mismatches={sim_result.mismatch_count}), refining..."
            )

            refine_prompt = build_refinement_prompt(
                dut_description=prompt_description,
                dut_code=dut_code,
                current_testbench=testbench_code,
                error_message=sim_result.output,
                error_type="simulation",
                skill_context=skill_context,
            )
            response = self._safe_llm_call(system_prompt, refine_prompt)
            if response is None:
                result.error_log.append(f"Iter {iteration}: LLM call failed.")
                break
            if response.usage:
                result.token_usage.append(response.usage)

            testbench_code = self._extract_verilog(response.text)
            if not testbench_code:
                result.error_log.append(
                    f"Iter {iteration}: Failed to extract Verilog from sim refinement."
                )
                break

        if not result.success:
            result.final_testbench = testbench_code or ""
            logger.info(f"[{task_name}] Failed after {result.iterations} iterations.")

        return result

    # Call the LLM with exception handling. Returns None on failure.
    def _safe_llm_call(self, system_prompt: str, user_prompt: str):
        try:
            return self.llm.generate(system_prompt, user_prompt)
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return None

    # Detect whether DUT is combinational or sequential from code patterns.
    def _detect_circuit_type(self, dut_code: str) -> str:
        sequential_keywords = [
            "always @(posedge",
            "always @(negedge",
            "always_ff",
            "always_latch",
            "posedge clk",
            "negedge clk",
            "posedge clock",
        ]
        code_lower = dut_code.lower()
        for kw in sequential_keywords:
            if kw.lower() in code_lower:
                return "sequential"
        return "combinational"

    # Load skill content based on circuit type (Layer 2 on-demand).
    def _load_relevant_skills(self, circuit_type: str) -> str:
        if not self.skills:
            return ""
        skill_name = (
            "sequential-verify" if circuit_type == "sequential"
            else "combinational-verify"
        )
        return self.skills.get_content(skill_name)

    # Load a specific skill by name.
    def _load_skill(self, name: str) -> str:
        if not self.skills:
            return ""
        return self.skills.get_content(name)

    # Extract Verilog code from LLM response (between ```verilog blocks).
    def _extract_verilog(self, text: str) -> str | None:
        if "```verilog" in text:
            parts = text.split("```verilog")
            if len(parts) > 1:
                code = parts[1].split("```")[0].strip()
                if code:
                    return code
        if "```systemverilog" in text:
            parts = text.split("```systemverilog")
            if len(parts) > 1:
                code = parts[1].split("```")[0].strip()
                if code:
                    return code
        if "```sv" in text:
            parts = text.split("```sv")
            if len(parts) > 1:
                code = parts[1].split("```")[0].strip()
                if code:
                    return code
        if "```" in text:
            parts = text.split("```")
            if len(parts) >= 3:
                code = parts[1].strip()
                if "module" in code or "initial" in code:
                    return code
        # Try raw: if the response looks like pure Verilog
        if "module" in text and "endmodule" in text:
            return text.strip()
        return None
