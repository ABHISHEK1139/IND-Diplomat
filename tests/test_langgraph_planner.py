"""
Test Suite: LangGraph Planner (Layer 0)
=======================================

Tests the OSS-integrated workflow for investigation planning.
Mocks out the actual model calls to ensure the state machine and
data passing works as expected.
"""

import pytest
from unittest.mock import patch, MagicMock
from dip.layer0_planning.workflow import PlanningWorkflow, PlannerState

# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------

class TestPlanningWorkflow:

    @patch("layer0_planning.workflow.ScopeDetector")
    @patch("layer0_planning.workflow.ObjectiveParser")
    @patch("layer0_planning.workflow.QueryExpander")
    @patch("layer0_planning.workflow.TemplateSelector")
    @patch("layer0_planning.workflow.PlannerMemory")
    def test_workflow_execution(self, mock_memory, mock_template, mock_expander, mock_objective, mock_scope):
        # Setup mocks
        mock_objective.return_value.parse.return_value = {
            "objective": "Test objective",
            "decision_support_type": "Policy Analysis",
            "time_horizon": "5 Years"
        }
        mock_scope.return_value.detect.return_value = {
            "countries": ["India"],
            "domains": ["Technology"]
        }
        mock_expander.return_value.expand.return_value = ["AI Policy", "Technology Roadmap"]
        mock_template.return_value.select.return_value = {
            "needs": ["Academic Papers"],
            "depth": "Research"
        }
        mock_memory.return_value.search_similar_plans.return_value = []
        
        # Instantiate workflow
        workflow = PlanningWorkflow()
        
        # Initial State
        initial_state = {
            "query": "Test query about India AI",
            "owner": "Tester",
            "investigation_id": "INV-TEST-003",
            "objective": None,
            "scope": None,
            "expanded_queries": None,
            "template": None,
            "past_plans": None,
            "final_plan": None,
            "investigation_obj": None
        }
        
        # We can test individual nodes without invoking the full graph
        state1 = workflow.node_understand(initial_state)
        assert state1["objective"]["decision_support_type"] == "Policy Analysis"
        
        state2 = workflow.node_extract_scope(state1)
        assert "India" in state2["scope"]["countries"]
        
        state3 = workflow.node_expand_query(state2)
        assert "AI Policy" in state3["expanded_queries"]
        
        state4 = workflow.node_choose_template(state3)
        assert "Academic Papers" in state4["template"]["needs"]
        
        state5 = workflow.node_generate_plan(state4)
        assert state5["final_plan"] is not None
        assert state5["investigation_obj"] is not None
        assert state5["investigation_obj"].investigation_id == "INV-TEST-003"
        assert state5["investigation_obj"].status == "CREATED"
        
        # Verify collection needs were created based on template
        needs = state5["investigation_obj"].collection_plan.needs
        assert len(needs) == 1
        assert needs[0].source_type == "Academic Papers"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
