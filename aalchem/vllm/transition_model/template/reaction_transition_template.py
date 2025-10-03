from typing import List, Dict, Any, Union
import logging
import pandas as pd
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
class ReactionTransitionTemplate(BasePopulatedTemplate):
    """Populated template for reaction transition prediction tasks."""
    # default input
    canonicalized_product: str
    rxn_insight_name: str
    rxn_insight_class: str
    rxn_insight_class_retro: str
    changed_atom_sites: str
    changed_atom_and_bond_sites: str
    # training set examples
    training_set_reaction_examples: List[str]
    # ground truth - this should be str, not List[str] based on your data
    ground_truth_reactants: str

    
    def get_required_fields(self) -> List[str]:
        return ["id", "canonicalized_product", "rxn_insight_name", "rxn_insight_class", "rxn_insight_class_retro", "changed_atom_sites", "changed_atom_and_bond_sites", "ground_truth_reactants", "training_set_reaction_examples", "prompt"]

class ReactionTransitionPopulator(TaskSpecificTemplatePopulator):
    """Template populator for reaction transition prediction tasks."""
    
    def populate_templates(self, data_points: List[Dict[str, Any]], use_train_examples: bool = True) -> List[ReactionTransitionTemplate]:
        results = []
        
        for i, data in enumerate(data_points):
            try:
                
                # Determine disconnection bonds (prioritize changed_atom_sites, fallback to changed_atom_and_bond_sites)
                if pd.notna(data['changed_atom_sites']):
                    disconnection_bonds = data['changed_atom_sites']
                else:
                    disconnection_bonds = data['changed_atom_and_bond_sites']
                
                # Format training examples as a list string
                if data["training_set_reaction_examples"]:
                    training_set_reaction_examples_formatted = '[\n' + ',\n'.join([f'    "{example}"' for example in data["training_set_reaction_examples"]]) + '\n]'
                else:
                    training_set_reaction_examples_formatted = '[]'

                # Replace placeholders in template
                populated_content = self.template.replace('<REACTION_POSITION>', str(disconnection_bonds))
                populated_content = populated_content.replace('<REACTION_NAME>', data['rxn_insight_name'])
                populated_content = populated_content.replace('<PRODUCT_SMILES>', data['canonicalized_product'])
                if use_train_examples:
                    populated_content = populated_content.replace('<TRAIN_REACTION_EXAMPLES>', training_set_reaction_examples_formatted)
                    training_set_reaction_examples = data["training_set_reaction_examples"]
                else:
                    populated_content = populated_content.replace('"retrosynthesis_reaction_examples": <TRAIN_REACTION_EXAMPLES>', '')
                    training_set_reaction_examples = []

                prompt = populated_content

                result = ReactionTransitionTemplate(
                    id=data["id"],
                    canonicalized_product=data["canonicalized_product"],
                    rxn_insight_name=data["rxn_insight_name"],
                    rxn_insight_class=data["rxn_insight_class"],
                    rxn_insight_class_retro=data["rxn_insight_class_retro"],
                    changed_atom_sites=data["changed_atom_sites"],
                    changed_atom_and_bond_sites=data["changed_atom_and_bond_sites"],
                    training_set_reaction_examples=training_set_reaction_examples,
                    ground_truth_reactants=data["ground_truth_reactants"],
                    prompt=prompt
                )
                results.append(result)
            except (KeyError, ValueError) as e:
                logger.warning(f"Error creating template for data point {i}: {e}")
            except Exception as e:
                logger.warning(f"Unexpected error formatting template for data point {i}: {e}")
        
        logger.info(f"Populated {len(results)} reaction transition templates")
        return results