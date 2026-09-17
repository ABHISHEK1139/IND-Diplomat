import pytest
import torch

pytestmark = pytest.mark.unit


def test_torch_cuda_probe():
    """Deterministic unit check: the CUDA probe itself behaves."""
    cuda_avail = torch.cuda.is_available()
    assert isinstance(cuda_avail, bool)


@pytest.mark.integration
def test_gliner_entity_extraction():
    """Optional model integration: runs only when gliner is installed.

    TEST-02: previously this swallowed every exception and always passed,
    which hid real model failures. A missing model now skips; a present
    but broken model fails loudly.
    """
    gliner = pytest.importorskip("gliner", reason="gliner not installed")
    from dip.pipeline.world_model.world.entity.gliner_extractor import EntityExtractor
    extractor = EntityExtractor()
    text = "The Prime Minister of India met with the President of Russia in Moscow today."
    entities = extractor.extract(text)
    assert isinstance(entities, list)

if __name__ == "__main__":
    print(f"\n--- CUDA Status ---")
    print(f"CUDA Available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"Device: {torch.cuda.get_device_name()}")
        print(f"VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")

