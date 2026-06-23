from src.graph import build_graph
from langchain_core.messages import HumanMessage
from src.utils.skills import get_skills_summary_string
import sys
import glob
import os

def dump_history_to_file(history: list, filepath: str):
    """Utility function to dump chat history to a file."""
    with open(filepath, "w") as f:
        for msg in history:
            f.write(f"--- {msg.__class__.__name__} ---\n")
            f.write(f"{repr(msg)}\n\n")

def run_sample():
    print("Initializing LangGraph Application...")
    app = build_graph()
    
    # Parse command line argument test=X
    test_id = 1 # default
    for arg in sys.argv[1:]:
        if arg.startswith("test="):
            try:
                test_id = int(arg.split("=")[1])
            except ValueError:
                print("Invalid test ID format. Use test=NUMBER")
                sys.exit(1)
                
    # Find dataset files
    pattern = os.path.join("dataset", f"Prob{test_id:03d}_*_ifc.txt")
    ifc_files = glob.glob(pattern)
    if not ifc_files:
        print(f"No dataset files found for test ID {test_id}")
        sys.exit(1)
        
    ifc_file = ifc_files[0]
    base_name = ifc_file[:-8] # remove "_ifc.txt"
    
    prompt_file = base_name + "_prompt.txt"
    ref_file = base_name + "_ref.sv"
    
    try:
        with open(prompt_file, 'r') as f:
            dut_description = f.read()
        with open(ifc_file, 'r') as f:
            dut_headers = f.read()
        with open(ref_file, 'r') as f:
            dut_code = f.read()
    except FileNotFoundError as e:
        print(f"Error reading dataset files: {e}")
        sys.exit(1)

    # We must write the DUT code to data/dut.sv so that the simulation tool can compile it.
    os.makedirs("data", exist_ok=True)
    with open("data/dut.sv", "w") as f:
        f.write(dut_code)

    initial_state = {
        "messages": [HumanMessage(content="Start the verification process.")],
        "tasks": {},
        "test_subject_id": test_id,
        "dut_description": dut_description,
        "dut_headers": dut_headers,
        "dut_code": dut_code,
        "context": "",
        "skills_summary": get_skills_summary_string(),
        "csv_format": "",
        "max_revisions": 3,
        "driver_revision_number": 0,
        "checker_revision_number": 0,
    }
    
    print("Starting agent execution...")
    # Invoke the graph
    final_state = app.invoke(initial_state, {"recursion_limit": 50})

    print("\n\n" + "="*50)
    print("FINAL EXECUTION RESULTS")
    print("="*50)
    
    if final_state and "messages" in final_state:
        dump_history_to_file(final_state["messages"], f"data/agent_messages_{test_id}.txt")
        last_message = final_state["messages"][-1]
        print(f"Final Message:\n{last_message.content}")
    print("="*50)

if __name__ == "__main__":
    run_sample()