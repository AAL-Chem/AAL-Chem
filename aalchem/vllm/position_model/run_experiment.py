import json
import asyncio
import os
import logging
import pandas as pd
from aalchem.vllm.utils.template_populator import BasePopulatedTemplate
from aalchem.vllm.utils.experiment_runner import run_sample_experiment
from aalchem.vllm.position_model.template.reaction_position_template import ReactionPositionPopulator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("run_experiment")

if __name__ == "__main__":
    import sys
    
    # Require config path as command line argument
    if len(sys.argv) < 2:
        logger.error("Usage: python run_experiment.py <config_path>")
        sys.exit(1)
    
    config_path = sys.argv[1]
    
    # Validate config file exists
    if not os.path.exists(config_path):
        logger.error(f"Configuration file not found: {config_path}")
        sys.exit(1)
    
    # Load configuration to get template path
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    # Create template populator and populate templates
    populator = ReactionPositionPopulator(config["task_config"]["prompt_template_path"])

    reaction_data = pd.read_csv(config["task_config"]["data_path"])
    
    selected_columns = [
        "id", "canonicalized_product", "rxn_insight_name", "rxn_insight_class", "rxn_insight_class_retro",
        "changed_atom_sites", "changed_atom_and_bond_sites"
    ]
    reaction_data = reaction_data[selected_columns]

    # add the row number to id
    reaction_data['id'] = reaction_data.index.astype(str)
    populated_templates = populator.populate_templates(reaction_data.to_dict(orient='records'))

    # Run the experiment
    asyncio.run(run_sample_experiment(config_path, populated_templates))