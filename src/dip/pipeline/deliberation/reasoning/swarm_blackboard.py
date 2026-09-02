"""
Swarm Blackboard Orchestrator
=============================
Implements a multi-agent autonomous swarm where sub-agents communicate 
via a shared memory space (the Blackboard) to coordinate, delegate sub-tasks,
and collaboratively solve a unified intelligence goal.
"""

import asyncio
import logging
import json
from typing import List, Dict, Any

from dip.core.Config.config import config
from dip.telemetry.llm_tracer import tracer
from dip.core.json_utils import strip_markdown_json

logger = logging.getLogger("Layer4.SwarmBlackboard")

class Blackboard:
    """The shared memory space for agent inter-communication."""
    def __init__(self, overarching_goal: str):
        self.goal = overarching_goal
        self.messages: List[Dict[str, str]] = []
        self.subtasks: Dict[str, Dict[str, str]] = {}
        
    def post_message(self, agent_name: str, message: str):
        self.messages.append({"agent": agent_name, "message": message})
        logger.debug(f"[Blackboard] {agent_name}: {message[:50]}...")
        
    def update_subtask(self, task_id: str, assignee: str, status: str, result: str = ""):
        self.subtasks[task_id] = {
            "assignee": assignee,
            "status": status,
            "result": result
        }
        
    def get_state(self) -> str:
        state = f"OVERARCHING GOAL: {self.goal}\n\n"
        state += "--- INTER-AGENT MESSAGES ---\n"
        for m in self.messages:
            state += f"[{m['agent']}]: {m['message']}\n"
        state += "\n--- SUBTASKS & DELEGATION ---\n"
        for tid, t in self.subtasks.items():
            state += f"{tid} [Assignee: {t['assignee']}] [{t['status']}] -> {t['result']}\n"
        return state

class SwarmAgent:
    """An autonomous sub-agent that reads from and writes to the Blackboard."""
    def __init__(self, name: str, expertise: str):
        self.name = name
        self.expertise = expertise
        
    async def run_turn(self, blackboard: Blackboard):
        state = blackboard.get_state()
        prompt = f"""You are '{self.name}', an expert in {self.expertise}.
You are part of an autonomous Swarm collaborating on a shared Blackboard.

{state}

Analyze the current state of the Blackboard. You can either:
1. Post a new message with insights, evidence, or questions for other agents.
2. Define a new subtask for the swarm (Use format T-1, T-2).
3. Claim an open subtask, solve it using your expertise, and post the result.

Respond STRICTLY in JSON format matching this schema:
{{
   "action": "post_message" or "update_subtask",
   "message": "Your text here (required if action is post_message)",
   "task_id": "T-X (required if action is update_subtask)",
   "status": "OPEN or IN_PROGRESS or COMPLETED (required if action is update_subtask)",
   "result": "Output of your work (required if action is update_subtask)"
}}
"""
        try:
            response = await tracer.acompletion(
                layer="Swarm_Collaboration",
                model=config.LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            content = strip_markdown_json(response.choices[0].message.content)
            data = json.loads(content)
            
            action = data.get("action")
            if action == "post_message":
                msg = data.get("message", "")
                if msg:
                    blackboard.post_message(self.name, msg)
            elif action == "update_subtask":
                tid = data.get("task_id", "T-0")
                status = data.get("status", "OPEN")
                res = data.get("result", "")
                blackboard.update_subtask(tid, self.name, status, res)
                blackboard.post_message(self.name, f"I have updated task {tid} to {status}.")
        except Exception as e:
            logger.error(f"SwarmAgent {self.name} failed turn: {e}")


class SwarmOrchestrator:
    """Orchestrates the Swarm, allowing them to collaborate iteratively."""
    def __init__(self, goal: str):
        self.goal = goal
        self.blackboard = Blackboard(goal)
        self.agents: List[SwarmAgent] = []
        
    def register_agent(self, name: str, expertise: str):
        self.agents.append(SwarmAgent(name, expertise))
        
    async def run_swarm(self, iterations: int = 3) -> Blackboard:
        """Runs the swarm collaboration loop."""
        logger.info(f"Starting Swarm on goal: {self.goal}")
        self.blackboard.post_message("SYSTEM", f"Swarm initialized with {len(self.agents)} agents. Begin collaboration.")
        
        for i in range(iterations):
            logger.info(f"Swarm iteration {i+1}/{iterations}...")
            # Agents act concurrently, reading the current state and making their moves
            tasks = [agent.run_turn(self.blackboard) for agent in self.agents]
            await asyncio.gather(*tasks)
            
        return self.blackboard
