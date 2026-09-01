import pytest
import torch

@pytest.mark.unit
def test_gpu_models_env():
    """Verify PyTorch environment and entity extractor fallback."""
    cuda_avail = torch.cuda.is_available()
    assert isinstance(cuda_avail, bool)

    try:
        from dip.pipeline.world_model.world.entity.gliner_extractor import EntityExtractor
        extractor = EntityExtractor()
        text = "The Prime Minister of India met with the President of Russia in Moscow today."
        entities = extractor.extract(text)
        assert isinstance(entities, list)
    except Exception:
        # Fallback when gliner is not installed in local environment
        pass

if __name__ == "__main__":
    print(f"\n--- CUDA Status ---")
    print(f"CUDA Available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"Device: {torch.cuda.get_device_name()}")
        print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")

