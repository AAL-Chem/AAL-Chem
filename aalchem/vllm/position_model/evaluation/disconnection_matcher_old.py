"""
Disconnection Matching Evaluation Framework

This module provides a clean, modular framework for evaluating disconnection matching performance
between ground truth and predicted disconnections. The framework is separated into distinct
responsibilities:

1. DisconnectionParser: Handles parsing of disconnection strings and JSON responses
2. SimilarityCalculator: Calculates overlap and Jaccard similarity between atom sets
3. DisconnectionMatcher: Finds best matches between ground truth and predictions
4. EvaluationAnalyzer: Calculates comprehensive evaluation metrics
5. EvaluationReporter: Handles formatting and exporting of results

Example usage:
    # Load data
    df = pd.read_csv('results.csv')
    
    # Choose parser
    parser = NestedDisconnectionParser()
    
    # Find matches
    matcher = DisconnectionMatcher(df, parser)
    match_results = matcher.get_match_results()
    
    # Calculate metrics
    rxn_names = matcher.df['rxn_insight_name'].tolist()
    analyzer = EvaluationAnalyzer(match_results, rxn_names, matcher.df, parser)
    metrics = analyzer.calculate_all_metrics()
    
    # Report results
    reporter = EvaluationReporter()
    reporter.print_summary(metrics)
"""

import json
import pandas as pd
from typing import Dict, List, Tuple, Optional, Set, Union
from scipy.spatial.distance import jaccard
import numpy as np
from dataclasses import dataclass
from collections import defaultdict, Counter
from abc import ABC, abstractmethod

@dataclass
class Reaction:
    """Data class to store reaction disconnection information."""
    disconnection: Optional[str]
    forwardReaction: Optional[str]
    isInOntology: Optional[bool]
    retrosynthesis_importance: Optional[int]
    priority: Optional[int]
    rationale: Optional[str]


@dataclass
class MatchResult:
    """Data class to store match results for a single prediction."""
    is_exact_match: bool
    is_partial_match: bool
    match_position: int
    overlap_percentage: float
    jaccard_similarity: float
    predicted_disconnection: str
    predicted_rxn_name: str
    is_rxn_name_correct: bool


class DisconnectionParser(ABC):
    """Abstract base class for disconnection parsers."""
    
    @staticmethod
    def parse_disconnection_string(disconnection_str: str) -> Set[str]:
        """Parse disconnection string into normalized atom set."""
        if pd.isna(disconnection_str) or not disconnection_str:
            return set()
        
        atoms = disconnection_str.strip().split()
        return {atom.strip().lower() for atom in atoms if atom.strip()}
    
    @staticmethod
    @abstractmethod
    def extract_disconnections_from_json(parsed_response_str: str) -> List[Reaction]:
        """Extract disconnections from JSON response."""
        pass


class FlatJsonDisconnectionParser(DisconnectionParser):
    """Handles parsing of disconnection strings and flat JSON responses."""
    
    @staticmethod
    def extract_disconnections_from_json(parsed_response_str: str) -> List[Reaction]:
        """Extract disconnections from flat JSON response."""
        if pd.isna(parsed_response_str) or not parsed_response_str:
            return []
        
        try:
            parsed_data = json.loads(parsed_response_str)
            disconnections = parsed_data.get('disconnections', [])
            
            result = []
            for disc in disconnections:
                if isinstance(disc, dict) and 'disconnection' in disc:
                    result.append(Reaction(
                        disconnection=disc.get('disconnection'),
                        forwardReaction=disc.get('forwardReaction'),
                        isInOntology=disc.get('isInOntology'),
                        retrosynthesis_importance=disc.get('retrosynthesis_importance'),
                        priority=disc.get('Priority'),
                        rationale=disc.get('rationale')
                    ))
            return result
        except Exception as e:
            print(f"Error parsing JSON: {e}")
            return []


class NestedDisconnectionParser(DisconnectionParser):
    """Handles parsing of nested JSON responses with reactions array per disconnection."""
    
    @staticmethod
    def extract_disconnections_from_json(parsed_response_str: str) -> List[Reaction]:
        """Extract disconnections from nested JSON response format."""
        if pd.isna(parsed_response_str) or not parsed_response_str:
            return []
        
        try:
            parsed_data = json.loads(parsed_response_str)
            disconnections = parsed_data.get('disconnections', [])
            
            result = []
            for disc in disconnections:
                if isinstance(disc, dict) and 'disconnection' in disc:
                    disconnection_str = disc.get('disconnection')
                    reactions = disc.get('reactions', [])
                    
                    # For each reaction in the nested structure, create a Reaction object
                    for reaction in reactions:
                        if isinstance(reaction, dict):
                            result.append(Reaction(
                                disconnection=disconnection_str,
                                forwardReaction=reaction.get('forwardReaction'),
                                isInOntology=reaction.get('isInOntology'),
                                retrosynthesis_importance=reaction.get('Retrosynthesis Importance'),
                                priority=reaction.get('Priority'),
                                rationale=reaction.get('rationale')
                            ))
            return result
        except Exception as e:
            print(f"Error parsing nested JSON: {e}")
            return []


class SimilarityCalculator:
    """Handles similarity calculations between atom sets."""
    
    @staticmethod
    def calculate_overlap_and_jaccard(gt_atoms: Set[str], pred_atoms: Set[str]) -> Tuple[float, float]:
        """Calculate overlap percentage and Jaccard similarity."""
        if not gt_atoms:
            raise ValueError("Ground truth atoms cannot be empty")
        
        if not pred_atoms:
            return 0.0, 0.0
        
        intersection = gt_atoms.intersection(pred_atoms)
        overlap_percentage = len(intersection) / len(pred_atoms)
        
        # Calculate Jaccard similarity using scipy
        all_atoms = sorted(gt_atoms.union(pred_atoms))
        vec1 = [1 if atom in gt_atoms else 0 for atom in all_atoms]
        vec2 = [1 if atom in pred_atoms else 0 for atom in all_atoms]
        
        jaccard_sim = 1 - jaccard(vec1, vec2)
        return overlap_percentage, jaccard_sim


class DisconnectionMatcher:
    """Main class for matching disconnections between ground truth and predictions."""

    def __init__(self, df: pd.DataFrame, parser: DisconnectionParser, exclude_empty_responses: bool = False):
        """Initialize matcher with dataframe."""
        self.original_df = df.copy()
        self.exclude_empty_responses = exclude_empty_responses
        self.df = self._prepare_dataframe()
        self.match_results: List[MatchResult] = []
        self.match_results_df: Optional[pd.DataFrame] = None
        self.full_results_df: Optional[pd.DataFrame] = None
        
        # Initialize components
        self.parser = parser
        self.similarity_calc = SimilarityCalculator()
    
    def _prepare_dataframe(self) -> pd.DataFrame:
        """Prepare dataframe by filtering empty responses if requested."""
        df = self.original_df.copy()
        
        if self.exclude_empty_responses:
            mask = (df['parsed_response'].notna() & 
                   (df['parsed_response'].astype(str).str.strip() != ''))
            df = df[mask].copy()
        
        return df
    
    def _get_ground_truth_disconnection(self, row: pd.Series) -> str:
        """Extract ground truth disconnection from row."""
        gt_disconnection = row.get('changed_atom_sites')
        if pd.isna(gt_disconnection) or not gt_disconnection:
            gt_disconnection = row.get('changed_atom_and_bond_sites')
        
        if not gt_disconnection:
            raise ValueError("Missing ground truth disconnection data")
        
        return gt_disconnection
    
    def _find_best_match(self, gt_atoms: Set[str], predictions: List[Reaction], gt_rxn_name: str) -> MatchResult:
        """Find best matching prediction for ground truth."""
        best_jaccard = 0.0
        best_result = MatchResult(
            is_exact_match=False,
            is_partial_match=False,
            match_position=-1,
            overlap_percentage=0.0,
            jaccard_similarity=0.0,
            predicted_disconnection='',
            predicted_rxn_name='',
            is_rxn_name_correct=False
        )
        
        for i, pred in enumerate(predictions):
            pred_atoms = self.parser.parse_disconnection_string(pred.disconnection)
            if not pred_atoms:
                continue
                
            overlap_pct, jaccard_sim = self.similarity_calc.calculate_overlap_and_jaccard(gt_atoms, pred_atoms)
            
            if jaccard_sim > best_jaccard:
                pred_rxn_name = pred.forwardReaction or ''
                is_exact = overlap_pct == 1.0 and jaccard_sim == 1.0
                is_partial = overlap_pct > 0
                is_rxn_correct = (pred_rxn_name.strip() == gt_rxn_name.strip() 
                                if pred_rxn_name and is_partial else False)
                
                best_result = MatchResult(
                    is_exact_match=is_exact,
                    is_partial_match=is_partial,
                    match_position=i,
                    overlap_percentage=overlap_pct,
                    jaccard_similarity=jaccard_sim,
                    predicted_disconnection=pred.disconnection or '',
                    predicted_rxn_name=pred_rxn_name,
                    is_rxn_name_correct=is_rxn_correct
                )
                best_jaccard = jaccard_sim

        return best_result
    
    def get_match_results(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Get the match results and full results as DataFrames, running analysis if not done yet.
        
        Returns:
            Tuple of (best_found_match_df, original_df)
            - best_found_match_df: DataFrame with only the match result columns
            - original_df: Original dataframe unchanged
        """
        best_match_data = []
        
        for idx, row in self.df.iterrows():
            # Extract ground truth data
            gt_disconnection = self._get_ground_truth_disconnection(row)
            gt_rxn_name = row['rxn_insight_name']
            parsed_response = row['parsed_response']
            
            # Parse ground truth atoms
            gt_atoms = self.parser.parse_disconnection_string(gt_disconnection)
            if not gt_atoms:
                raise ValueError(f"Row {idx}: Empty ground truth atoms")
            
            # Extract predictions
            predictions = self.parser.extract_disconnections_from_json(parsed_response)
            
            # Find best match
            match_result = self._find_best_match(gt_atoms, predictions, gt_rxn_name)
            best_match_data.append(match_result.__dict__)

        # Create best found match DataFrame
        best_found_match_df = pd.DataFrame(best_match_data, index=self.df.index)
        
        return best_found_match_df, self.df


class EvaluationAnalyzer:
    """Dedicated class for calculating evaluation metrics from match results."""
    
    def __init__(self, match_results_df: pd.DataFrame, full_results_df: pd.DataFrame, parser: DisconnectionParser):
        """Initialize analyzer with match results dataframe, full results dataframe, and parser.
        
        Args:
            match_results_df: DataFrame containing match results with columns like is_exact_match, 
                             is_partial_match, match_position, overlap_percentage, jaccard_similarity, 
                             is_rxn_name_correct, predicted_disconnection, predicted_rxn_name
            full_results_df: DataFrame containing the original data with columns like rxn_insight_name, 
                           parsed_response, and ground truth columns
            parser: DisconnectionParser instance for parsing JSON responses
        """
        self.match_results_df = match_results_df.copy()
        self.full_results_df = full_results_df.copy()
        self.parser = parser
        
        # Validate required columns in match results
        required_match_cols = ['is_exact_match', 'is_partial_match', 'match_position', 
                              'overlap_percentage', 'jaccard_similarity', 'is_rxn_name_correct']
        missing_match_cols = [col for col in required_match_cols if col not in match_results_df.columns]
        if missing_match_cols:
            raise ValueError(f"Missing required columns in match results DataFrame: {missing_match_cols}")
        
        # Validate required columns in full results
        required_full_cols = ['rxn_insight_name', 'parsed_response']
        missing_full_cols = [col for col in required_full_cols if col not in full_results_df.columns]
        if missing_full_cols:
            raise ValueError(f"Missing required columns in full results DataFrame: {missing_full_cols}")
        
        # Ensure both dataframes have the same length and compatible indices
        if len(self.match_results_df) != len(self.full_results_df):
            raise ValueError(f"DataFrames must have the same length. "
                           f"Match results: {len(self.match_results_df)}, "
                           f"Full results: {len(self.full_results_df)}")
        
        # Reset indices to ensure alignment
        self.match_results_df = self.match_results_df.reset_index(drop=True)
        self.full_results_df = self.full_results_df.reset_index(drop=True)

    def calculate_all_metrics(self) -> Dict:
        """Calculate all evaluation metrics according to specification."""
        results = {}
        results.update(self._calculate_basic_metrics())
        results.update(self._calculate_exact_match_metrics())
        results.update(self._calculate_partial_match_metrics())
        results.update(self._calculate_rxn_insight_metrics())
        return results
    
    def _calculate_basic_metrics(self) -> Dict:
        """Calculate basic metrics from match results and full results dataframes."""
        # Basic counts from match results
        total_rows = len(self.match_results_df)
        exact_matches = self.match_results_df['is_exact_match'].sum()
        partial_matches = self.match_results_df['is_partial_match'].sum()
        
        # Calculate metrics for suggested alternatives using full results
        total_suggested_alternatives = 0
        unique_disconnections = set()
        disconnection_reaction_counts = defaultdict(int)
        
        # Process each row in full results to get suggestion statistics
        for idx, row in self.full_results_df.iterrows():
            parsed_response = row['parsed_response']
            predictions = self.parser.extract_disconnections_from_json(parsed_response)
            total_suggested_alternatives += len(predictions)
            
            # Track unique disconnection sides and their reaction counts
            for pred in predictions:
                if pred.disconnection:
                    disconnection_str = pred.disconnection.strip()
                    unique_disconnections.add(disconnection_str)
                    disconnection_reaction_counts[disconnection_str] += 1
        
        # Calculate derived metrics
        analyzed_rows = len(self.full_results_df)
        avg_suggested_alternatives = total_suggested_alternatives / analyzed_rows if analyzed_rows > 0 else 0
        total_disconnection_sides = len(unique_disconnections)
        avg_reactions_per_disconnection = (sum(disconnection_reaction_counts.values()) / 
                                         len(disconnection_reaction_counts)) if disconnection_reaction_counts else 0
        
        return {
            "total_rows": total_rows,
            "exact_matches": int(exact_matches),
            "partial_matches": int(partial_matches),
            "number_of_suggested_alternatives": avg_suggested_alternatives,
            "total_suggested_alternatives": total_suggested_alternatives,
            "total_suggested_disconnection_sides": total_disconnection_sides,
            "avg_suggested_reactions_per_disconnection_side": avg_reactions_per_disconnection
        }
    
    def _calculate_exact_match_metrics(self) -> Dict:
        """Calculate metrics for exact matches from match results dataframe."""
        exact_matches_df = self.match_results_df[self.match_results_df['is_exact_match']]
        
        if len(exact_matches_df) == 0:
            return {
                "exact_match_priority_positions": [],
                "avg_exact_match_position": 0,
                "exact_matches_correct_reaction": 0,
                "exact_matches_correct_reaction_ratio": 0.0,
                "first_position_exact_match_rate": 0
            }
        
        positions = exact_matches_df['match_position'].tolist()
        
        # Create array of counts from position 0 to max position
        max_position = max(positions) if positions else 0
        position_counts = [0] * (max_position + 1)
        for pos in positions:
            position_counts[pos] += 1
        
        # Calculate reaction name correctness and position metrics
        correct_reactions = exact_matches_df['is_rxn_name_correct'].sum()
        first_position_count = (exact_matches_df['match_position'] == 0).sum()
        
        return {
            "exact_match_priority_positions": position_counts,
            "avg_exact_match_position": float(np.mean(positions)),
            "exact_matches_correct_reaction": int(correct_reactions),
            "exact_matches_correct_reaction_ratio": correct_reactions / len(exact_matches_df),
            "first_position_exact_match_rate": first_position_count / len(exact_matches_df)
        }
    
    def _calculate_partial_match_metrics(self) -> Dict:
        """Calculate metrics for partial matches from match results dataframe."""
        partial_matches_df = self.match_results_df[self.match_results_df['is_partial_match']]
        
        if len(partial_matches_df) == 0:
            return {
                "partial_match_priority_positions": [],
                "partial_matches_correct_reaction": 0,
                "partial_matches_correct_reaction_ratio": 0.0,
                "first_position_partial_match_rate": 0,
                "avg_overlap_percentage": 0.0,
                "avg_jaccard_similarity": 0.0
            }
        
        positions = partial_matches_df['match_position'].tolist()
        
        # Create array of counts from position 0 to max position
        max_position = max(positions) if positions else 0
        position_counts = [0] * (max_position + 1)
        for pos in positions:
            position_counts[pos] += 1
        
        # Calculate reaction name correctness and position metrics for partial matches
        correct_reactions = partial_matches_df['is_rxn_name_correct'].sum()
        first_position_count = (partial_matches_df['match_position'] == 0).sum()
        
        # Calculate averages including all match results (matches and non-matches)
        # This gives us the overall average overlap and similarity across all predictions
        all_overlaps = self.match_results_df['overlap_percentage']
        all_jaccards = self.match_results_df['jaccard_similarity']
        
        return {
            "partial_match_priority_positions": position_counts,
            "partial_matches_correct_reaction": int(correct_reactions),
            "partial_matches_correct_reaction_ratio": correct_reactions / len(partial_matches_df),
            "first_position_partial_match_rate": first_position_count / len(partial_matches_df),
            "avg_overlap_percentage": float(all_overlaps.mean()),
            "avg_jaccard_similarity": float(all_jaccards.mean())
        }
    
    def _calculate_rxn_insight_metrics(self) -> Dict:
        """Calculate metrics per reaction insight class using aligned dataframes."""
        exact_per_class = {}
        partial_per_class = {}
        
        # Get unique reaction names from full results
        unique_rxn_names = self.full_results_df['rxn_insight_name'].unique()
        
        for rxn_name in unique_rxn_names:
            # Get boolean mask for this reaction name in full results
            rxn_mask = self.full_results_df['rxn_insight_name'] == rxn_name
            
            # Apply the same mask to match results (since indices are aligned)
            rxn_match_results = self.match_results_df[rxn_mask]
            
            # Calculate exact and partial matches for this reaction class
            exact_matches_df = rxn_match_results[rxn_match_results['is_exact_match']]
            partial_matches_df = rxn_match_results[rxn_match_results['is_partial_match']]
            total_samples = len(rxn_match_results)
            
            # Calculate correct reaction counts
            exact_correct = exact_matches_df['is_rxn_name_correct'].sum() if len(exact_matches_df) > 0 else 0
            partial_correct = partial_matches_df['is_rxn_name_correct'].sum() if len(partial_matches_df) > 0 else 0
            
            # Store exact match metrics for this reaction class
            exact_per_class[rxn_name] = {
                "matched": len(exact_matches_df),
                "possible_matches": total_samples,
                "ratio": len(exact_matches_df) / total_samples if total_samples > 0 else 0.0,
                "correct_reaction": int(exact_correct),
                "correct_reaction_ratio": exact_correct / len(exact_matches_df) if len(exact_matches_df) > 0 else 0.0
            }
            
            # Store partial match metrics for this reaction class
            partial_per_class[rxn_name] = {
                "matched": len(partial_matches_df),
                "possible_matches": total_samples,
                "ratio": len(partial_matches_df) / total_samples if total_samples > 0 else 0.0,
                "correct_reaction": int(partial_correct),
                "correct_reaction_ratio": partial_correct / len(partial_matches_df) if len(partial_matches_df) > 0 else 0.0
            }
        
        return {
            "exact_match_per_rxn_insight_class": exact_per_class,
            "partial_match_per_rxn_insight_class": partial_per_class
        }


class EvaluationReporter:
    """Handles reporting and exporting of evaluation results."""
    
    @staticmethod
    def print_summary(results: Dict) -> None:
        """Print formatted summary of evaluation results."""
        print("="*60)
        print("DISCONNECTION MATCHING EVALUATION SUMMARY")
        print("="*60)
        
        print(f"Total rows: {results['total_rows']}")
        print(f"Average suggested alternatives: {results['number_of_suggested_alternatives']:.2f}")
        print(f"Total suggested alternatives: {results['total_suggested_alternatives']}")
        print(f"Total suggested disconnection sides: {results['total_suggested_disconnection_sides']}")
        print(f"Average reactions per disconnection side: {results['avg_suggested_reactions_per_disconnection_side']:.2f}")
        print(f"Exact matches: {results['exact_matches']} ({results['exact_matches']/results['total_rows']:.2%})")
        print(f"Partial matches: {results['partial_matches']} ({results['partial_matches']/results['total_rows']:.2%})")
        
        if results['exact_matches'] > 0:
            print(f"\nExact Match Analysis:")
            print(f"  - Correct reactions: {results['exact_matches_correct_reaction']}")
            print(f"  - First position rate: {results['first_position_exact_match_rate']:.2%}")
            print(f"  - Average position: {results['avg_exact_match_position']:.2f}")
            print(f"  - Position distribution: {results['exact_match_priority_positions']}")
        
        if results['partial_matches'] > 0:
            print(f"\nPartial Match Analysis:")
            print(f"  - Correct reactions: {results['partial_matches_correct_reaction']}")
            print(f"  - First position rate: {results['first_position_partial_match_rate']:.2%}")
            print(f"  - Average overlap: {results['avg_overlap_percentage']:.2%}")
            print(f"  - Average Jaccard: {results['avg_jaccard_similarity']:.2%}")
            print(f"  - Position distribution: {results['partial_match_priority_positions']}")
        
        print(f"\nReaction Class Analysis:")
        print(f"  - Exact matches per class: {len(results['exact_match_per_rxn_insight_class'])} classes")
        print(f"  - Partial matches per class: {len(results['partial_match_per_rxn_insight_class'])} classes")
    
    @staticmethod
    def save_match_results_dataframe(match_results_df: pd.DataFrame, filepath: str) -> None:
        """Save the match results DataFrame to CSV file."""
        match_results_df.to_csv(filepath, index=False)
        print(f"Match results dataframe exported to {filepath}")

    @staticmethod
    def save_full_results_dataframe(full_results_df: pd.DataFrame, filepath: str) -> None:
        """Save the full results DataFrame to CSV file."""
        full_results_df.to_csv(filepath, index=False)
        print(f"Full results dataframe exported to {filepath}")

    @staticmethod
    def export_metrics_summary(results: Dict, filepath: str) -> None:
        """Export metrics summary to JSON file."""
        # Convert numpy types for JSON serialization
        json_safe_results = {}
        for key, value in results.items():
            if isinstance(value, (pd.Series, pd.Index)):
                json_safe_results[key] = value.tolist()
            elif hasattr(value, 'item'):  # numpy scalar
                json_safe_results[key] = value.item()
            elif isinstance(value, dict):
                json_safe_results[key] = {str(k): int(v) if hasattr(v, 'item') else v 
                                        for k, v in value.items()}
            else:
                json_safe_results[key] = value
        
        with open(filepath, 'w') as f:
            json.dump(json_safe_results, f, indent=4)
        print(f"Metrics summary exported to {filepath}")


def run_evaluation_pipeline(csv_path: str, exclude_empty: bool = False, flat_json: bool = False) -> Tuple[pd.DataFrame, pd.DataFrame, Dict]:
    """
    Convenience function to run the complete evaluation pipeline.
    
    Args:
        csv_path: Path to CSV file with evaluation data
        exclude_empty: Whether to exclude rows with empty responses
        flat_json: Whether to use flat JSON parser instead of nested
        
    Returns:
        Tuple of (match_results_df, full_results_df, metrics_dict)
    """
    # Load data
    df = pd.read_csv(csv_path)
    
    # Choose parser based on format
    parser = FlatJsonDisconnectionParser() if flat_json else NestedDisconnectionParser()
    
    # Run matching
    matcher = DisconnectionMatcher(df, parser, exclude_empty_responses=exclude_empty)
    match_results_df, full_results_df = matcher.get_match_results()
    
    # Calculate metrics
    analyzer = EvaluationAnalyzer(match_results_df, full_results_df, parser)
    metrics = analyzer.calculate_all_metrics()
    
    return match_results_df, full_results_df, metrics

def main():
    """Main function for command-line usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Clean Disconnection Matching Evaluation")
    parser.add_argument("--csv", required=True, help="Path to CSV file with parsed results")
    parser.add_argument("--export", help="Path to export analysis results")
    parser.add_argument("--exclude-empty", action="store_true", 
                       help="Exclude rows with empty or null parsed_response from analysis")
    parser.add_argument("--flat-json", action="store_true",
                       help="Use flat JSON parser instead of nested JSON parser")
    args = parser.parse_args()
    
    # Load and validate data
    df = pd.read_csv(args.csv)
    required_columns = ['rxn_insight_name', 'parsed_response']
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")
    
    # Print initial statistics
    total_rows = len(df)
    empty_responses = df['parsed_response'].isna().sum() + \
                     (df['parsed_response'].astype(str).str.strip() == '').sum()
    
    print(f"Initial dataset: {total_rows} rows")
    if args.exclude_empty:
        print(f"Excluding {empty_responses} rows with empty parsed_response")
        print(f"Analyzing {total_rows - empty_responses} rows")
    
    # Choose parser based on format
    disconnection_parser = FlatJsonDisconnectionParser() if args.flat_json else NestedDisconnectionParser()
    print(f"Using parser: {disconnection_parser.__class__.__name__}")
    
    # Run matching analysis
    matcher = DisconnectionMatcher(df, disconnection_parser, exclude_empty_responses=args.exclude_empty)
    match_results_df, full_results_df = matcher.get_match_results()
    
    # Run evaluation analysis
    analyzer = EvaluationAnalyzer(match_results_df, full_results_df, disconnection_parser)
    results = analyzer.calculate_all_metrics()
    
    # Report results
    reporter = EvaluationReporter()
    reporter.print_summary(results)
    
    # Export if requested
    if args.export:
        # Save both dataframes
        match_results_path = args.export.replace('.csv', '_match_results.csv')
        reporter.save_match_results_dataframe(match_results_df, match_results_path)

        full_results_path = args.export.replace('.csv', '_full_results.csv')
        reporter.save_full_results_dataframe(full_results_df, full_results_path)
        
        # Save metrics summary
        summary_path = args.export.replace('.csv', '_summary.json')
        reporter.export_metrics_summary(results, summary_path)


if __name__ == "__main__":
    main()