
import logging
import time
from pathlib import Path
from dataclasses import dataclass, field

from src.llm_client import LLMClient
from src.prompts import build_system_prompt, build_generation_prompt
from tools.iverilog import iverilog_compile, vvp_simulate

logger = logging.getLogger(__name__)


@dataclass
class BaselineResult:
    task_name: str
    success: bool
    compile_pass: bool = False
    functional_pass: bool = False
    final_testbench: str = ""
    error_log: list[str] = field(default_factory=list)
    token_usage: list[dict] = field(default_factory=list)
    latency_seconds: float = 0.0


class BaselineAgent:
    """Single-call baseline: one LLM call, one compile attempt, no refinement."""

    def __init__(
        self,
        llm_client: LLMClient,
        work_dir: Path,
        iverilog_path: str = "iverilog",
        vvp_path: str = "vvp",
    ):
        self.llm = llm_client
        self.work_dir = work_dir
        self.iverilog_path = iverilog_path
        self.vvp_path = vvp_path

    def run(
        self,
        task_name: str,
        dut_code: str,
        prompt_description: str,
    ) -> BaselineResult:
        result = BaselineResult(task_name=task_name, success=False)
        task_dir = self.work_dir / task_name
        task_dir.mkdir(parents=True, exist_ok=True)
        start = time.time()

        # Single LLM call — no skills, no RAG, no refinement
        system_prompt = build_system_prompt()
        gen_prompt = build_generation_prompt(
            dut_description=prompt_description,
            dut_code=dut_code,
        )

        try:
            response = self.llm.generate(system_prompt, gen_prompt)
        except Exception as e:
            result.error_log.append(f"LLM call failed: {e}")
            return result

        if response.usage:
            result.token_usage.append(response.usage)

        testbench_code = self._extract_verilog(response.text)
        if not testbench_code:
            result.error_log.append("Failed to extract Verilog from LLM response.")
            return result

        result.final_testbench = testbench_code

        # Single compile attempt
        compile_result = iverilog_compile(
            testbench_code=testbench_code,
            dut_code=dut_code,
            work_dir=task_dir / "iter_1",
            iverilog_path=self.iverilog_path,
        )

        if not compile_result.success:
            result.error_log.append(f"Compile error: {compile_result.output}")
            result.latency_seconds = time.time() - start
            return result

        result.compile_pass = True

        # Single simulation attempt
        sim_result = vvp_simulate(
            binary_path=compile_result.binary_path,
            vvp_path=self.vvp_path,
        )

        if sim_result.success:
            result.functional_pass = True
            result.success = True

        result.latency_seconds = time.time() - start
        return result

    def _extract_verilog(self, text: str) -> str | None:
        for fence in ["```verilog", "```systemverilog", "```sv"]:
            if fence in text:
                parts = text.split(fence)
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
        if "module" in text and "endmodule" in text:
            return text.strip()
        return None