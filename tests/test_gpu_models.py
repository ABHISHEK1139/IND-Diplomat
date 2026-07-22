import torch

print(f'\n--- CUDA Status ---')
print(f'CUDA Available: {torch.cuda.is_available()}')
if torch.cuda.is_available():
    print(f'Device: {torch.cuda.get_device_name()}')
    print(f'VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB')

print('\n--- Loading GLiNER (Layer 3 Entity Extractor) ---')
try:
    from dip.layer3_world_model.entity.gliner_extractor import EntityExtractor
    extractor = EntityExtractor()
    text = "The Prime Minister of India met with the President of Russia in Moscow today to discuss defense agreements."
    entities = extractor.extract(text)
    print(f'Input: "{text}"')
    print('Extracted Entities:')
    for e in entities:
        print(f' - {e}')
except Exception as e:
    print(f'GLiNER Error: {e}')
