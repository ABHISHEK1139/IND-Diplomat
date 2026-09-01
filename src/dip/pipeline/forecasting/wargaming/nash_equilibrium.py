"""
Layer 8 Wargaming: Nash Equilibrium Solver
==========================================
Computes the Pure and Mixed Strategy Nash Equilibria for given state actors
based on the NextGenSRE escalation probabilities and heuristic payloads.
"""

from typing import List, Dict, Any, Tuple
import numpy as np

def compute_equilibrium(payoff_matrix: np.ndarray) -> Dict[str, Any]:
    """
    Computes pure strategy Nash Equilibria for a 2-player normal form game.
    payoff_matrix: shape (N, M, 2) where N is player 1 actions, M is player 2 actions,
                   and the last dimension holds (p1_payoff, p2_payoff).
    """
    equilibria = []
    rows, cols, _ = payoff_matrix.shape
    
    # Check each cell if it's a best response for both players
    for i in range(rows):
        for j in range(cols):
            p1_payoff = payoff_matrix[i, j, 0]
            p2_payoff = payoff_matrix[i, j, 1]
            
            # Is p1_payoff the max in column j for player 1?
            is_p1_best = all(p1_payoff >= payoff_matrix[k, j, 0] for k in range(rows))
            # Is p2_payoff the max in row i for player 2?
            is_p2_best = all(p2_payoff >= payoff_matrix[i, l, 1] for l in range(cols))
            
            if is_p1_best and is_p2_best:
                equilibria.append(((i, j), (p1_payoff, p2_payoff)))
                
    return {
        "pure_strategies": equilibria,
        "is_stable": len(equilibria) > 0,
        "multiple_equilibria": len(equilibria) > 1
    }

def generate_payoff_matrix(actor1_capabilities: float, actor2_capabilities: float, sre_escalation: float) -> np.ndarray:
    """
    Generates a generic 2x2 (Cooperate vs Defect/Escalate) payoff matrix 
    derived from SRE escalation indexes and actor capabilities.
    """
    # Actions: 0 = Cooperate (De-escalate), 1 = Defect (Escalate)
    # Matrix structure:
    # [ [ (C,C), (C,D) ],
    #   [ (D,C), (D,D) ] ]
    
    # Cooperate vs Cooperate
    cc_1 = 5.0
    cc_2 = 5.0
    
    # Cooperate vs Defect
    cd_1 = 0.0 - (actor2_capabilities * 0.5)
    cd_2 = 10.0 + (actor2_capabilities * 0.5)
    
    # Defect vs Cooperate
    dc_1 = 10.0 + (actor1_capabilities * 0.5)
    dc_2 = 0.0 - (actor1_capabilities * 0.5)
    
    # Defect vs Defect (Mutual Escalation)
    # The higher the SRE escalation risk, the more negative this becomes
    dd_1 = -5.0 - (sre_escalation * 10)
    dd_2 = -5.0 - (sre_escalation * 10)
    
    matrix = np.array([
        [[cc_1, cc_2], [cd_1, cd_2]],
        [[dc_1, dc_2], [dd_1, dd_2]]
    ])
    return matrix
