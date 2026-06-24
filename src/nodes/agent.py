from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.types import Command

from src.state import AgentState
from src.utils.llm import get_llm
from src.tools.verification_tools import tools

def agent_node(state: AgentState):
    """The central agent node that reasons and calls tools."""
    new_msgs = []
    for msg in reversed(state["messages"]):
        if msg.__class__.__name__ == "AIMessage":
            break
        new_msgs.insert(0, msg)
        
    for msg in new_msgs:
        print(f"\n[{msg.__class__.__name__}]:\n{msg.content}\n")
    
    llm = get_llm()
    # Bind tools to the LLM
    llm_with_tools = llm.bind_tools(tools)
    
    # Construct System Prompt
    system_prompt = f"""You are an expert autonomous hardware verification agent.
Your goal is to test the given SystemVerilog Design Under Test (DUT) using a hybrid approach. You will write two separate pieces of code: a driver (in SystemVerilog) that drives the DUT and stores the stimulus and responses to a CSV file, and a checker (in Python) that implements a reference model of the DUT and verifies the DUT outputs from the CSV file against the reference model outputs for each input.

Verification Workflow:

1. Analyze the DUT description and headers, and create a comprehensive test plan with filename `test_plan.md`. The test plan should outline the complete set of test scenarios, edge cases, and any other specific cases you are going to test in the DUT. You must also use the task manager tool to create a task checklist to track your execution progress.

2. Implement a hybrid testbench strategy using your test plan as the single source of truth.

3. Create the SystemVerilog testbench (driver) with filename `tb.sv` that instantiates the DUT, drives stimulus covering all stimuli as per the test plan, and logs all inputs and outputs in a file called `driver_output.csv`.

4. Execute the `tb.sv` simulation and check for any compilation or simulation errors. Fix them if any.

5. Create a Python checker with the filename `checker.py` that models the expected behavior of the DUT, parses `driver_output.csv`, and compares the results of the DUT with the expected outputs from the reference model.

6. Execute the Python checker to evaluate correctness. Iterate on fixing any issues in the checker using execution feedback.

Important: The DUT code is already developed and present in the file 'dut.sv'. You must NOT read, write, modify, or overwrite 'dut.sv' file. Your task is strictly to verify it by writing the test plan ('test_plan.md'), driver ('tb.sv'), and checker ('checker.py').

Available Skills:
{state.get('skills_summary', 'None')}

DUT Description and Headers (DUT has already been developed with the following prompt):
{state.get('dut_description', 'N/A')}
"""

    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    
    response = llm_with_tools.invoke(messages)

    if hasattr(response, "tool_calls") and response.tool_calls:
        tool_names = [tc["name"] for tc in response.tool_calls]
        print(f"\n[AGENT DECISION]\nTool Calls: {', '.join(tool_names)}\n")
    else:
        print("\n[AGENT DECISION]\nAI responded without using tools.\n")
    
    # Check for empty response or malformed function calls (common with large code payloads)
    finish_reason = response.response_metadata.get('finish_reason', '')
    if finish_reason == 'MALFORMED_FUNCTION_CALL' or (not response.content and not getattr(response, "tool_calls", None)):
        print("\n[WARNING]\nLLM returned a malformed function call. Retrying...\n")
        retry_msg = HumanMessage(content="Your last function call was malformed JSON (likely due to unescaped quotes in the code). Please try again and ensure the JSON arguments are valid.")
        return Command(goto="agent", update={"messages": [response, retry_msg]})
        
    # We return the newly generated message to be appended to the state
    return {"messages": [response]}