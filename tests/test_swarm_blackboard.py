import asyncio
import os
import sys

# Ensure dip is in PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from dip.pipeline.deliberation.reasoning.swarm_blackboard import SwarmOrchestrator

async def test_swarm():
    print("\nBooting Politiq AI Agent Swarm...")
    
    # 1. Initialize the Swarm with an overarching goal
    goal = "Investigate the potential for a localized maritime skirmish in the South China Sea within 30 days."
    swarm = SwarmOrchestrator(goal)
    
    # 2. Register specialized sub-agents
    swarm.register_agent("Security Minister", "Military strategy, naval deployments, and kinetic threat assessment")
    swarm.register_agent("Diplomacy Minister", "Geopolitical negotiations, treaties, and international signaling")
    swarm.register_agent("Economic Minister", "Trade routes, supply chain disruptions, and sanctions")
    
    # 3. Run the swarm for 3 communication loops
    print(f"\nGoal: {goal}\n")
    print("Agents are communicating on the Blackboard...\n")
    
    final_board = await swarm.run_swarm(iterations=3)
    
    # 4. Print the final state of the Blackboard
    print("\n" + "="*50)
    print("FINAL BLACKBOARD STATE")
    print("="*50)
    print(final_board.get_state())

if __name__ == "__main__":
    asyncio.run(test_swarm())
