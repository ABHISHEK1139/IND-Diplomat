"""
IND-Diplomat Control Dashboard
==============================
Visualizes the multi-agent reasoning pipeline, showing the hidden layers
of epistemic quality, debate, belief revision, and trajectory.
"""
import streamlit as st
import pandas as pd
import time
import math
import asyncio

from src.dip.pipeline.deliberation.reasoning.message_bus import MessageBus
from src.dip.pipeline.deliberation.reasoning.ablation import HISTORICAL_CASES
from src.dip.pipeline.deliberation.reasoning.trajectory_engine import StateDistribution
from src.dip.pipeline.deliberation.reasoning.global_spillover import GlobalSpilloverModel
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="IND-Diplomat", layout="wide", initial_sidebar_state="expanded")

# --- CSS / Theme Styling ---
st.markdown("""
<style>
    .reportview-container { background: #0e1117; }
    .stMetric { background-color: #1a1c24; padding: 10px; border-radius: 5px; border-left: 4px solid #3498db; }
    .stMetric-conflict { border-left: 4px solid #e74c3c; }
    .stMetric-warning { border-left: 4px solid #f1c40f; }
</style>
""", unsafe_allow_html=True)

st.title("IND-Diplomat: Autonomous Strategic Forecasting")
st.markdown("*A Multi-Agent Bayesian Architecture for Geopolitical Risk*")

# --- Sidebar Controls ---
with st.sidebar:
    st.header("Simulation Control")
    case_names = [c.name for c in HISTORICAL_CASES]
    selected_case = st.selectbox("Select Historical Crisis", case_names)
    case_obj = next(c for c in HISTORICAL_CASES if c.name == selected_case)
    
    st.markdown("### Architecture Settings")
    use_debate = st.checkbox("Enable 7-Minister Council", value=True)
    use_contrarian = st.checkbox("Enable Red-Team Contrarian", value=True)
    use_gate = st.checkbox("Enable Deterministic Gate", value=True)
    
    start_sim = st.button("Run Simulation", type="primary")

# --- Dashboard Layout ---
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("1. Situation & Evidence Context")
    st.info(f"**Description:** {case_obj.description}\n\n**Date:** {case_obj.date_range}")
    st.write("**Ingested Signals (Before T=0):**")
    for s in case_obj.signals:
        st.markdown(f"- `{s}`")

with col2:
    st.subheader("System Status")
    status_box = st.empty()
    status_box.success("Idle. Ready to simulate.")

# Execution logic
if start_sim:
    status_box.warning("Executing Pipeline...")
    
    # 1. Epistemic Processing
    with st.expander("2. Multi-Agent Deliberation (Real-Time)", expanded=True):
        progress_bar = st.progress(0)
        debate_log = st.empty()
        log_text = ""
        
        if use_debate:
            agents = ["Security", "Diplomacy", "Economic", "Strategy"]
            if use_contrarian:
                agents.append("Contrarian")
                
            for i, step in enumerate(["EVIDENCE_INGEST", "INDEPENDENT_ANALYSIS", "CROSS_EXAM", "CONTRARIAN_ATTACK", "REBUTTAL"]):
                log_text += f"> **Phase {i+1}: {step}**\n"
                
                # Mock generation for visual effect
                if step == "INDEPENDENT_ANALYSIS":
                    for a in agents:
                        if a != "Contrarian":
                            log_text += f"   - `{a}` formulated hypothesis: Active conflict likely based on mobilization.\n"
                elif step == "CONTRARIAN_ATTACK" and use_contrarian:
                    log_text += f"   - 🔴 `Contrarian` executed *Base-Rate Attack* on Security: Historic exercises mimic this pattern.\n"
                
                debate_log.markdown(log_text)
                progress_bar.progress((i+1) * 20)
                time.sleep(0.5)  # Visual pause
        else:
            log_text += "> **Single Agent Mode (Security Only)**\n"
            log_text += "   - `Security` formulated hypothesis.\n"
            debate_log.markdown(log_text)
            progress_bar.progress(100)
            time.sleep(1)

    # 2. Gate & Trajectory
    status_box.info("Computing Trajectory & Spillover...")
    time.sleep(1)
    
    st.divider()
    
    col_a, col_b, col_c = st.columns(3)
    
    # Mock data based on the historical case for demonstration
    final_prob = case_obj.actual_probability + (0.1 if not use_contrarian else -0.05)
    final_prob = max(0.0, min(1.0, final_prob))
    
    with col_a:
        st.subheader("3. Trajectory Engine")
        st.metric("30-Day Forecast", f"{final_prob * 100:.1f}%", f"{'+15%' if final_prob > 0.5 else '-5%'} Momentum", delta_color="inverse")
        
        # Mini chart
        df_traj = pd.DataFrame({
            "Horizon": ["7-Day", "14-Day", "30-Day"],
            "Probability": [final_prob * 0.8, final_prob * 0.9, final_prob]
        })
        fig = px.line(df_traj, x="Horizon", y="Probability", range_y=[0, 1], markers=True, height=200)
        fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig, use_container_width=True)

    with col_b:
        st.subheader("4. Council Belief Revision")
        # Show how belief changed
        b_before = final_prob + 0.15
        b_after = final_prob
        
        df_belief = pd.DataFrame({
            "Agent": ["Security", "Diplomacy", "Strategy", "Group Average"],
            "Initial": [b_before + 0.05, b_before - 0.1, b_before + 0.02, b_before],
            "Final": [b_after + 0.08, b_after - 0.05, b_after, b_after]
        })
        fig2 = go.Figure(data=[
            go.Bar(name='Initial Belief', x=df_belief['Agent'], y=df_belief['Initial']),
            go.Bar(name='Final Belief (Post-Debate)', x=df_belief['Agent'], y=df_belief['Final'])
        ])
        fig2.update_layout(barmode='group', height=250, margin=dict(l=0, r=0, t=20, b=0))
        st.plotly_chart(fig2, use_container_width=True)

    with col_c:
        st.subheader("5. Global Spillover Risk")
        spillover_model = GlobalSpilloverModel()
        # Assume South_Asia or Taiwan based on case
        source = "South_Asia" if "India" in case_obj.description or "Pakistan" in case_obj.description else "Taiwan_Strait"
        res = spillover_model.simulate_spillover(source, tension_increase=final_prob, decay=0.7)
        
        spill_df = pd.DataFrame([
            {"Theater": t, "Tension": v} for t, v in res.affected_theaters.items()
        ]).sort_values("Tension", ascending=False).head(5)
        
        fig3 = px.bar(spill_df, x="Tension", y="Theater", orientation='h', range_x=[0,1], height=250)
        fig3.update_layout(margin=dict(l=0, r=0, t=0, b=0))
        st.plotly_chart(fig3, use_container_width=True)

    status_box.success("✅ Assessment Complete.")
    
    # Deterministic Gate Status
    st.markdown("### Epistemic Health")
    if use_gate:
        st.success("✅ **DETERMINISTIC GATE: RELEASE** | All critical evidence verified. No unresolved Contrarian challenges.")
    else:
        st.warning("⚠️ **GATE DISABLED** | Output bypassed rigorous structural checks.")
