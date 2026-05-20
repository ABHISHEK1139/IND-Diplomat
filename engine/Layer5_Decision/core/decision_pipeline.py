import logging
from typing import Dict, Any
from engine.Layer4_Analysis.council_session import CouncilSession
from engine.Layer5_Decision.managers.strategy_designer import StrategyDesigner
from engine.Layer5_Decision.managers.risk_manager import RiskManager
from engine.Layer5_Decision.managers.policy_maker import PolicyMaker

logger = logging.getLogger(__name__)

class DecisionPipeline:
    """
    Orchestrates Phase 3 (Layer 5 Decision Pipeline).
    Flow: CouncilSession -> StrategyDesigner -> RiskManager -> PolicyMaker
    """
    def __init__(self):
        self.strategy_designer = StrategyDesigner()
        self.risk_manager = RiskManager()
        self.policy_maker = PolicyMaker()

    async def execute_decision_phase(self, session: CouncilSession) -> Dict[str, Any]:
        logger.info("[LAYER 5] Initiating Decision Pipeline...")
        
        # 1. Strategy Design
        strategy = await self.strategy_designer.design_strategy(session)
        logger.info("[LAYER 5] Strategy designed. Recommended: %s", strategy.get('recommended_tier', 'unknown'))

        # 2. Risk Evaluation
        risk_assessment = await self.risk_manager.evaluate_risk(strategy)
        logger.info("[LAYER 5] Risk evaluated. Veto recommendation: %s", risk_assessment.get('veto_recommendation', False))

        # 3. Policy Finalization
        final_policy = await self.policy_maker.finalize_policy(strategy, risk_assessment)
        logger.info("[LAYER 5] Final policy finalized.")
        
        # Aggregate the decision state
        decision_state = {
            "strategy_proposal": strategy,
            "risk_assessment": risk_assessment,
            "final_policy": final_policy
        }
        
        # Attach to session for traceability if needed
        session.decision_state = decision_state
        return decision_state
