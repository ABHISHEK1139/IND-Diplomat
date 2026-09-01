from dip.engines.assessment_graph import HeadOfStatePipelineGraph


def test_blackboard_posts_and_checkpoints(tmp_path):
    graph = HeadOfStatePipelineGraph(checkpoint_dir=tmp_path)
    goal, bb = graph.start("Test objective", country="CXY")
    bb.post("collection", "collection.started", {"count": 3})
    bb.post("sre", "sre.completed", {"score": 0.5})
    graph.save_phase(goal, "report", bb)

    # Check that some checkpoint file referencing the trace_id exists
    files = list(tmp_path.iterdir())
    assert any(goal.trace_id in p.name for p in files)
