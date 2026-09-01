"""
REBEL Relation Extractor
=========================
Uses the Babelscape/rebel-large model to extract semantic relations
(triplets) from text chunks.
"""

import logging
from typing import List, Dict, Any

try:
    from transformers import pipeline
except ImportError:
    pipeline = None

logger = logging.getLogger("Layer3.RelationExtractor")


class RelationExtractor:
    """
    Extracts Subject -> Predicate -> Object relationships from text.
    """

    def __init__(self, model_name: str = "Babelscape/rebel-large"):
        self.model_name = model_name
        self._pipeline = None

    def _load_model(self):
        if not pipeline:
            logger.warning("transformers not installed. Relation extraction skipped.")
            return

        if self._pipeline is None:
            logger.info(f"Loading REBEL Relation Extractor: {self.model_name}")
            try:
                # We use text2text-generation as REBEL is a seq2seq model (BART-based)
                self._pipeline = pipeline(
                    "text2text-generation", 
                    model=self.model_name, 
                    tokenizer=self.model_name,
                )
            except Exception as e:
                logger.error(f"Failed to load REBEL: {e}")
                self._pipeline = None

    def _extract_triplets(self, text: str) -> List[Dict[str, str]]:
        """
        Parses the specific output format of the REBEL model into triplets.
        """
        triplets = []
        current = 'x'
        subject, relation, object_ = '', '', ''
        
        text = text.strip()
        # The model outputs special tokens: <triplet> Subject <subj> Object <obj> Relation
        
        text = text.replace("<s>", "").replace("</s>", "").replace("<pad>", "")
        
        tokens = text.split()
        for token in tokens:
            if token == "<triplet>":
                current = 't'
                if relation != '':
                    triplets.append({'head': subject.strip(), 'type': relation.strip(), 'tail': object_.strip()})
                    relation = ''
                subject = ''
            elif token == "<subj>":
                current = 's'
                if relation != '':
                    triplets.append({'head': subject.strip(), 'type': relation.strip(), 'tail': object_.strip()})
                object_ = ''
            elif token == "<obj>":
                current = 'o'
                relation = ''
            else:
                if current == 't':
                    subject += ' ' + token
                elif current == 's':
                    object_ += ' ' + token
                elif current == 'o':
                    relation += ' ' + token
                    
        if subject != '' and relation != '' and object_ != '':
            triplets.append({'head': subject.strip(), 'type': relation.strip(), 'tail': object_.strip()})
            
        return triplets

    def extract(self, text: str) -> List[Dict[str, str]]:
        """
        Extracts relationship triplets from text.
        """
        self._load_model()
        if self._pipeline is None:
            return []

        try:
            # Generate raw token output
            # REBEL has a max length limit (typically 1024), we should chunk long text
            # For simplicity in this mock, we just truncate
            chunk = text[:1000]
            
            gen_kwargs = {
                "max_length": 256,
                "length_penalty": 0,
                "num_beams": 3,
                "num_return_sequences": 1,
            }
            
            output = self._pipeline(chunk, **gen_kwargs)
            raw_text = output[0]['generated_text']
            
            triplets = self._extract_triplets(raw_text)
            logger.debug(f"Extracted {len(triplets)} relations.")
            return triplets
            
        except Exception as e:
            logger.error(f"Relation extraction failed: {e}")
            return []
