# Changelog

## v3.1.0 (2026-09-02) - DIP 3.1 Neuro-Symbolic Structured Message Protocol
### Added
- **Agent Message Bus:** Central async pub/sub bus replacing parallel execution.
- **Debate Orchestrator:** State machine for EVIDENCE_READY -> INDEPENDENT_ANALYSIS -> CROSS_EXAMINATION -> CONTRARIAN_CHALLENGE -> REBUTTAL -> CONSENSUS.
- **Structured Schemas:** Pydantic AgentMessage with message_type and evidence_ids tracking.
- **BaseSpecialist Class:** Upgraded 7 Ministers to analytical specialists interacting over the bus.
- **3-Tier Memory:** Global Evidence Memory, Agent Belief Ledgers, and Debate Traces.

