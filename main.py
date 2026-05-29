#!/usr/bin/env python3

# Hardware Verification Agent. Main entry point. Runs the agent on one or more VerilogEval tasks.

# Usage:
#     python main.py                          # Run on first task as smoke test
#     python main.py --task Prob001_zero      # Run on specific task
#     python main.py --all                    # Run on all 156 tasks
#     python main.py --range 1 10            # Run on tasks 1-10

import argparse
import json
import logging
from pathlib import Path
from datetime import datetime

import yaml
from dotenv import load_dotenv

from src.llm_client import LLMClient
from src.agent import VerificationAgent
from src.skill_loader import SkillLoader

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent


# Load configuration from YAML file.    
def load_config(config_file: str | None = None) -> dict:
    if config_file:
        config_path = Path(config_file)
    else:
        config_path = PROJECT_ROOT / "config" / "config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


# Rename the DUT module to `target_name` for consistent testbench instantiation. VerilogEval _ref.sv files use 'RefModule' but our testbenches instantiate 'TopModule'.
def normalize_dut_module_name(code: str, target_name: str = "TopModule") -> str:
    import re
    code = re.sub(
        r'\bmodule\s+RefModule\b',
        f'module {target_name}',
        code,
    )
    return code


# Load a single VerilogEval task (prompt, reference, testbench).
def load_task(dataset_dir: Path, task_name: str) -> dict | None:
    prompt_file = dataset_dir / f"{task_name}_prompt.txt"
    ref_file = dataset_dir / f"{task_name}_ref.sv"
    test_file = dataset_dir / f"{task_name}_test.sv"

    if not prompt_file.exists():
        logger.error(f"Task not found: {prompt_file}")
        return None

    dut_code = ref_file.read_text().strip() if ref_file.exists() else ""
    dut_code = normalize_dut_module_name(dut_code)

    return {
        "name": task_name,
        "description": prompt_file.read_text().strip(),
        "dut_code": dut_code,
        "golden_testbench": test_file.read_text().strip() if test_file.exists() else "",
    }


# Get sorted list of all task names from the dataset directory.
def get_task_list(dataset_dir: Path) -> list[str]:
    tasks = set()
    for f in dataset_dir.glob("*_prompt.txt"):
        task_name = f.stem.replace("_prompt", "")
        tasks.add(task_name)
    return sorted(tasks)


# Main entry point. Parses command line arguments and runs the agent.
def main():
    parser = argparse.ArgumentParser(description="Hardware Verification Agent")
    parser.add_argument("--task", type=str, help="Specific task name to run")
    parser.add_argument("--all", action="store_true", help="Run on all tasks")
    parser.add_argument("--range", nargs=2, type=int, help="Task range (start end)")
    parser.add_argument("--config", type=str, default=None, help="Config file path")
    args = parser.parse_args()

    # Load environment variables and configuration.
    load_dotenv(PROJECT_ROOT / "config" / ".env")
    config = load_config(args.config)

    # Resolve the dataset path.
    dataset_dir = Path(config["evaluation"]["dataset_path"])
    if not dataset_dir.is_absolute():
        dataset_dir = (PROJECT_ROOT / dataset_dir).resolve()

    if not dataset_dir.exists():
        logger.error(f"Dataset directory not found: {dataset_dir}")
        return

    # Initialize the components.
    llm_client = LLMClient(
        provider=config["llm"]["provider"],
        model=config["llm"]["model"],
        temperature=config["llm"]["temperature"],
        max_tokens=config["llm"]["max_tokens"],
    )

    skill_loader = SkillLoader(PROJECT_ROOT / config["skills"]["directory"])

    work_dir = PROJECT_ROOT / config["tools"]["work_dir"]
    work_dir.mkdir(parents=True, exist_ok=True)

    agent = VerificationAgent(
        llm_client=llm_client,
        skill_loader=skill_loader,
        max_iterations=config["agent"]["max_iterations"],
        timeout_seconds=config["agent"].get("timeout_seconds", 120),
        work_dir=work_dir,
        iverilog_path=config["tools"]["iverilog_path"],
        vvp_path=config["tools"]["vvp_path"],
    )

    # Determine which tasks to run.
    all_tasks = get_task_list(dataset_dir)
    logger.info(f"Found {len(all_tasks)} tasks in dataset.")

    if args.task:
        tasks_to_run = [args.task]
    elif args.range:
        start, end = args.range
        tasks_to_run = all_tasks[start - 1 : end]
    elif args.all:
        tasks_to_run = all_tasks
    else:
        tasks_to_run = all_tasks[:1]

    # Run the agent.
    results = []
    logger.info(f"Running agent on {len(tasks_to_run)} task(s)...")

    for task_name in tasks_to_run:
        task_data = load_task(dataset_dir, task_name)
        if not task_data:
            continue

        result = agent.verify_design(
            task_name=task_data["name"],
            dut_code=task_data["dut_code"],
            prompt_description=task_data["description"],
            reference_testbench=task_data["golden_testbench"],
        )
        results.append(result)
        status = "PASS" if result.success else "FAIL"
        logger.info(
            f"  {task_name}: {status} (compile={result.compile_pass}, "
            f"functional={result.functional_pass}, iters={result.iterations})"
        )

    # Summary
    total = len(results)
    compile_pass = sum(1 for r in results if r.compile_pass)
    functional_pass = sum(1 for r in results if r.functional_pass)

    logger.info("=" * 60)
    logger.info(f"RESULTS: {total} tasks")
    if total > 0:
        logger.info(f"  Compilation pass rate: {compile_pass}/{total} ({100*compile_pass/total:.1f}%)")
        logger.info(f"  Functional pass rate:  {functional_pass}/{total} ({100*functional_pass/total:.1f}%)")
    else:
        logger.info("  No tasks were executed.")
    logger.info("=" * 60)

    # Save results
    results_dir = PROJECT_ROOT / config["evaluation"]["results_dir"]
    results_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = results_dir / f"results_{timestamp}.json"

    results_data = {
        "timestamp": timestamp,
        "config": config,
        "summary": {
            "total": total,
            "compile_pass": compile_pass,
            "functional_pass": functional_pass,
        },
        "tasks": [
            {
                "name": r.task_name,
                "success": r.success,
                "compile_pass": r.compile_pass,
                "functional_pass": r.functional_pass,
                "iterations": r.iterations,
                "errors": r.error_log,
                "token_usage": r.token_usage,
                "final_testbench": r.final_testbench,
            }
            for r in results
        ],
    }
    results_file.write_text(json.dumps(results_data, indent=2))
    logger.info(f"Results saved to: {results_file}")


if __name__ == "__main__":
    main()
