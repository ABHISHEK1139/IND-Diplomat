"""
Bayesian Hidden Markov Model — 5-State Conflict Model (DIP 2.1)

Replaces the fuzzy linear sum in conflict_state_model.py with a proper
5-state Hidden Markov Model with adaptive transition matrices.

States:
  PEACE (0) → TENSIONS (1) → ESCALATION (2) → CRISIS (3) → WAR (4)

Features:
  - Forward-backward algorithm for state inference
  - Adaptive transition matrix (per-country priors)
  - Emission probabilities from signal intensities
  - Viterbi decoding for most-likely state sequence
  - Bayesian prior persistence (states tend to persist)

Mathematical foundation:
  P(S_t | O_{1:t}) ∝ P(O_t | S_t) · Σ P(S_t | S_{t-1}) · P(S_{t-1} | O_{1:t-1})
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


# ── State definitions ────────────────────────────────────────────

STATES = ["PEACE", "TENSIONS", "ESCALATION", "CRISIS", "WAR"]
N_STATES = 5

STATE_INDICES = {s: i for i, s in enumerate(STATES)}

# Default transition matrix: states tend to persist (high diagonal)
# Rows sum to 1.0; higher values on diagonal = state persistence
DEFAULT_TRANSITION_MATRIX = np.array([
    # PEACE   TENSIONS  ESCALATION  CRISIS   WAR
    [0.80,    0.15,     0.04,       0.01,    0.00],  # PEACE → 
    [0.10,    0.70,     0.15,       0.04,    0.01],  # TENSIONS →
    [0.03,    0.12,     0.65,       0.15,    0.05],  # ESCALATION →
    [0.01,    0.05,     0.15,       0.60,    0.19],  # CRISIS →
    [0.00,    0.02,     0.08,       0.25,    0.65],  # WAR →
])

# Per-country transition modifiers (some countries are more volatile)
COUNTRY_VOLATILITY: Dict[str, float] = {
    "KP": 0.30,   # North Korea — highly volatile
    "UA": 0.25,   # Ukraine — active conflict
    "YE": 0.25,   # Yemen — active conflict
    "IL": 0.22,   # Israel — frequent escalation
    "SY": 0.22,   # Syria — active conflict
    "IR": 0.20,   # Iran — elevated volatility
    "PK": 0.20,   # Pakistan — elevated volatility
    "AF": 0.20,   # Afghanistan — elevated volatility
    "IN": 0.15,   # India — moderate volatility
    "CN": 0.12,   # China — relatively stable
    "US": 0.10,   # US — relatively stable
    "RU": 0.15,   # Russia — moderate volatility
}

# Base emission priors: how likely each signal domain fires in each state
# Rows = states, Cols = [military, diplomatic, economic, cyber, political]
BASE_EMISSION_WEIGHTS = np.array([
    [0.05, 0.10, 0.05, 0.02, 0.05],  # PEACE
    [0.15, 0.30, 0.15, 0.08, 0.15],  # TENSIONS
    [0.40, 0.35, 0.25, 0.15, 0.25],  # ESCALATION
    [0.60, 0.30, 0.30, 0.20, 0.30],  # CRISIS
    [0.80, 0.15, 0.25, 0.25, 0.25],  # WAR
])


@dataclass
class HMMState:
    """Result of HMM inference at a single timestep."""
    state_probs: List[float]   # P(state_i) for each of 5 states
    most_likely_state: str     # The MAP state
    confidence: float          # Probability of MAP state
    entropy: float             # Uncertainty (higher = less certain)
    dominant_domain: str       # Which signal domain drives this state


@dataclass
class HMMResult:
    """Full HMM analysis result."""
    current_state: HMMState
    state_distribution: Dict[str, float]  # All 5 state probabilities
    transition_risk: float                # Probability of escalating in next step
    trajectory: List[HMMState]            # State history (if tracking multiple steps)
    country_code: str
    transition_matrix: List[List[float]]  # The adapted matrix used


class BayesianConflictHMM:
    """
    5-state Hidden Markov Model for conflict state inference.
    
    Usage:
        hmm = BayesianConflictHMM(country_code="IN")
        result = hmm.infer(signals)
        print(result.current_state.most_likely_state)  # "TENSIONS"
    """
    
    def __init__(
        self,
        country_code: str = "XX",
        prior_state: Optional[np.ndarray] = None,
        persistence_file: Optional[Path] = None,
    ):
        self.country_code = country_code
        self.volatility = COUNTRY_VOLATILITY.get(country_code, 0.15)
        
        # Adapt transition matrix for this country
        self.transition_matrix = self._adapt_transition(DEFAULT_TRANSITION_MATRIX)
        
        # State belief (initialized to PEACE with high certainty)
        if prior_state is not None:
            self.belief = prior_state
        else:
            self.belief = np.array([0.70, 0.20, 0.07, 0.02, 0.01])
        
        self.state_history: List[np.ndarray] = [self.belief.copy()]
        self.persistence_file = persistence_file
        
        # Load persisted belief if available
        if persistence_file and persistence_file.exists():
            self._load_persistence()
    
    def _adapt_transition(self, base: np.ndarray) -> np.ndarray:
        """
        Adapt the transition matrix based on country volatility.
        
        Higher volatility → flatter matrix (states change more easily).
        Lower volatility → sharper diagonal (states persist more).
        """
        if self.volatility <= 0:
            return base.copy()
        
        # Interpolate between base matrix and uniform matrix
        uniform = np.ones((N_STATES, N_STATES)) / N_STATES
        adapted = (1 - self.volatility) * base + self.volatility * uniform
        
        # Ensure rows sum to 1
        row_sums = adapted.sum(axis=1, keepdims=True)
        adapted = adapted / row_sums
        
        return adapted
    
    def infer(
        self,
        signals: List[Any],
        store_history: bool = True,
    ) -> HMMResult:
        """
        Run one step of HMM inference given new signals.
        
        Args:
            signals: List of Signal objects with .domain and .intensity attributes
            store_history: Whether to append to state_history
        """
        if not signals:
            # No new evidence → propagate belief forward one step
            self.belief = self._predict_step(self.belief)
        else:
            # Compute emission probabilities from signals
            emission = self._compute_emissions(signals)
            
            # Predict step: P(S_t | O_{1:t-1})
            predicted_belief = self._predict_step(self.belief)
            
            # Update step: P(S_t | O_t) ∝ P(O_t | S_t) · P(S_t | O_{1:t-1})
            self.belief = self._update_step(predicted_belief, emission)
        
        # Normalize
        self.belief = self.belief / self.belief.sum()
        
        if store_history:
            self.state_history.append(self.belief.copy())
        
        # Build result
        map_idx = int(np.argmax(self.belief))
        map_prob = float(self.belief[map_idx])
        
        # Entropy: -Σ p log p
        entropy = -float(sum(p * math.log(max(p, 1e-10)) for p in self.belief))
        
        # Dominant domain
        if signals:
            domain_counts: Dict[str, float] = {}
            for sig in signals:
                domain = getattr(sig, 'domain', 'unknown')
                intensity = getattr(sig, 'intensity', 0.5)
                domain_counts[domain] = domain_counts.get(domain, 0) + intensity
            dominant_domain = max(domain_counts, key=domain_counts.get) if domain_counts else "unknown"
        else:
            dominant_domain = "none"
        
        current = HMMState(
            state_probs=[round(float(p), 4) for p in self.belief],
            most_likely_state=STATES[map_idx],
            confidence=round(map_prob, 4),
            entropy=round(entropy, 4),
            dominant_domain=dominant_domain,
        )
        
        # Transition risk: probability of moving to a worse state
        transition_risk = self._compute_transition_risk()
        
        # Build trajectory
        trajectory = []
        for hist_belief in self.state_history[-10:]:  # Last 10 steps
            idx = int(np.argmax(hist_belief))
            prob = float(hist_belief[idx])
            trajectory.append(HMMState(
                state_probs=[round(float(p), 4) for p in hist_belief],
                most_likely_state=STATES[idx],
                confidence=round(prob, 4),
                entropy=0.0,
                dominant_domain="",
            ))
        
        return HMMResult(
            current_state=current,
            state_distribution={STATES[i]: round(float(self.belief[i]), 4) for i in range(N_STATES)},
            transition_risk=round(transition_risk, 4),
            trajectory=trajectory[-5:],  # Last 5 states
            country_code=self.country_code,
            transition_matrix=[[round(float(x), 4) for x in row] for row in self.transition_matrix],
        )
    
    def _predict_step(self, belief: np.ndarray) -> np.ndarray:
        """
        Chapman-Kolmogorov prediction: P(S_t | O_{1:t-1}) = Σ P(S_t | S_{t-1}) · P(S_{t-1} | O_{1:t-1})
        """
        return belief @ self.transition_matrix
    
    def _update_step(self, predicted: np.ndarray, emission: np.ndarray) -> np.ndarray:
        """
        Bayes update: P(S_t | O_t) ∝ P(O_t | S_t) · P(S_t | O_{1:t-1})
        """
        unnormalized = emission * predicted
        total = unnormalized.sum()
        if total > 0:
            return unnormalized / total
        return predicted
    
    def _compute_emissions(self, signals: List[Any]) -> np.ndarray:
        """
        Compute P(O_t | S_t) for each state.
        
        Uses domain-weighted signal intensities mapped through base emission weights.
        """
        # Aggregate signal intensities by domain
        domain_intensities = np.zeros(5)  # [military, diplomatic, economic, cyber, political]
        domain_counts = np.zeros(5)
        
        domain_map = {
            "military": 0, "defense": 0, "security": 0,
            "diplomatic": 1, "political": 1, "legal": 1,
            "economic": 2, "trade": 2, "sanctions": 2,
            "cyber": 3, "digital": 3,
            "information": 4, "media": 4, "propaganda": 4,
        }
        
        for sig in signals:
            domain = getattr(sig, 'domain', 'unknown')
            intensity = getattr(sig, 'intensity', 0.5)
            idx = domain_map.get(domain, 4)  # Default to political
            domain_intensities[idx] += intensity
            domain_counts[idx] += 1
        
        # Average intensities
        for i in range(5):
            if domain_counts[i] > 0:
                domain_intensities[i] /= domain_counts[i]
        
        # Weighted emission: how well each state explains the observed signals
        emission = np.zeros(N_STATES)
        for s in range(N_STATES):
            # Weighted sum of domain intensities × emission weights for this state
            emission[s] = float(np.dot(domain_intensities, BASE_EMISSION_WEIGHTS[s]))
        
        # Add small epsilon to avoid zero probabilities
        emission += 0.01
        emission = emission / emission.sum()
        
        return emission
    
    def _compute_transition_risk(self) -> float:
        """
        Probability of escalating from current state to any worse state.
        """
        map_idx = int(np.argmax(self.belief))
        if map_idx >= N_STATES - 1:
            return 0.0  # Already at WAR
        
        # Sum probability of transitioning to states worse than current
        risk = sum(self.transition_matrix[map_idx, map_idx + 1:])
        return float(risk)
    
    def viterbi(self, signal_sequences: List[List[Any]]) -> Tuple[List[int], float]:
        """
        Viterbi decoding: find the most likely state sequence given all observations.
        
        Returns: (state_sequence, log_probability)
        """
        T = len(signal_sequences)
        if T == 0:
            return [0], 0.0
        
        # Initialize
        emissions = np.array([self._compute_emissions(sigs) for sigs in signal_sequences])
        
        # Viterbi trellis
        viterbi = np.zeros((T, N_STATES))
        backpointers = np.zeros((T, N_STATES), dtype=int)
        
        # Initial step
        viterbi[0] = np.log(self.belief + 1e-10) + np.log(emissions[0] + 1e-10)
        
        # Recursion
        for t in range(1, T):
            for s in range(N_STATES):
                trans_log = np.log(self.transition_matrix[:, s] + 1e-10)
                candidates = viterbi[t-1] + trans_log
                best_prev = int(np.argmax(candidates))
                viterbi[t, s] = candidates[best_prev] + np.log(emissions[t, s] + 1e-10)
                backpointers[t, s] = best_prev
        
        # Backtrack
        best_path = [int(np.argmax(viterbi[-1]))]
        for t in range(T - 1, 0, -1):
            best_path.insert(0, backpointers[t, best_path[0]])
        
        return best_path, float(np.max(viterbi[-1]))
    
    def _load_persistence(self) -> None:
        """Load persisted belief state from disk."""
        try:
            with open(self.persistence_file, "r") as f:
                data = json.load(f)
            if data.get("country_code") == self.country_code:
                self.belief = np.array(data.get("belief", self.belief.tolist()))
                self.state_history = [np.array(h) for h in data.get("history", [self.belief.tolist()])]
        except (json.JSONDecodeError, KeyError, FileNotFoundError):
            pass
    
    def save_persistence(self) -> None:
        """Save current belief state to disk."""
        if not self.persistence_file:
            return
        
        self.persistence_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.persistence_file, "w") as f:
            json.dump({
                "country_code": self.country_code,
                "belief": self.belief.tolist(),
                "history": [h.tolist() for h in self.state_history[-20:]],
                "volatility": self.volatility,
            }, f, indent=2)
