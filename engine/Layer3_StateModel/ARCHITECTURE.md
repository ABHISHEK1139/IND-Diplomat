# Layer-3 Architecture

Layer-3 is measurement and state construction only.

## Structure

- `schemas/`: data contracts (`StateContext`, state vectors).
- `binding/`: evidence/entity binding and graph links.
- `temporal/`: recency, timeline, precursor tracking.
- `credibility/`: contradiction/corroboration/source credibility.
- `construction/`: country and relationship state construction.
- `scoring/`: confidence and evidence-gate scoring.
- `interface/`: single external API for Layer-4.

## External Contract

Layer-4 should consume Layer-3 through:

`Layer3_StateModel.interface.state_provider`

and not import internal Layer-3 components directly.

Layer-3 should consume Layer-2 only through structured signal contracts and
access APIs, not Layer-2 storage internals.
