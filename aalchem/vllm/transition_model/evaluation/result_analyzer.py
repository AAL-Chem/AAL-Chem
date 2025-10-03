import argparse
import json
import logging
from rdkit import Chem
from aalchem.vllm.transition_model.evaluation.molecule_comparer import MoleculeComparer
from typing import List, Dict, Optional
from dataclasses import dataclass


# pip install rdkit
from rdkit import Chem
from collections import Counter
import pandas as pd

# Setup logger
logger = logging.getLogger(__name__)


@dataclass
class ReactantPrediction:
    """Data class representing a single reactant permutation from model output"""
    reactants: List[str]
    non_canonicalized_reactants: List[str]
    is_valid: bool
    is_template: bool
    reasoning: str

class TransitionEvaluation:
    """Class for evaluating chemical reaction transition models"""
    
    def __init__(self):
        pass
        
    def extract_reactant_permutations(self, response_data: Dict) -> List[ReactantPrediction]:
        """
        Extract reactant permutations from model response data.
        
        Args:
            response_data (Dict): JSON response from the model API
            
        Returns:
            List[ReactantPrediction]: List of extracted reactant permutations
        """
        # Extract the parsed_response part if it exists, otherwise use the whole response
        parsed_response = response_data["parsed_response"] if "parsed_response" in response_data else response_data
        
        permutations = []
        
        # Iterate through all reaction analyses in the response 
        parsed_response = json.loads(parsed_response)
        for analysis in parsed_response["reaction_analysis"]:
            # Extract each reactant permutation
            for perm_data in analysis["reactant_permutations"]:

                # if the required fields are not present, skip this example
                if "reactants" not in perm_data or "is_valid" not in perm_data or "is_template" not in perm_data or "reasoning" not in perm_data:
                    continue

                canonical_list = []
                reactant_list_temp = perm_data["reactants"]

                # Split reactants containing '.' into separate reactants. LLMs are stupid.
                reactant_list = []
                for reactant in reactant_list_temp:
                    if '.' in reactant:
                        splitted_reactants = reactant.split('.')
                        reactant_list.extend(splitted_reactants)
                    else:
                        reactant_list.append(reactant)

                for reactant in reactant_list:
                    # Check if this specific reactant contains "*" AND if this permutation is marked as template
                    if perm_data["is_template"]:
                        # Don't canonicalize templates with asterisks, preserve them as-is
                        canonical_list.append(reactant)
                    else:
                        # Canonicalize non-template reactants
                        canonical_reactant = self.remove_atom_mapping_and_canonicalize(reactant)
                        canonical_list.append(canonical_reactant)

                permutation = ReactantPrediction(
                    reactants=canonical_list,
                    non_canonicalized_reactants=reactant_list,
                    is_valid=perm_data["is_valid"],
                    is_template=perm_data["is_template"],
                    reasoning=perm_data["reasoning"]
                )
                permutations.append(permutation)
        
        return permutations

    def remove_atom_mapping_and_canonicalize(self, smiles):
        """Remove atom mapping and canonicalize SMILES"""
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            # Try parsing as SMARTS if SMILES fails (for templates)
            mol = Chem.MolFromSmarts(smiles)
            if mol is None:
                return smiles # Return original if both fail
        for atom in mol.GetAtoms():
            atom.SetAtomMapNum(0)
        return Chem.MolToSmiles(mol, canonical=True)


    def evaluate_reactant_prediction(self, ground_truth_reactants:str, response_data:dict):
        # Step 1: Split ground truth into reactant parts and remove atom mapping
        ground_truth_reactants_raw = ground_truth_reactants.split('.')
        ground_truth_reactants = []

        # Remove atom mapping and canonicalize ground truth reactants
        for reactant in ground_truth_reactants_raw:
            canonical_reactant = self.remove_atom_mapping_and_canonicalize(reactant)
            ground_truth_reactants.append(canonical_reactant)

        # Step 2: Extract data from the response
        reactant_predictions = self.extract_reactant_permutations(response_data)

        reactant_comparer = MoleculeComparer()

        # validity statistics
        at_least_one_valid_non_template_reactant_pair_generated = False

        # match statistics
        template_match_found_without_stereochemistry = False
        template_match_found_with_stereochemistry = False
        match_found_without_stereochemistry = False
        match_found_with_stereochemistry = False

        # meta statistics
        number_of_reactant_predictions_created = 0
        number_of_reactants_per_prediction = []
        number_of_templates_created = 0
        number_of_non_templates_created = 0
        number_of_valid_predictions_without_templates = 0
        number_of_invalid_predictions_out_templates = 0

        # Evaluate each prediction
        for reactant_prediction in reactant_predictions:
            
            number_of_reactant_predictions_created = number_of_reactant_predictions_created + 1
            number_of_reactants_per_prediction.append(len(reactant_prediction.reactants))

            # For templates
            if reactant_prediction.is_template:
                # Pass the reactants list, not the whole ReactantPrediction object
                match_result_with_stereo = reactant_comparer.evaluate_reactant_pair(
                    ground_truth_reactants, 
                    reactant_prediction.reactants,  # Pass the list of reactants, not the object
                    is_template=True, 
                    consider_stereochemistry=True, 
                    comparison_type="template"
                )
                
                match_result_without_stereo = reactant_comparer.evaluate_reactant_pair(
                    ground_truth_reactants, 
                    reactant_prediction.reactants,  # Pass the list of reactants, not the object
                    is_template=True, 
                    consider_stereochemistry=False, 
                    comparison_type="template"
                )
                
                # Update the flags using OR logic - this preserves True values from previous matches
                # so we can detect if ANY prediction was a match across all permutations
                template_match_found_with_stereochemistry = template_match_found_with_stereochemistry or match_result_with_stereo["is_match"]
                template_match_found_without_stereochemistry = template_match_found_without_stereochemistry or match_result_without_stereo["is_match"]
                number_of_templates_created = number_of_templates_created + 1
            # For non-templates
            else:

                if reactant_comparer.validate_reactant_smiles(reactant_prediction.reactants):
                    at_least_one_valid_non_template_reactant_pair_generated = True

                if reactant_prediction.is_valid:
                    number_of_valid_predictions_without_templates = number_of_valid_predictions_without_templates + 1
                else:
                    number_of_invalid_predictions_out_templates = number_of_invalid_predictions_out_templates + 1

                match_result_with_stereo = reactant_comparer.evaluate_reactant_pair(
                    ground_truth_reactants, 
                    reactant_prediction.reactants,  # Pass the list of reactants, not the object
                    is_template=False, 
                    consider_stereochemistry=True, 
                    comparison_type="inchi"
                )
                
                match_result_without_stereo = reactant_comparer.evaluate_reactant_pair(
                    ground_truth_reactants, 
                    reactant_prediction.reactants,  # Pass the list of reactants, not the object
                    is_template=False, 
                    consider_stereochemistry=False, 
                    comparison_type="graph"
                )
                
                # Update the flags using OR logic - this preserves True values from previous matches
                # so we can detect if ANY prediction was a match across all permutations
                match_found_with_stereochemistry = match_found_with_stereochemistry or match_result_with_stereo["is_match"]
                match_found_without_stereochemistry = match_found_without_stereochemistry or match_result_without_stereo["is_match"]
                number_of_non_templates_created = number_of_non_templates_created + 1

        return {
            #validity
            "at_least_one_valid_non_template_reactant_pair_generated": at_least_one_valid_non_template_reactant_pair_generated,
            #performance
            "template_match_found_without_stereochemistry": template_match_found_without_stereochemistry,
            "template_match_found_with_stereochemistry": template_match_found_with_stereochemistry,
            "match_found_without_stereochemistry": match_found_without_stereochemistry,
            "match_found_with_stereochemistry": match_found_with_stereochemistry,
            # Statistics
            "number_of_reactant_predictions_created": number_of_reactant_predictions_created,
            "number_of_reactants_per_prediction": number_of_reactants_per_prediction,
            "number_of_templates_created": number_of_templates_created,
            "number_of_non_templates_created": number_of_non_templates_created,
            "number_of_valid_predictions_without_templates": number_of_valid_predictions_without_templates,
            "number_of_invalid_predictions_out_templates": number_of_invalid_predictions_out_templates
        }

    def evaluate_result(self, result_df):
        """
        Evaluate results from a DataFrame containing reaction predictions
        
        Args:
            result_df: DataFrame with reaction prediction data
        
        Returns:
            DataFrame: DataFrame with evaluation statistics
        """
        evaluation_results = []
        
        # for each row in result_df
        for i, (_, row) in enumerate(result_df.iterrows()):
            logger.info(f"Evaluating row {i}")

            # Parse JSON strings from the DataFrame
            template_data = json.loads(row["template_data"])
            parsed_response = row["parsed_response"]
            failed_json_parsing = row["failed_json_parsing"]
            # usage_stats = json.loads(row["usage_stats"])
            
            # getting ground truth data
            ground_truth_canonicalized_product = template_data["canonicalized_product"]
            ground_truth_reactants = template_data["ground_truth_reactants"]
            ground_truth_rxn_insight_name = template_data["rxn_insight_name"]
            ground_truth_rxn_insight_class = template_data["rxn_insight_class"]
            ground_truth_reaction_examples = template_data["training_set_reaction_examples"]
            ground_truth_number_of_reaction_examples = len(ground_truth_reaction_examples)

            if failed_json_parsing:
                # Provide default values for all metrics that would come from evaluate_reactant_prediction
                statistics = {
                    "at_least_one_valid_non_template_reactant_pair_generated": False,
                    "template_match_found_without_stereochemistry": False,
                    "template_match_found_with_stereochemistry": False,
                    "match_found_without_stereochemistry": False,
                    "match_found_with_stereochemistry": False,
                    "number_of_reactant_predictions_created": 0,
                    "number_of_reactants_per_prediction": [],
                    "number_of_templates_created": 0,
                    "number_of_non_templates_created": 0,
                    "number_of_valid_predictions_without_templates": 0,
                    "number_of_invalid_predictions_out_templates": 0,
                    "failed_json_parsing": True
                }
            else:
                # Compute evaluation statistics for this row
                statistics = self.evaluate_reactant_prediction(ground_truth_reactants, parsed_response)
                statistics["failed_json_parsing"] = False

            # Add metadata
            statistics["row_index"] = i
            statistics["ground_truth_canonicalized_product"] = ground_truth_canonicalized_product
            statistics["ground_truth_rxn_insight_name"] = ground_truth_rxn_insight_name
            statistics["ground_truth_rxn_insight_class"] = ground_truth_rxn_insight_class
            statistics["ground_truth_reaction_examples"] = ground_truth_reaction_examples
            statistics["ground_truth_number_of_reaction_examples"] = ground_truth_number_of_reaction_examples
            
            # meta information
            # statistics["prompt_tokens"] = usage_stats["prompt_tokens"]
            # statistics["completion_tokens"] = usage_stats["completion_tokens"]
            # statistics["total_tokens"] = usage_stats["total_tokens"]

            evaluation_results.append(statistics)
                    
        evaluation_results_df = pd.DataFrame(evaluation_results)

        return evaluation_results_df

def analyze_results(input: str, output: str, log_level: str) -> pd.DataFrame:
    """
    Command-line interface to evaluate reaction results and save the evaluation.
    
    Example usage:
    python result_analyzer.py --input /path/to/results.csv --output /path/to/evaluation_output.csv
    """
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # Load the input dataframe
        logger.info(f"Loading results from {input}")
        result_df = pd.read_csv(input)
        
        # Create evaluator and run evaluation
        evaluator = TransitionEvaluation()
        logger.info("Starting evaluation...")
        evaluation_results = evaluator.evaluate_result(result_df)

        assert len(result_df) == len(evaluation_results), "The length of the result dataframe must match the length of the evaluation results"

        # Save the evaluation results
        logger.info(f"Saving evaluation results to {output}")
        evaluation_results.to_csv(output, index=False)
        
    except Exception as e:
        logger.error(f"Error during evaluation: {str(e)}")
        return None
        
if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Evaluate chemical reaction predictions")
    parser.add_argument("--input", required=True, help="Path to the input CSV file containing reaction results")
    parser.add_argument("--output", required=True, help="Path to save the evaluation results CSV")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="INFO", 
                        help="Set logging level (default: INFO)")
    args = parser.parse_args()
    analyze_results(args.input, args.output, args.log_level)
