import boto3
import os
from typing import Dict, List, Any

class ComprehendService:
    def __init__(self):
        self.region = os.getenv('COMPREHEND_MEDICAL_REGION', 'us-east-1')
        self.client = boto3.client('comprehendmedical', region_name=self.region)
        self.enabled = os.getenv('COMPREHEND_MEDICAL_ENABLED', 'true').lower() == 'true'
    
    def detect_medical_entities(self, text: str) -> Dict[str, List[Dict[str, Any]]]:
        """Extract medical entities from text using Comprehend Medical or basic extraction"""
        if not self.enabled or not text.strip():
            return self._basic_medical_extraction(text)
        
        try:
            # Split text into chunks if too large (max 20KB for Comprehend Medical)
            chunks = self._split_text(text, max_size=20000)
            all_entities = self._empty_entities()
            
            for chunk in chunks:
                chunk_entities = self._process_chunk(chunk)
                self._merge_entities(all_entities, chunk_entities)
            
            return all_entities
            
        except Exception as e:
            print(f"Comprehend Medical error: {str(e)}")
            return self._empty_entities()
    
    def _process_chunk(self, text: str) -> Dict[str, List[Dict[str, Any]]]:
        """Process a single text chunk"""
        try:
            response = self.client.detect_entities_v2(Text=text)
            
            entities = self._empty_entities()
            
            for entity in response.get('Entities', []):
                category = entity.get('Category', '').lower()
                entity_type = entity.get('Type', '')
                
                entity_data = {
                    'text': entity.get('Text', ''),
                    'confidence': entity.get('Score', 0.0),
                    'type': entity_type,
                    'begin_offset': entity.get('BeginOffset', 0),
                    'end_offset': entity.get('EndOffset', 0)
                }
                
                # Map to our entity categories
                if category == 'medication':
                    entities['medications'].append(entity_data)
                elif category == 'medical_condition':
                    entities['conditions'].append(entity_data)
                elif category == 'procedure':
                    entities['procedures'].append(entity_data)
                elif category == 'anatomy':
                    entities['anatomy'].append(entity_data)
                elif category == 'test_treatment_procedure':
                    entities['tests'].append(entity_data)
            
            return entities
            
        except Exception as e:
            print(f"Chunk processing error: {str(e)}")
            return self._empty_entities()
    
    def _split_text(self, text: str, max_size: int = 20000) -> List[str]:
        """Split text into chunks for processing"""
        if len(text) <= max_size:
            return [text]
        
        chunks = []
        words = text.split()
        current_chunk = []
        current_size = 0
        
        for word in words:
            word_size = len(word) + 1  # +1 for space
            if current_size + word_size > max_size and current_chunk:
                chunks.append(' '.join(current_chunk))
                current_chunk = [word]
                current_size = word_size
            else:
                current_chunk.append(word)
                current_size += word_size
        
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        return chunks
    
    def _empty_entities(self) -> Dict[str, List[Dict[str, Any]]]:
        """Return empty entities structure"""
        return {
            'medications': [],
            'conditions': [],
            'procedures': [],
            'anatomy': [],
            'tests': []
        }
    
    def _merge_entities(self, target: Dict, source: Dict):
        """Merge entities from source into target"""
        for category in target:
            if category in source:
                target[category].extend(source[category])
    
    def _basic_medical_extraction(self, text: str) -> Dict[str, List[Dict[str, Any]]]:
        """Basic medical entity extraction using keyword matching"""
        import re
        
        entities = self._empty_entities()
        
        # Common medical terms patterns
        medication_patterns = [
            r'\b(metformin|insulin|aspirin|warfarin|lisinopril|atorvastatin|amlodipine|omeprazole|levothyroxine|simvastatin)\b',
            r'\b\w+\s*\d+\s*mg\b',  # medication with dosage
            r'\b\w+\s*tablet[s]?\b'
        ]
        
        condition_patterns = [
            r'\b(diabetes|hypertension|hyperlipidemia|depression|anxiety|asthma|copd|heart failure|stroke|cancer)\b',
            r'\b(type\s*[12]\s*diabetes)\b',
            r'\b(high\s*blood\s*pressure)\b'
        ]
        
        procedure_patterns = [
            r'\b(surgery|operation|procedure|biopsy|endoscopy|colonoscopy|mammography|ct\s*scan|mri|x-ray)\b',
            r'\b(blood\s*test|lab\s*work|laboratory)\b'
        ]
        
        anatomy_patterns = [
            r'\b(heart|lung|liver|kidney|brain|stomach|intestine|pancreas|thyroid|prostate)\b',
            r'\b(left\s*ventricle|right\s*atrium|aorta|vena\s*cava)\b'
        ]
        
        # Extract entities using patterns
        for pattern in medication_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                entities['medications'].append({
                    'text': match.group(),
                    'confidence': 0.7,  # Basic confidence
                    'type': 'MEDICATION',
                    'begin_offset': match.start(),
                    'end_offset': match.end()
                })
        
        for pattern in condition_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                entities['conditions'].append({
                    'text': match.group(),
                    'confidence': 0.7,
                    'type': 'MEDICAL_CONDITION',
                    'begin_offset': match.start(),
                    'end_offset': match.end()
                })
        
        for pattern in procedure_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                entities['procedures'].append({
                    'text': match.group(),
                    'confidence': 0.7,
                    'type': 'PROCEDURE',
                    'begin_offset': match.start(),
                    'end_offset': match.end()
                })
        
        for pattern in anatomy_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                entities['anatomy'].append({
                    'text': match.group(),
                    'confidence': 0.7,
                    'type': 'ANATOMY',
                    'begin_offset': match.start(),
                    'end_offset': match.end()
                })
        
        return entities
    
    def get_entity_summary(self, entities: Dict[str, List[Dict[str, Any]]]) -> Dict[str, int]:
        """Get summary count of entities by category"""
        return {
            category: len(entity_list) 
            for category, entity_list in entities.items()
        }
    
    def extract_high_confidence_entities(self, entities: Dict[str, List[Dict[str, Any]]], 
                                       min_confidence: float = 0.8) -> Dict[str, List[str]]:
        """Extract only high-confidence entity names"""
        high_confidence = {}
        
        for category, entity_list in entities.items():
            high_confidence[category] = [
                entity['text'] 
                for entity in entity_list 
                if entity['confidence'] >= min_confidence
            ]
        
        return high_confidence