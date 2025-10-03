import argparse
from aalchem.vllm.transition_model.run_experiment import get_test_row_and_train_examples
from aalchem.vllm.utils.evaluation.json_combiner import parse_jsons
from aalchem.vllm.transition_model.evaluation.result_analyzer import analyze_results
from aalchem.vllm.transition_model.evaluation.calculate_statistics import calculate_statistics
from aalchem.vllm.transition_model.template.reaction_transition_template import ReactionTransitionPopulator
from aalchem.vllm.utils.evaluation.result_extractor import RetrosynthesisAnalysis
from aalchem.config import ExperimentConfig
from aalchem.models.gemini import GeminiVertexModel
from aalchem.models.claude import AnthropicModel
from aalchem.models.open import OpenAIModel

import pandas as pd
import os
from pprint import pprint
from tqdm import tqdm


def load_data(config: ExperimentConfig):
    """
    Load the data for the transition model.
    """
    reaction_data_test = pd.read_csv(config.eval_set_filepath)
    reaction_data_train = pd.read_csv(config.train_filepath)

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

    return reaction_data
 

def evaluate_transition_model(config: ExperimentConfig, skip_predict: bool = False) -> None:
    """
    Evaluate the transition model.
    """

    # Create output directory
    os.makedirs(config.results_path, exist_ok=True)
    pprint(config.to_dict())
    config.to_json(config.results_path / 'experiment_config.json')

    # Load data
    populator = ReactionTransitionPopulator(config.prompt_template_path)
    reaction_data = load_data(config)
    populated_templates = populator.populate_templates(
        reaction_data.to_dict(orient='records'),
        use_train_examples=config.use_examples
        )

    # Load model
    model = config.model_name
    if 'gemini' in model:
        model = GeminiVertexModel(model)
    elif 'gemma' in model:
        model = GeminiVertexModel(model)
    elif 'anthropic' in model or 'claude' in model:
        model = AnthropicModel(model)
    elif '-o' in model or 'gpt' in model:
        model = OpenAIModel(
            model,
            reasoning=config.reasoning,
            verbosity=config.verbosity
        )
    else:
        raise ValueError(f"Model {model} not supported")

    # Predict
    json_dir = config.results_path / 'jsons'
    os.makedirs(json_dir, exist_ok=True)
    if not skip_predict:
        print("Predicting templates...")
        n_samples = len(populated_templates) if config.n_samples is None else config.n_samples
        for i, template in tqdm(enumerate(populated_templates[config.start_index:config.start_index+n_samples]), total=n_samples, desc="Predicting templates"):
            file_path = json_dir / f'response_{template.id}.json'
            print(file_path)
            if file_path.exists():
                print('Skipping existing file:' / json_dir / f'response_{template.id}.json')
                continue
            model.predict_template(
                template,
                thinking=config.thinking, 
                thinking_budget_tokens=config.thinking_budget_tokens,
                write_to_file=True,
                output_dir=json_dir
            )
    else:
        print("Skipping prediction...")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Evaluate a transition model")
    parser.add_argument('-n', '--name', type=str, default=None, help="Name of the experiment")
    parser.add_argument('-c', '--config', type=str, default=None, help="Path to .yml config file")
    parser.add_argument('-m', '--model', type=str, default=None, help="Name of the model")
    parser.add_argument('-s', '--skip_predict', action='store_true', help="Skip prediction")
    args = parser.parse_args()

    if args.config and os.path.isfile(args.config):
        print(f"Loading config from {args.config}")
        config = ExperimentConfig().from_yaml(args.config)
    else:
        config = ExperimentConfig()

    if args.name:
        config.experiment_name = args.name

    evaluate_transition_model(config, skip_predict=args.skip_predict)
