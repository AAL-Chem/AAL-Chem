from typing import List, Dict, Any, Union
import logging
from dataclasses import dataclass
from abc import ABC, abstractmethod
from aalchem.vllm.utils.template_populator import BasePopulatedTemplate, TaskSpecificTemplatePopulator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("template_populator")


@dataclass
class ReactionPositionTemplate(BasePopulatedTemplate):
    """Populated template for reaction position prediction tasks."""
    canonicalized_product: str
    rxn_insight_name: str
    rxn_insight_class: str
    rxn_insight_class_retro: str
    changed_atom_sites: str
    changed_atom_and_bond_sites: str
    
    def get_required_fields(self) -> List[str]:
        return ["id", "canonicalized_product", "rxn_insight_name", "rxn_insight_class", "rxn_insight_class_retro", "changed_atom_sites", "changed_atom_and_bond_sites", "prompt"]

class ReactionPositionPopulator(TaskSpecificTemplatePopulator):
    """Template populator for reaction position prediction tasks."""
    
    def populate_templates(self, data_points: List[Dict[str, Any]]) -> List[ReactionPositionTemplate]:
        results = []
        
        for i, data in enumerate(data_points):
            try:
                # Format template with data - placeholder for actual template formatting
                prompt = self.template.replace("<canonicalized_product>", data.get("canonicalized_product")) if "<canonicalized_product>" in self.template else self.template

                result = ReactionPositionTemplate(
                    id=data["id"],
                    canonicalized_product=data["canonicalized_product"],
                    rxn_insight_name=data["rxn_insight_name"],
                    rxn_insight_class=data["rxn_insight_class"],
                    rxn_insight_class_retro=data["rxn_insight_class_retro"],
                    changed_atom_sites=data["changed_atom_sites"],
                    changed_atom_and_bond_sites=data["changed_atom_and_bond_sites"],
                    prompt=prompt
                )
                results.append(result)
            except (KeyError, ValueError) as e:
                logger.warning(f"Error creating template for data point {i}: {e}")
            except Exception as e:
                logger.warning(f"Unexpected error formatting template for data point {i}: {e}")
        
        logger.info(f"Populated {len(results)} reaction position templates")
        return results