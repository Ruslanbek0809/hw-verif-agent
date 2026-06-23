from typing import TypedDict, Optional, Annotated, Any
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

def merge_tasks(left: dict, right: dict) -> dict:
    if right.get("__clear__"):
        return {}
    return {**left, **right}

class AgentState(TypedDict):
    # Core ReAct agent messages list
    messages: Annotated[list[BaseMessage], add_messages]
    
    # Task Manager
    tasks: Annotated[dict, merge_tasks]
    
    # Inputs
    test_subject_id: int
    dut_description: str
    dut_headers: str
    dut_code: Optional[str] # The actual DUT code for simulation
    
    # Context/Skills
    context: Optional[str]
    skills_summary: Optional[str]

    # Shared State for tools
    csv_format: Optional[str]
    max_revisions: int
    
    # Trackers for tools
    driver_revision_number: int
    checker_revision_number: int
