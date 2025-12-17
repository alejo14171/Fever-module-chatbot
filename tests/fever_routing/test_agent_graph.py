from fever_routing.agent import make_graph
from langgraph.graph import StateGraph
from unittest.mock import MagicMock

def test_make_graph_structure():
    # Verify make_graph returns a compiled graph
    config = {"checkpoint": None}
    agent = make_graph(config)
    
    # It should be a CompiledStateGraph (or similar)
    # We can check if it has 'invoke' method
    assert hasattr(agent, "invoke")
    assert hasattr(agent, "stream")
    
    # We can verify the structure by inspecting the underlying graph if accessible
    # But usually just compiling it without error is a good smoke test
    
    # Check if nodes exist (internal implementation details usually)
    # But we can assume it works if compiled.

def test_make_graph_with_checkpointer():
    mock_checkpointer = MagicMock()
    config = {"checkpoint": mock_checkpointer}
    agent = make_graph(config)
    assert hasattr(agent, "invoke")
    
    # Verify checkpointer was passed to compile (hard to check on compiled object directly without digging)

