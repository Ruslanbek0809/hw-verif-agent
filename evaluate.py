# Runs baseline vs agent on VerilogEval tasks and compares results.
#
# Usage:
#   python evaluate.py --mode baseline         # baseline only
#   python evaluate.py --mode agent            # agent only
#   python evaluate.py --mode both             # compare both (default)
#   python evaluate.py --mode both --range 1 10
#   python evaluate.py --mode both --task Prob001_zero

import argparse
import json
import logging
from pathlib import Path
from datetime import datetime

import yaml
from dotenv import load_dotenv

from src.llm_client import LLMClient
from src.agent import VerificationAgent
from src.baseline import BaselineAgent
from src.skill_loader import SkillLoader

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent


def load_config(config_file=None):
    path = Path(config_file) if config_file else PROJECT_ROOT / "config" / "config.yaml"
    with open(path) as f:
        return yaml.safe_load(f)


def normalize_dut_module_name(code: str, target_name: str = "TopModule") -> str:
    import re
    return re.sub(r'\bmodule\s+RefModule\b', f'module {target_name}', code)


def load_task(dataset_dir: Path, task_name: str) -> dict | None:
    prompt_file = dataset_dir / f"{task_name}_prompt.txt"
    ref_file    = dataset_dir / f"{task_name}_ref.sv"
    test_file   = dataset_dir / f"{task_name}_test.sv"

    if not prompt_file.exists():
        logger.error(f"Task not found: {prompt_file}")
        return None

    dut_code = normalize_dut_module_name(
        ref_file.read_text().strip() if ref_file.exists() else ""
    )
    return {
        "name": task_name,
        "description": prompt_file.read_text().strip(),
        "dut_code": dut_code,
        "golden_testbench": test_file.read_text().strip() if test_file.exists() else "",
    }


def get_task_list(dataset_dir: Path) -> list[str]:
    return sorted(
        f.stem.replace("_prompt", "")
        for f in dataset_dir.glob("*_prompt.txt")
    )


def print_summary(label: str, results: list):
    total = len(results)
    cp = sum(1 for r in results if r.compile_pass)
    fp = sum(1 for r in results if r.functional_pass)
    logger.info(f"  [{label}] Compile:  {cp}/{total} ({100*cp/total:.1f}%)")
    logger.info(f"  [{label}] Functional: {fp}/{total} ({100*fp/total:.1f}%)")


def main():
    parser = argparse.ArgumentParser(description="Task C: Evaluation Pipeline")
    parser.add_argument("--mode", choices=["baseline", "agent", "both"], default="both")
    parser.add_argument("--task", type=str)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--range", nargs=2, type=int)
    parser.add_argument("--config", type=str, default=None)
    args = parser.parse_args()

    load_dotenv(PROJECT_ROOT / "config" / ".env")
    config = load_config(args.config)

    # Dataset
    dataset_dir = Path(config["evaluation"]["dataset_path"])
    if not dataset_dir.is_absolute():
        dataset_dir = (PROJECT_ROOT / dataset_dir).resolve()
    if not dataset_dir.exists():
        logger.error(f"Dataset not found: {dataset_dir}")
        return

    # Tasks
    all_tasks = get_task_list(dataset_dir)
    logger.info(f"Found {len(all_tasks)} tasks.")

    if args.task:
        tasks_to_run = [args.task]
    elif args.range:
        s, e = args.range
        tasks_to_run = all_tasks[s-1:e]
    elif args.all:
        tasks_to_run = all_tasks
    else:
        tasks_to_run = all_tasks[:1]  # smoke test

    logger.info(f"Running {len(tasks_to_run)} task(s) in mode='{args.mode}'...")

    # Shared components
    llm_client = LLMClient(
        provider=config["llm"]["provider"],
        model=config["llm"]["model"],
        temperature=config["llm"]["temperature"],
        max_tokens=config["llm"]["max_tokens"],
    )

    work_dir = PROJECT_ROOT / config["tools"]["work_dir"]
    work_dir.mkdir(parents=True, exist_ok=True)

    baseline_results = []
    agent_results = []

    # --- Baseline ---
    if args.mode in ("baseline", "both"):
        logger.info("=" * 60)
        logger.info("BASELINE RUN (single LLM call, no refinement)")
        logger.info("=" * 60)

        baseline = BaselineAgent(
            llm_client=llm_client,
            work_dir=work_dir / "baseline",
            iverilog_path=config["tools"]["iverilog_path"],
            vvp_path=config["tools"]["vvp_path"],
        )

        for task_name in tasks_to_run:
            task = load_task(dataset_dir, task_name)
            if not task:
                continue
            r = baseline.run(
                task_name=task["name"],
                dut_code=task["dut_code"],
                prompt_description=task["description"],
            )
            baseline_results.append(r)
            status = "PASS" if r.success else "FAIL"
            logger.info(
                f"  {task_name}: {status} "
                f"(compile={r.compile_pass}, functional={r.functional_pass})"
            )

    # --- Agent ---
    if args.mode in ("agent", "both"):
        logger.info("=" * 60)
        logger.info("AGENT RUN (iterative refinement loop)")
        logger.info("=" * 60)

        skill_loader = SkillLoader(PROJECT_ROOT / config["skills"]["directory"])
        agent = VerificationAgent(
            llm_client=llm_client,
            skill_loader=skill_loader,
            max_iterations=config["agent"]["max_iterations"],
            timeout_seconds=config["agent"].get("timeout_seconds", 120),
            work_dir=work_dir / "agent",
            iverilog_path=config["tools"]["iverilog_path"],
            vvp_path=config["tools"]["vvp_path"],
        )

        for task_name in tasks_to_run:
            task = load_task(dataset_dir, task_name)
            if not task:
                continue
            r = agent.verify_design(
                task_name=task["name"],
                dut_code=task["dut_code"],
                prompt_description=task["description"],
                reference_testbench=task["golden_testbench"],
            )
            agent_results.append(r)
            status = "PASS" if r.success else "FAIL"
            logger.info(
                f"  {task_name}: {status} "
                f"(compile={r.compile_pass}, functional={r.functional_pass}, iters={r.iterations})"
            )

    # --- Summary ---
    logger.info("=" * 60)
    logger.info(f"SUMMARY — {len(tasks_to_run)} task(s)")
    if baseline_results:
        print_summary("BASELINE", baseline_results)
    if agent_results:
        print_summary("AGENT", agent_results)
    logger.info("=" * 60)

    # --- Save results ---
    results_dir = PROJECT_ROOT / config["evaluation"]["results_dir"]
    results_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    def serialize(r):
        return {
            "name": r.task_name,
            "success": r.success,
            "compile_pass": r.compile_pass,
            "functional_pass": r.functional_pass,
            "errors": r.error_log,
            "token_usage": r.token_usage,
            "final_testbench": r.final_testbench,
        }

    output = {
        "timestamp": timestamp,
        "mode": args.mode,
        "tasks": tasks_to_run,
        "baseline": [serialize(r) for r in baseline_results],
        "agent": [serialize(r) for r in agent_results],
        "summary": {
            "baseline": {
                "compile_pass": sum(1 for r in baseline_results if r.compile_pass),
                "functional_pass": sum(1 for r in baseline_results if r.functional_pass),
                "total": len(baseline_results),
            },
            "agent": {
                "compile_pass": sum(1 for r in agent_results if r.compile_pass),
                "functional_pass": sum(1 for r in agent_results if r.functional_pass),
                "total": len(agent_results),
            },
        },
    }

    out_file = results_dir / f"eval_{args.mode}_{timestamp}.json"
    out_file.write_text(json.dumps(output, indent=2))
    logger.info(f"Results saved: {out_file}")


if __name__ == "__main__":
    main()