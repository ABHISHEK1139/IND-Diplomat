# Layer-2 Architecture

Layer-2 is a signal extraction and normalization factory.

## Structure

- `0_sources/`: external intake connectors.
- `1_parsing/`: document parsing/chunking/segmentation.
- `2_signal_extraction/`: geopolitical signal extraction.
- `3_normalization/`: identity resolution and deduplication.
- `4_storage/`: memory/index/vector persistence.
- `5_access_api/`: controlled access/query APIs for upper layers.

## Contract

Layer-2 outputs structured signals and access APIs.

Preferred flow:

`documents -> parsed units -> signals -> normalized signals -> storage -> access API`

Layer-2 should not perform Layer-3 state construction or Layer-4 causal explanation.

## Compatibility

Legacy imports at `Layer2_Knowledge/*.py`, `Layer2_Knowledge/assimilation/`,
`Layer2_Knowledge/translators/`, `Layer2_Knowledge/retrieval/`,
`Layer2_Knowledge/legal_signal_extractor/`, and `Layer2_Knowledge/signals/`
are maintained via compatibility shims.

