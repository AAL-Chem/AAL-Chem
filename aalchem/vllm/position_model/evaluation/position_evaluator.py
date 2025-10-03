from typing import Set, Tuple
from scipy.spatial.distance import jaccard
from dataclasses import dataclass
import pandas as pd
import argparse

@dataclass
class MatchResult:
    """Data class to store match results for a single prediction."""
    is_exact_match: bool
    is_partial_match: bool
    precision: float
    recall: float
    jaccard_similarity: float
    is_rxn_name_correct: bool

class SimilarityCalculator:
    """
    Handles similarity calculations between atom sets.
    - Precision = |Intersection| / |Predicted| (How many of the predicted atoms are correct?)
    - Recall = |Intersection| / |Ground Truth| (How many of the ground truth atoms were found?)
    - Jaccard Similarity = |Intersection| / |Union| (Overall similarity between the sets)
    - If precision=1 and recall=1, the sets are identical, and Jaccard similarity is also 1.
    """
    
    @staticmethod
    def calculate_similarity_metrics(gt_atoms: Set[str], pred_atoms: Set[str]) -> Tuple[float, float, float]:
        """Calculate precision, recall, and Jaccard similarity."""
        if not gt_atoms:
            raise ValueError("Ground truth atoms cannot be empty")
        
        if not pred_atoms:
            return 0.0, 0.0, 0.0
        
        intersection = gt_atoms.intersection(pred_atoms)
        precision = len(intersection) / len(pred_atoms)
        recall = len(intersection) / len(gt_atoms)
        
        # Calculate Jaccard similarity using scipy
        all_atoms = sorted(gt_atoms.union(pred_atoms))
        vec1 = [1 if atom in gt_atoms else 0 for atom in all_atoms]
        vec2 = [1 if atom in pred_atoms else 0 for atom in all_atoms]
        
        jaccard_sim = 1 - jaccard(vec1, vec2)
        return precision, recall, jaccard_sim

    @staticmethod
    def calculate_all_metrics(gt_atoms: Set[str], pred_atoms: Set[str], ground_truth_name: str, prediction_name: str):
        """Calculate all metrics for pre-split atom sets and reaction names."""

        # assert that all are present
        assert gt_atoms, "Ground truth atom sets must be non-empty."
        assert ground_truth_name, "Ground truth reaction names must be non-empty."

        precision, recall, jaccard_sim = SimilarityCalculator.calculate_similarity_metrics(gt_atoms, pred_atoms)

        is_exact_match = (precision == 1.0 and recall == 1.0 and jaccard_sim == 1.0)
        # A partial match means we found at least one of the ground truth atoms.
        # Using recall is more intuitive here than precision.
        is_partial_match = (recall > 0.0)
        
        # if we find the correct position, do we find the correct reaction
        if is_partial_match:
            is_rxn_name_correct = ground_truth_name == prediction_name
        else:
            is_rxn_name_correct = False

        return MatchResult(
            is_exact_match=is_exact_match,
            is_partial_match=is_partial_match,
            precision=precision,
            recall=recall,
            jaccard_similarity=jaccard_sim,
            is_rxn_name_correct=is_rxn_name_correct
        )

def evaluate_position_predictions(input_csv: str, output_csv: str):
    """Main function to process CSV file and add evaluation results."""
   
    # Load CSV file
    df = pd.read_csv(input_csv)
    
    # Process each row
    results = []
    for _, row in df.iterrows():
        # sometimes gt_changed_atom_sites is nan because only the bonds change. we would then use gt_changed_atom_and_bond_sites
        if pd.notna(row["gt_changed_atom_sites"]):
            ground_truth_atoms = set(row["gt_changed_atom_sites"].split(' ')) if pd.notna(row["gt_changed_atom_sites"]) else set()
        else:
            ground_truth_atoms = set(row["gt_changed_atom_and_bond_sites"].split(' ')) if pd.notna(row["gt_changed_atom_and_bond_sites"]) else set()

        predicted_atoms = set(row["predicted_disconnection"].split(' ')) if pd.notna(row["predicted_disconnection"]) else set()

        # Get reaction names
        ground_truth_forward_reaction_name = row["gt_rxn_insight_name"]
        predicted_forward_reaction_name = row["predicted_forwardReaction"]

        # Calculate metrics
        try:
            match_result = SimilarityCalculator.calculate_all_metrics(
                ground_truth_atoms, predicted_atoms, ground_truth_forward_reaction_name, predicted_forward_reaction_name
            )
            
            # Convert MatchResult to dict with result_ prefix
            result_dict = {
                "result_is_exact_match": match_result.is_exact_match,
                "result_is_partial_match": match_result.is_partial_match,
                "result_precision": match_result.precision,
                "result_recall": match_result.recall,
                "result_jaccard_similarity": match_result.jaccard_similarity,
                "result_is_rxn_name_correct": match_result.is_rxn_name_correct
            }
        except AssertionError as e:
            # Handle empty ground truth case and assertion failures
            result_dict = {
                "result_is_exact_match": False,
                "result_is_partial_match": False,
                "result_precision": 0.0,
                "result_recall": 0.0,
                "result_jaccard_similarity": 0.0,
                "result_is_rxn_name_correct": False
            }
            print(f"Warning: {e} at row {len(results)}")
        
        results.append(result_dict)
    
    # Add results to dataframe
    result_df = pd.DataFrame(results)
    final_df = pd.concat([df, result_df], axis=1)
    
    # Save results
    final_df.to_csv(output_csv, index=False)
    print(f"Results saved to {output_csv}")
    
    # Print summary statistics
    print("\nSummary Statistics:")
    print(f"Total rows processed: {len(final_df)}")
    print(f"Exact matches: {final_df['result_is_exact_match'].sum()}")
    print(f"Partial matches: {final_df['result_is_partial_match'].sum()}")
    print(f"Correct Reaction Names: {final_df['result_is_rxn_name_correct'].sum()}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate position predictions")
    parser.add_argument("input_csv", help="Path to input CSV file")
    parser.add_argument("output_csv", help="Path to output CSV file")
    
    args = parser.parse_args()
 
    evaluate_position_predictions(args.input_csv, args.output_csv)