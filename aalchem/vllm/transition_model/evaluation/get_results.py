from aalchem.vllm.transition_model.evaluation.calculate_statistics import calculate_statistics
from aalchem.vllm.transition_model.evaluation.result_analyzer import analyze_results
from aalchem.vllm.utils.evaluation.json_combiner import parse_jsons
from aalchem.vllm.utils.evaluation.json_combiner_proprietary import parse_jsons_proprietary
from aalchem.vllm.utils.evaluation.result_extractor import RetrosynthesisAnalysis

from aalchem.vllm.position_model.evaluation.calculate_statistics import calculate_statistics_position
from aalchem.vllm.position_model.evaluation.reaction_extractor import extract_reactions
from aalchem.vllm.position_model.evaluation.position_evaluator import evaluate_position_predictions
from aalchem.config import paths

from pathlib import Path
import pandas as pd
import argparse
import logging
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_transition_model_results(
        model_name: str, 
        eval_set_filepath: str | Path = paths.DEFAULT_TEST_SET_PATH_TRANSITION,
        json_dir: str = 'jsons',
        proprietary: bool = False
    ):
    """
    Get the results of a transition model.
    Provided the model name and the evaluation set filepath, this function will return the matched dataframe and the good samples.

    Runs:
    - Parse the json files using the json_combiner_original.py script
    - Run the retrosynthesis a}nalysis using RetrosynthesisAnalysis class
    - Return the matched dataframe and the good samples
    - Analyze the results using the result_analyzer.py script
    - Calculate the statistics using the calculate_statistics.py script
    """

    result_dir = paths.RESULTS / f'transition_model/{model_name}'
    out_file = result_dir / 'all_jsons.json'
    json_output_path = result_dir / json_dir
    if proprietary:
        jsons = parse_jsons_proprietary(folder=json_output_path, output=out_file)
    else:
        jsons = parse_jsons(folder=json_output_path, output=out_file)
    with open(out_file, "r") as f:
        jsons = json.load(f)

    # Load eval set
    eval_set = pd.read_csv(eval_set_filepath)
    retro = RetrosynthesisAnalysis(eval_set, jsons)
    out_df = retro.get_matched_dataframe()

    good_samples = out_df[out_df['failed_json_parsing'] == False]
    print(f"Good samples: {len(good_samples)}")
    print(f'Total samples: {len(out_df)}')
    print(out_df.failed_json_parsing.value_counts())

    out_df.to_csv(result_dir / 'matched_dataframe.csv', index=False)
    good_samples_path = result_dir / 'matched_good_samples.csv'
    good_samples.to_csv(good_samples_path, index=False)

    # Analyze results
    analyze_results_file = result_dir / 'analyze_results.csv'
    analyze_results(
        input=good_samples_path, 
        output=analyze_results_file, 
        log_level='INFO'
    )

    # Calculate statistics
    stats_file = result_dir / 'aggregated_statistics.csv'
    stats = calculate_statistics(
        input=analyze_results_file, 
        output=stats_file
    )

    return stats

def get_position_model_results(
        model_name: str, 
        eval_set_filepath: str | Path = paths.DEFAULT_TEST_SET_PATH_POSITION,
        json_dir: str = 'jsons',
        proprietary: bool = False
    ):
    """
    Get the results of a position model.
    """

    result_dir = paths.RESULTS / 'position_model' / model_name
    out_file = result_dir / 'all_jsons.json'
    json_output_path = result_dir / json_dir
    if proprietary:
        jsons = parse_jsons_proprietary(folder=str(json_output_path), output=str(out_file))
    else:
        jsons = parse_jsons(folder=json_output_path, output=out_file)
    print(f"Parsed {len(jsons)} jsons")
    with open(out_file, "r") as f:
        jsons = json.load(f)

    eval_set = pd.read_csv(eval_set_filepath)
    retro = RetrosynthesisAnalysis(eval_set, jsons)
    out_df = retro.get_matched_dataframe()
    good_samples = out_df[out_df['failed_json_parsing'] == False]
    print(f"Good samples: {len(good_samples)}")
    print(f'Total samples: {len(out_df)}')
    print(out_df.failed_json_parsing.value_counts())

    out_df.to_csv(result_dir / 'matched_dataframe.csv', index=False)
    good_samples_path = result_dir / 'matched_good_samples.csv'
    good_samples.to_csv(good_samples_path, index=False)

    # Analyze results
    out_file = result_dir / 'matched_good_samples_extracted.csv'
    extract_reactions(good_samples_path, out_file)

    ## Evaluate results
    in_file = out_file
    out_file = result_dir / 'matched_good_samples_extracted_evaluated.csv'
    evaluate_position_predictions(
        input_csv=in_file, 
        output_csv=out_file
    )

    # Calculate statistics
    stats_file = result_dir / 'aggregated_statistics.csv'
    best_examples_file = result_dir / 'best_examples.csv'
    stats = calculate_statistics_position(
        out_file, 
        best_examples=best_examples_file,
        aggregated_subset_stats=stats_file,
    )

    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Get the results of a transition model")
    parser.add_argument("--model_name", required=True, help="Name of the model")
    parser.add_argument("--eval_set_filepath", default=paths.DEFAULT_EVAL_SET_PATH, help="Path to the evaluation set")
    args = parser.parse_args()
    get_transition_model_results(args.model_name, args.eval_set_filepath)