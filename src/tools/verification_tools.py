import os
import subprocess
import tempfile
import sys
import json
from typing import Annotated
from langchain_core.tools import tool
from langchain_core.tools.base import InjectedToolCallId
from langgraph.types import Command
from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import InjectedState
from pydantic import BaseModel, Field
from typing import Literal, Optional
from src.utils.skills import get_skill_content

@tool
def save_testbench_code(tb_code: str) -> str:
    """Saves the SystemVerilog testbench code to be simulated later.
    You MUST call this before running run_simulation if you generated a new testbench.
    Args:
        tb_code: The SystemVerilog testbench source code.
    """
    os.makedirs("data", exist_ok=True)
    with open("data/tb.sv", "w") as f:
        f.write(tb_code)
    return "Testbench code saved successfully to data/tb.sv"

@tool
def run_simulation() -> str:
    """Compiles the testbench (data/tb.sv) and DUT (data/dut.sv) using Icarus Verilog and simulates it.
    Returns the simulation output or compilation errors.
    """
    if not os.path.exists("data/dut.sv"):
        return "Error: data/dut.sv not found. The DUT code must be present."
    if not os.path.exists("data/tb.sv"):
        return "Error: data/tb.sv not found. You must generate and save the testbench code first."
        
    with tempfile.TemporaryDirectory() as temp_dir:
        vvp_file = os.path.join(temp_dir, "sim.vvp")
        
        # Compile
        compile_cmd = ["iverilog", "-g2012", "-o", vvp_file, "data/dut.sv", "data/tb.sv"]
        try:
            subprocess.run(compile_cmd, capture_output=True, text=True, check=True, timeout=60)
        except subprocess.TimeoutExpired:
            return "COMPILATION TIMED OUT."
        except subprocess.CalledProcessError as e:
            return f"COMPILATION FAILED:\n{e.stderr}\n{e.stdout}"
            
        # Simulate
        sim_cmd = ["vvp", vvp_file]
        try:
            sim_res = subprocess.run(sim_cmd, capture_output=True, text=True, check=True, timeout=60)
            output = sim_res.stdout
            if "error" in output.lower() or "fatal" in output.lower():
                return f"SIMULATION RAN BUT REPORTED ERRORS:\n{output}"
            else:
                return f"SIMULATION SUCCESSFUL:\n{output}"
        except subprocess.TimeoutExpired:
            return "SIMULATION TIMED OUT (Possible infinite loop in TB)."
        except subprocess.CalledProcessError as e:
            return f"SIMULATION FAILED AT EXECUTION:\n{e.stderr}\n{e.stdout}"

@tool
def save_checker_code(checker_code: str) -> str:
    """Saves the Python checker script to be run later.
    Args:
        checker_code: The complete Python script to verify the simulation output.
    """
    os.makedirs("data", exist_ok=True)
    with open("data/checker.py", "w") as f:
        f.write(checker_code)
    return "Checker code saved successfully to data/checker.py"

@tool
def run_python_checker() -> str:
    """Runs the python checker script against the generated driver_output.csv.
    Returns the checker output.
    """
    if not os.path.exists("data/checker.py"):
        return "Error: data/checker.py not found. You must generate and save the checker code first."
    if not os.path.exists("driver_output.csv"):
        return "Error: driver_output.csv not found. Did the simulation run successfully and generate the file?"
        
    checker_cmd = ["python", "data/checker.py", "driver_output.csv"]
    try:
        checker_output = subprocess.run(checker_cmd, capture_output=True, text=True, check=True)
        lines = checker_output.stdout.splitlines()
        if len(lines) > 50:
            stdout_str = "\n".join(lines[:50]) + f"\n\n... (additional {len(lines) - 50} lines are truncated) ..."
        else:
            stdout_str = checker_output.stdout
        return f"CHECKER RAN SUCCESSFULLY:\n{stdout_str}"
    except subprocess.CalledProcessError as e:
        lines = e.stdout.splitlines()
        if len(lines) > 50:
            stdout_str = "\n".join(lines[:50]) + f"\n\n... (additional {len(lines) - 50} lines are truncated) ..."
        else:
            stdout_str = e.stdout
        return f"CHECKER FAILED:\n{e.stderr}\n{stdout_str}"

@tool
def read_file(filepath: str) -> str:
    """Reads and returns the contents of a file."""
    try:
        with open(filepath, "r") as f:
            content = f.read()
            # Truncate if too long
            if len(content) > 500:
                return content[:300] + "\n\n... (truncated due to length) ...\n\n" + content[-300:]
            return content
    except FileNotFoundError:
        return f"Error: File {filepath} not found."

class ManageTasksInput(BaseModel):
    action: Literal["add", "complete", "view", "clear"] = Field(description="The action to perform.")
    task_id: Optional[str] = Field(default="", description="A short, unique string ID for the task (required for 'add' and 'complete'). Example: 'write_tb'.")
    description: Optional[str] = Field(default="", description="The description of the task (required for 'add').")

@tool(args_schema=ManageTasksInput)
def manage_tasks(
    action: str, 
    tool_call_id: Annotated[str, InjectedToolCallId], 
    state: Annotated[dict, InjectedState],
    task_id: str = "", 
    description: str = ""
) -> Command:
    """A tool to manage a multi-step task list to help you stay organized and on-track."""
    current_tasks = state.get("tasks", {})
    update_dict = {}
    msg = ""

    if action == "add":
        if not task_id:
            msg = "Error: task_id is required for 'add'."
        else:
            update_dict[task_id] = {"desc": description, "status": "open"}
            msg = f"Task added with ID '{task_id}': '{description}'"
    elif action == "complete":
        if not task_id:
            msg = "Error: task_id is required for 'complete'."
        elif task_id not in current_tasks:
            msg = f"Error: Task ID '{task_id}' not found."
        else:
            update_dict[task_id] = {"desc": current_tasks[task_id]["desc"], "status": "completed"}
            msg = f"Task '{task_id}' marked as completed."
    elif action == "clear":
        update_dict["__clear__"] = True
        msg = "All tasks cleared."
    elif action == "view":
        pass
    else:
        msg = f"Error: Unknown action '{action}'"
        
    if action == "view" or not msg.startswith("Error"):
        # Combine current state with planned updates to show the immediate result
        merged_tasks = {**current_tasks, **update_dict}
        if merged_tasks.get("__clear__"):
            merged_tasks = {}
            
        view_str = "CURRENT TASKS:\n"
        tasks_found = False
        for k, v in merged_tasks.items():
            if k == "__clear__": continue
            tasks_found = True
            mark = "X" if v["status"] == "completed" else " "
            view_str += f" [{mark}] {k}: {v['desc']}\n"
            
        if not tasks_found:
            view_str += "(No tasks)"
            
        msg = f"{msg}\n\n{view_str}".strip()

    return Command(update={
        "tasks": update_dict,
        "messages": [ToolMessage(content=msg, tool_call_id=tool_call_id)]
    })

@tool
def load_skill(skill_name: str) -> str:
    """Load specialized knowledge using the skill name."""
    return get_skill_content(skill_name)

# List of tools available to the agent
tools = [
    save_testbench_code,
    run_simulation,
    save_checker_code,
    run_python_checker,
    read_file,
    manage_tasks,
    load_skill
]