import argparse
from aalchem.models.gemini import GeminiVertexModel
from aalchem.config import PositionExperimentConfig
from aalchem.models.claude import AnthropicModel
from aalchem.models.open import OpenAIModel
from aalchem.vllm.position_model.template.reaction_position_template import ReactionPositionPopulator

import pandas as pd
import os
from pprint import pprint
from tqdm import tqdm


def evaluate_position_model(config: PositionExperimentConfig, skip_predict: bool = False) -> None:
    """
    Evaluate the position model.
    """

    # Create output directory
    os.makedirs(config.results_path, exist_ok=True)
    pprint(config.to_dict())
    config.to_json(config.results_path / 'experiment_config.json')

    populator = ReactionPositionPopulator(config.prompt_template_path)
    reaction_data = pd.read_csv(config.data_path)
    
    selected_columns = [
        "id", "canonicalized_product", "rxn_insight_name", "rxn_insight_class", "rxn_insight_class_retro",
        "changed_atom_sites", "changed_atom_and_bond_sites"
    ]
    reaction_data = reaction_data[selected_columns]
    
    reaction_data['id'] = reaction_data.index.astype(str)
    populated_templates = populator.populate_templates(reaction_data.to_dict(orient='records'))

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
    if not skip_predict:
        print("Predicting templates...")
        os.makedirs(json_dir, exist_ok=True)
        n_samples = len(populated_templates) if config.n_samples is None else config.n_samples
        for i, template in tqdm(enumerate(populated_templates[config.start_index:config.start_index+n_samples]), total=n_samples, desc="Predicting templates"):
            file_path = json_dir / f'response_{template.id}.json'
            print(file_path)
            if file_path.exists():
                print('Skipping existing file:', json_dir / f'response_{template.id}.json')
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
        config = PositionExperimentConfig().from_yaml(args.config)
    else:
        if args.model:
            config = PositionExperimentConfig(
                model_name=args.model
            )
        else:
            config = PositionExperimentConfig()

    if args.name:
        config.experiment_name = args.name

    evaluate_position_model(config, skip_predict=args.skip_predict)
