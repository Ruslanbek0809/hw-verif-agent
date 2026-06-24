import os
import subprocess
import tempfile 
from typing import Annotated
from langchain_core.tools import tool
from langchain_core.tools.base import InjectedToolCallId
from langgraph.types import Command
from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import InjectedState
from pydantic import BaseModel, Field
from typing import Literal, Optional
from src.utils.skills import get_skill_content

def get_data_dir(state: dict) -> str:
    """Helper to get the data directory for the current test_subject_id."""
    test_id = state.get("test_subject_id", 1)
    return os.path.join("data", str(test_id))

def resolve_data_path(filename: str, state: dict) -> str:
    """Helper to resolve a filename relative to the 'data/<test_subject_id>' directory."""
    safe_filename = os.path.basename(filename)
    data_dir = get_data_dir(state)
    return os.path.join(data_dir, safe_filename)

@tool
def run_simulation(state: Annotated[dict, InjectedState]) -> str:
    """Compiles the testbench (tb.sv) and DUT (dut.sv) using Icarus Verilog and simulates it.
    Returns the simulation output or compilation errors.
    """
    data_dir = get_data_dir(state)
    dut_path = os.path.join(data_dir, "dut.sv")
    tb_path = os.path.join(data_dir, "tb.sv")
    
    if not os.path.exists(dut_path):
        return f"Error: {dut_path} not found. The DUT code must be present."
    if not os.path.exists(tb_path):
        return f"Error: {tb_path} not found. You must generate and save the testbench code first."
        
    with tempfile.TemporaryDirectory() as temp_dir:
        vvp_file = os.path.join(temp_dir, "sim.vvp")
        
        # Compile
        compile_cmd = ["iverilog", "-g2012", "-o", vvp_file, dut_path, tb_path]
        try:
            subprocess.run(compile_cmd, capture_output=True, text=True, check=True, timeout=60)
        except subprocess.TimeoutExpired:
            return "COMPILATION TIMED OUT."
        except subprocess.CalledProcessError as e:
            return f"COMPILATION FAILED:\n{e.stderr}\n{e.stdout}"
            
        # Simulate (run with CWD set to data_dir so driver_output.csv is written there)
        sim_cmd = ["vvp", vvp_file]
        try:
            sim_res = subprocess.run(sim_cmd, capture_output=True, text=True, check=True, timeout=60, cwd=data_dir)
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
def run_python_checker(state: Annotated[dict, InjectedState]) -> str:
    """Runs the python checker script `checker.py` against the generated `driver_output.csv`.
    Returns the checker output.
    """
    data_dir = get_data_dir(state)
    checker_file = os.path.join(data_dir, "checker.py")
    csv_file = os.path.join(data_dir, "driver_output.csv")
    
    if not os.path.exists(checker_file):
        return f"Error: {checker_file} not found. You must generate and save the checker code first."
    if not os.path.exists(csv_file):
        return f"Error: {csv_file} not found. Did the simulation run successfully and generate the file?"
        
    # Run the Python checker with CWD set to data_dir so checker can load local files if needed,
    # and pass the csv filename 'driver_output.csv' as the argument.
    checker_cmd = ["python", "checker.py", "driver_output.csv"]
    try:
        checker_output = subprocess.run(checker_cmd, capture_output=True, text=True, check=True, cwd=data_dir)
        lines = checker_output.stdout.splitlines()
        if len(lines) > 50:
            stdout_str = "\n".join(lines[:50]) + f"\n\n... (additional {len(lines) - 50} lines are truncated) ..."
        else:
            stdout_str = checker_output.stdout
        print(stdout_str)
        return f"CHECKER Output:\n{stdout_str}"
    except subprocess.CalledProcessError as e:
        lines = e.stdout.splitlines()
        if len(lines) > 50:
            stdout_str = "\n".join(lines[:50]) + f"\n\n... (additional {len(lines) - 50} lines are truncated) ..."
        else:
            stdout_str = e.stdout
        return f"CHECKER FAILED:\n{e.stderr}\n{stdout_str}"

@tool
def read_file(filename: str, state: Annotated[dict, InjectedState]) -> str:
    """Reads and returns the contents of a file in the data folder of the current test."""
    try:
        resolved_path = resolve_data_path(filename, state)
        with open(resolved_path, "r") as f:
            content = f.read()
            # Truncate if too long (raised threshold to 10000 characters to prevent test plan truncation)
            if len(content) > 10000:
                return content[:3000] + "\n\n... (truncated due to length) ...\n\n" + content[-3000:]
            return content
    except FileNotFoundError:
        return f"Error: File '{filename}' not found."

@tool
def write_file(filename: str, content: str, state: Annotated[dict, InjectedState]) -> str:
    """Writes the specified content to a file in the data folder of the current test.
    Args:
        filename: The name of the file.
        content: The text content to write.
    """
    try:
        if filename == "dut.sv":
            return "Error: You are not allowed to overwrite 'dut.sv'. This file is already provided."
            
        resolved_path = resolve_data_path(filename, state)
        dirname = os.path.dirname(resolved_path)
        if dirname:
            os.makedirs(dirname, exist_ok=True)
        with open(resolved_path, "w") as f:
            f.write(content)
        return f"File '{filename}' written successfully."
    except Exception as e:
        return f"Error writing file '{filename}': {str(e)}"

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
    run_simulation,
    run_python_checker,
    read_file,
    write_file,
    manage_tasks,
    load_skill
]