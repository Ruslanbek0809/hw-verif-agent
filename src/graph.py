from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from src.state import AgentState
from src.nodes.agent import agent_node
from src.tools.verification_tools import tools

def build_graph():
    """Builds and compiles the LangGraph ReAct agent graph."""
    workflow = StateGraph(AgentState)
    
    # Define the two nodes we will cycle between
    workflow.add_node("agent", agent_node)
    
    # ToolNode automatically handles calling the tools defined in the agent's bind_tools
    tool_node = ToolNode(tools)
    workflow.add_node("tools", tool_node)
    
    # Set the entrypoint
    workflow.add_edge(START, "agent")
    
    # We now add a conditional edge
    # `tools_condition` routes to "tools" if the agent returned tool calls,
    # otherwise it routes to END
    workflow.add_conditional_edges(
        "agent",
        tools_condition,
        {"tools": "tools", END: END}
    )
    
    # Any time a tool is called, we return to the agent to decide the next step
    workflow.add_edge("tools", "agent")
    
    # Compile the graph
    app = workflow.compile()
    
    return app
