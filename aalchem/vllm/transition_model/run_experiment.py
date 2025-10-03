import json
import asyncio
import os
import logging
import pandas as pd
from aalchem.vllm.utils.template_populator import BasePopulatedTemplate
from aalchem.vllm.utils.experiment_runner import run_sample_experiment
from aalchem.vllm.transition_model.template.reaction_transition_template import ReactionTransitionPopulator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("run_experiment")


def get_test_row_and_train_examples(test_df, train_df, row_index):
    """
    Get a selected row from test and all matching examples from train based on rxn_insight_name.
    
    Args:
        test_df: Test dataframe
        train_df: Train dataframe  
        row_index: Index of row to select from test
    
    Returns:
        tuple: (selected_test_row, list_of_train_no_atom_mapping)
    """
    # Get the selected test row
    selected_test_row = test_df.iloc[row_index]
    
    # Get the rxn_insight_name from selected test row
    rxn_name = selected_test_row['rxn_insight_name']

    # we dont provide examples for OtherReaction
    if rxn_name == "OtherReaction":
        return selected_test_row, []
    else:
        # Filter train data for matching rxn_insight_name
        matching_train_rows = train_df[train_df['rxn_insight_name'] == rxn_name]

        if len(matching_train_rows) == 0:
            # No matching training examples found
            train_examples = []
        else:
            # Extract canonicalized_retro_reaction as list
            train_examples = matching_train_rows['canonicalized_retro_reaction'].tolist()

        return selected_test_row, train_examples


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
    populator = ReactionTransitionPopulator(config["task_config"]["prompt_template_path"])

    reaction_data_test = pd.read_csv(config["task_config"]["test_data_path"])
    reaction_data_train = pd.read_csv(config["task_config"]["trainings_data_reaction_examples_path"])
    
    # Assert required columns are present in test data
    required_test_columns = [
        'canonicalized_product', 'rxn_insight_name', 'rxn_insight_class', 
        'rxn_insight_class_retro', 'changed_atom_sites', 'changed_atom_and_bond_sites', 
        'canonicalized_reactants'
    ]
    for col in required_test_columns:
        assert col in reaction_data_test.columns, f"Required column '{col}' missing from test data"
    
    # rename canonicalized_reactants to ground_truth_reactants
    reaction_data_test = reaction_data_test.rename(columns={"canonicalized_reactants": "ground_truth_reactants"})

    # Assert required columns are present in training data
    required_train_columns = ['rxn_insight_name', 'canonicalized_retro_reaction']
    for col in required_train_columns:
        assert col in reaction_data_train.columns, f"Required column '{col}' missing from training data"
    
    # Create combined dataset with training examples for each test row
    combined_data = []
    for idx in range(len(reaction_data_test)):
        test_row, train_examples = get_test_row_and_train_examples(
            reaction_data_test, reaction_data_train, idx
        )
        
        # Create combined row with training examples
        combined_row = test_row.to_dict()
        combined_row['training_set_reaction_examples'] = train_examples
        combined_data.append(combined_row)
    
    reaction_data = pd.DataFrame(combined_data)

    # add the row number to id
    reaction_data['id'] = reaction_data.index.astype(str)
    populated_templates = populator.populate_templates(reaction_data.to_dict(orient='records'))

    # Run the experiment
    asyncio.run(run_sample_experiment(config_path, populated_templates))