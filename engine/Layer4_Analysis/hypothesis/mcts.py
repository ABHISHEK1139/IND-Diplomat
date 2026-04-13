
import math
import random
from typing import List, Dict, Any, Optional

class MCTSNode:
    """Represents a node in the MCTS reasoning tree."""
    
    def __init__(self, state: str, parent=None, action: str = None):
        self.state = state  # Current reasoning state/query
        self.parent = parent
        self.action = action  # Action taken to reach this state
        self.children = []
        self.visits = 0
        self.value = 0.0  # Accumulated value from simulations
        self.is_terminal = False
        self.untried_actions = None  # Lazy initialization

    def is_fully_expanded(self) -> bool:
        return self.untried_actions is not None and len(self.untried_actions) == 0

    def get_ucb1(self, exploration_weight: float) -> float:
        """Calculates UCB1 score for this node."""
        if self.visits == 0:
            return float('inf')
        
        exploitation = self.value / self.visits
        exploration = exploration_weight * math.sqrt(math.log(self.parent.visits) / self.visits)
        return exploitation + exploration


class MCTSRAGAgent:
    """
    State-grounded Monte Carlo Tree Search for reasoning path discovery.

    Scores reasoning paths by StateContext signal relevance — NOT by
    retrieval quality. Layer-4 must never access Layer-2 directly.

    Features:
    1. LLM-guided action generation
    2. StateContext signal-based simulation scoring
    3. Configurable exploration/exploitation
    4. Pruning of low-value branches
    """
    
    def __init__(self, exploration_weight: float = 1.41, max_depth: int = 5,
                 state_context: dict = None):
        self.exploration_weight = exploration_weight
        self.max_depth = max_depth
        self.state_context = state_context or {}
        self.action_templates = [
            "legal implications of {topic}",
            "economic impact of {topic}",
            "historical precedents for {topic}",
            "security risks of {topic}",
            "stakeholder perspectives on {topic}",
            "timeline and milestones of {topic}"
        ]

        # Signal dimension keywords for scoring reasoning path relevance
        self._signal_dimensions = {
            "military": ["military", "mobilization", "troops", "exercises", "clash",
                         "border", "logistics", "weapons", "defense", "attack"],
            "diplomatic": ["diplomatic", "negotiation", "treaty", "alliance", "hostility",
                           "ambassador", "summit", "sanctions", "statement", "stance"],
            "economic": ["economic", "trade", "sanctions", "tariff", "investment",
                         "dependency", "pressure", "gdp", "currency", "embargo"],
            "domestic": ["domestic", "unrest", "protest", "stability", "regime",
                         "election", "opposition", "public opinion", "media"],
            "legal": ["legal", "law", "treaty", "convention", "jurisdiction",
                      "sovereignty", "international law", "resolution", "compliance"],
        }

    def set_state_context(self, state_context: dict) -> None:
        """Update the state context for scoring."""
        self.state_context = state_context or {}

    async def generate_actions(self, state: str) -> List[str]:
        """
        Generates possible reasoning actions from current state.
        Uses LLM when available, falls back to templates.
        """
        try:
            from engine.Layer4_Analysis.core.llm_client import llm_client
            
            prompt = f"""Given this diplomatic analysis topic:
"{state}"

Generate 3 specific follow-up questions or research directions that would deepen the analysis.
Return ONLY the questions, one per line."""

            response = await llm_client.generate(prompt, system_prompt="You are a research strategist.", query_type="factual")
            actions = [a.strip() for a in response.strip().split("\n") if a.strip()]
            return actions[:3] if actions else self._template_actions(state)
            
        except Exception:
            return self._template_actions(state)
    
    def _template_actions(self, state: str) -> List[str]:
        """Template-based action generation fallback."""
        topic = state.split("->")[-1].strip() if "->" in state else state[:50]
        return [t.format(topic=topic) for t in random.sample(self.action_templates, 3)]

    def select(self, node: MCTSNode) -> MCTSNode:
        """
        Selects the best child using UCB1 until reaching unexpanded or terminal node.
        """
        current = node
        depth = 0
        
        while not current.is_terminal and depth < self.max_depth:
            if current.untried_actions is None:
                # First visit - need to expand
                return current
            
            if not current.is_fully_expanded():
                return current
            
            if not current.children:
                break
            
            # Select best child by UCB1
            current = max(current.children, key=lambda c: c.get_ucb1(self.exploration_weight))
            depth += 1
        
        return current

    async def expand(self, node: MCTSNode) -> MCTSNode:
        """
        Expands a node by generating and trying one new action.
        """
        if node.untried_actions is None:
            node.untried_actions = await self.generate_actions(node.state)
        
        if not node.untried_actions:
            node.is_terminal = True
            return node
        
        # Take the first untried action
        action = node.untried_actions.pop(0)
        new_state = f"{node.state} -> {action}"
        
        child = MCTSNode(new_state, parent=node, action=action)
        node.children.append(child)
        
        return child

    async def simulate(self, node: MCTSNode) -> float:
        """
        Simulates from node to estimate value.

        Scores reasoning paths by how well they align with StateContext
        signal dimensions. Paths that explore dimensions where state data
        exists are scored higher — this guides MCTS toward state-grounded
        reasoning rather than document-availability-based reasoning.
        """
        query = node.action if node.action else node.state
        query_lower = query.lower()

        # Score based on alignment with StateContext signal dimensions
        dimension_scores = {}
        for dimension, keywords in self._signal_dimensions.items():
            # Check if the reasoning path touches this signal dimension
            keyword_hits = sum(1 for kw in keywords if kw in query_lower)
            if keyword_hits == 0:
                continue

            # Check if StateContext has data for this dimension
            state_data = self.state_context.get(dimension, {}) or {}
            if not state_data:
                # Dimension exists in query but no state data — low value
                dimension_scores[dimension] = 0.2
            else:
                # Dimension has state data — score by intensity
                values = []
                for v in state_data.values():
                    try:
                        values.append(abs(float(v)))
                    except (TypeError, ValueError):
                        values.append(0.3)  # Non-numeric signals (e.g. "hostile")
                avg_intensity = sum(values) / len(values) if values else 0.0
                dimension_scores[dimension] = min(1.0, 0.3 + avg_intensity * 0.7)

        if not dimension_scores:
            # Reasoning path doesn't clearly map to any signal dimension
            depth = node.state.count("->")
            return random.uniform(0.2, 0.5) * (1.0 - depth * 0.1)

        # Combined score: weighted by how many dimensions are covered
        base_score = sum(dimension_scores.values()) / len(dimension_scores)

        # Bonus for covering multiple dimensions (breadth of reasoning)
        coverage_bonus = min(0.2, len(dimension_scores) * 0.05)

        # Depth penalty to prefer shallower, focused paths
        depth = node.state.count("->")
        depth_penalty = depth * 0.05

        return max(0.1, min(1.0, base_score + coverage_bonus - depth_penalty))

    def backpropagate(self, node: MCTSNode, reward: float):
        """
        Updates value and visits up the tree.
        """
        current = node
        while current is not None:
            current.visits += 1
            current.value += reward
            current = current.parent

    def get_best_path(self, root: MCTSNode) -> str:
        """
        Returns the best reasoning path based on exploitation (avg value).
        """
        if not root.children:
            return root.state
        
        # Find best child by average value
        best_child = max(root.children, key=lambda c: c.value / c.visits if c.visits > 0 else 0)
        
        # Recursively get best path
        return self.get_best_path(best_child)

    async def search(self, initial_query: str, iterations: int = 10) -> str:
        """
        Main MCTS search loop.
        Returns the best reasoning path discovered.
        """
        print(f"[MCTS] Starting search for: {initial_query}")
        root = MCTSNode(initial_query)
        
        for i in range(iterations):
            # 1. Selection
            leaf = self.select(root)
            
            # 2. Expansion
            if not leaf.is_terminal:
                leaf = await self.expand(leaf)
            
            # 3. Simulation
            reward = await self.simulate(leaf)
            
            # 4. Backpropagation
            self.backpropagate(leaf, reward)
            
            if (i + 1) % 5 == 0:
                print(f"[MCTS] Iteration {i+1}/{iterations} complete")
        
        # Return best path
        best_path = self.get_best_path(root)
        print(f"[MCTS] Best reasoning path: {best_path}")
        
        return best_path
    
    def get_tree_stats(self, root: MCTSNode) -> Dict[str, Any]:
        """Returns statistics about the search tree."""
        def count_nodes(node):
            return 1 + sum(count_nodes(c) for c in node.children)
        
        def max_depth(node, depth=0):
            if not node.children:
                return depth
            return max(max_depth(c, depth + 1) for c in node.children)
        
        return {
            "total_nodes": count_nodes(root),
            "max_depth": max_depth(root),
            "root_visits": root.visits,
            "num_children": len(root.children)
        }
