import pandas as pd
import numpy as np
import argparse
import logging
from typing import Dict, List, Any
from collections import defaultdict

# Setup logger
logger = logging.getLogger(__name__)

class PerformanceCalculator:
    """Calculate performance statistics for chemical reaction evaluation results"""
    
    def __init__(self):
        pass
    
    def calculate_accuracy(self, predictions: np.ndarray) -> float:
        """
        Calculate accuracy for top-1 evaluation where we expect one match per sample.
        For top-1 evaluation, precision = recall = f1 = accuracy = success_rate
        
        Args:
            predictions: Binary array where 1 indicates a match was found
            
        Returns:
            Accuracy (success rate): sum(successes) / len(all)
        """
        if len(predictions) == 0:
            return 0.0
            
        # Calculate success rate: sum(successes) / len(all)
        # np.mean on binary array gives us exactly this: sum(1s) / total_count
        return np.mean(predictions)
    
    def calculate_performance_metrics(self, df: pd.DataFrame, category: str) -> Dict[str, Any]:
        """Calculate performance metrics for a subset of data"""
        total_samples = len(df)
        
        if total_samples == 0:
            return {
                "category": category,
                "total_samples": 0,
                "reactants_accuracy_with_stereochemistry": 0.0,
                "reactants_accuracy_without_stereochemistry": 0.0,
                "template_accuracy_with_stereochemistry": 0.0,
                "template_accuracy_without_stereochemistry": 0.0,
                "either_accuracy_with_stereochemistry": 0.0,
                "either_accuracy_without_stereochemistry": 0.0,
                "failed_json_parsing": 0,
                "failed_json_parsing_rate": 0.0,
                "avg_predictions_created": 0.0,
                "avg_reactants_per_prediction": 0.0,
                "avg_templates_created": 0.0,
                "avg_non_templates_created": 0.0,
                "avg_valid_predictions": 0.0,
                "avg_invalid_predictions": 0.0,
                "avg_total_tokens": 0.0,
                "max_tokens": 0
            }
        
        # Calculate metrics for reactants (with stereochemistry)
        y_pred_reactants_stereochemistry = df['match_found_with_stereochemistry'].astype(int).values
        reactants_accuracy_stereochemistry = self.calculate_accuracy(y_pred_reactants_stereochemistry)
        
        # Calculate metrics for reactants (without stereochemistry)
        y_pred_reactants_no_stereochemistry = df['match_found_without_stereochemistry'].astype(int).values
        reactants_accuracy_no_stereochemistry = self.calculate_accuracy(y_pred_reactants_no_stereochemistry)
        
        # Calculate metrics for templates (with stereochemistry)
        y_pred_template_stereochemistry = df['template_match_found_with_stereochemistry'].astype(int).values
        template_accuracy_stereochemistry = self.calculate_accuracy(y_pred_template_stereochemistry)
        
        # Calculate metrics for templates (without stereochemistry)
        y_pred_template_no_stereochemistry = df['template_match_found_without_stereochemistry'].astype(int).values
        template_accuracy_no_stereochemistry = self.calculate_accuracy(y_pred_template_no_stereochemistry)
        
        # Calculate metrics for either reactants or templates (with stereochemistry)
        y_pred_either_stereochemistry = ((df['match_found_with_stereochemistry'] == True) | 
                               (df['template_match_found_with_stereochemistry'] == True)).astype(int).values
        either_accuracy_stereochemistry = self.calculate_accuracy(y_pred_either_stereochemistry)
        
        # Calculate metrics for either reactants or templates (without stereochemistry)
        y_pred_either_no_stereochemistry = ((df['match_found_without_stereochemistry'] == True) | 
                                  (df['template_match_found_without_stereochemistry'] == True)).astype(int).values
        either_accuracy_no_stereochemistry = self.calculate_accuracy(y_pred_either_no_stereochemistry)
        
        # Calculate averages for list columns
        avg_reactants_per_prediction = 0.0
        if not df.empty and 'number_of_reactants_per_prediction' in df.columns:
            # Handle the list column properly
            all_reactants_counts = []
            for _, row in df.iterrows():
                if isinstance(row['number_of_reactants_per_prediction'], list):
                    all_reactants_counts.extend(row['number_of_reactants_per_prediction'])
                elif pd.notna(row['number_of_reactants_per_prediction']):
                    # Convert string or other types to numeric
                    try:
                        # Try to evaluate if it's a string representation of a list
                        if isinstance(row['number_of_reactants_per_prediction'], str):
                            import ast
                            parsed_value = ast.literal_eval(row['number_of_reactants_per_prediction'])
                            if isinstance(parsed_value, list):
                                all_reactants_counts.extend([float(x) for x in parsed_value if pd.notna(x)])
                            else:
                                all_reactants_counts.append(float(parsed_value))
                        else:
                            all_reactants_counts.append(float(row['number_of_reactants_per_prediction']))
                    except (ValueError, SyntaxError, TypeError):
                        # Skip invalid values
                        logger.warning(f"Could not parse number_of_reactants_per_prediction value: {row['number_of_reactants_per_prediction']}")
                        continue
            
            if all_reactants_counts:
                avg_reactants_per_prediction = np.mean(all_reactants_counts)
        
        # Failed JSON parsing statistics
        failed_json_count = df['failed_json_parsing'].sum()
        failed_json_rate = failed_json_count / total_samples if total_samples > 0 else 0.0

        # Ground truth ground_truth_number_of_reaction_examples
        ground_truth_reaction_examples = df['ground_truth_number_of_reaction_examples'].sum()
        ground_truth_reaction_examples_rate = ground_truth_reaction_examples / total_samples if total_samples > 0 else 0.0

        return {
            "category": category,
            "total_samples": total_samples,
            # Accuracy metrics (which equal F1 for top-1 evaluation)
            "reactants_accuracy_with_stereochemistry": reactants_accuracy_stereochemistry,
            "reactants_accuracy_without_stereochemistry": reactants_accuracy_no_stereochemistry,
            "template_accuracy_with_stereochemistry": template_accuracy_stereochemistry,
            "template_accuracy_without_stereochemistry": template_accuracy_no_stereochemistry,
            "either_accuracy_with_stereochemistry": either_accuracy_stereochemistry,
            "either_accuracy_without_stereochemistry": either_accuracy_no_stereochemistry,
            # Validity metrics
            "avg_at_least_one_valid_non_template_reactant_pair_generated": df['at_least_one_valid_non_template_reactant_pair_generated'].mean() if not df.empty else 0.0,
            # Ground truth metrics
            "total_ground_truth_reaction_examples": ground_truth_reaction_examples,
            "avg_ground_truth_reaction_examples_per_sample": ground_truth_reaction_examples_rate,
            # Other statistics
            "failed_json_parsing": failed_json_count,
            "failed_json_parsing_rate": failed_json_rate,
            "avg_predictions_created": df['number_of_reactant_predictions_created'].mean() if not df.empty else 0.0,
            "avg_reactants_per_prediction": avg_reactants_per_prediction,
            "avg_templates_created": df['number_of_templates_created'].mean() if not df.empty else 0.0,
            "avg_non_templates_created": df['number_of_non_templates_created'].mean() if not df.empty else 0.0,
            "avg_valid_predictions": df['number_of_valid_predictions_without_templates'].mean() if not df.empty else 0.0,
            "avg_invalid_predictions": df['number_of_invalid_predictions_out_templates'].mean() if not df.empty else 0.0,
        }
    
    def calculate_statistics(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate comprehensive performance statistics"""
        logger.info(f"Calculating statistics for {len(df)} samples")
        
        results = []
        
        # Overall statistics
        overall_stats = self.calculate_performance_metrics(df, "overall")

        assert overall_stats["total_samples"] == len(df), "The length of the overall statistics must match the length of the input DataFrame"

        results.append(overall_stats)
        
        # Statistics by reaction class (OtherReaction vs !OtherReaction)
        other_reaction_df = df[df['ground_truth_rxn_insight_name'] == 'OtherReaction']
        non_other_reaction_df = df[df['ground_truth_rxn_insight_name'] != 'OtherReaction']
        
        other_stats = self.calculate_performance_metrics(other_reaction_df, "other_reaction")
        results.append(other_stats)
        
        non_other_stats = self.calculate_performance_metrics(non_other_reaction_df, "non_other_reaction")
        results.append(non_other_stats)
        
        # Statistics by individual reaction classes (excluding OtherReaction)
        unique_reactions = df[df['ground_truth_rxn_insight_name'] != 'OtherReaction']['ground_truth_rxn_insight_name'].unique()
        
        for reaction_name in unique_reactions:
            reaction_df = df[df['ground_truth_rxn_insight_name'] == reaction_name]
            reaction_stats = self.calculate_performance_metrics(reaction_df, f"reaction_{reaction_name}")
            results.append(reaction_stats)
        
        # Statistics by reaction insight class
        unique_classes = df['ground_truth_rxn_insight_class'].unique()
        
        for class_name in unique_classes:
            if pd.notna(class_name):
                class_df = df[df['ground_truth_rxn_insight_class'] == class_name]
                class_stats = self.calculate_performance_metrics(class_df, f"class_{class_name}")
                results.append(class_stats)
        
        # Statistics by number of training examples (for non-other reactions only)
        non_other_reaction_df = df[df['ground_truth_rxn_insight_name'] != 'OtherReaction']
        
        # Define thresholds for training examples
        example_thresholds = [5, 4, 3, 2, 1]
        
        for threshold in example_thresholds:
            # Reactions with at least 'threshold' training examples
            threshold_df = non_other_reaction_df[non_other_reaction_df['ground_truth_number_of_reaction_examples'] <= threshold]
            if len(threshold_df) > 0:
                threshold_stats = self.calculate_performance_metrics(threshold_df, f"non_other_max_{threshold}_train_examples")
                results.append(threshold_stats)
            
            # Reactions with exactly 'threshold' training examples
            exact_threshold_df = non_other_reaction_df[non_other_reaction_df['ground_truth_number_of_reaction_examples'] == threshold]
            if len(exact_threshold_df) > 0:
                exact_stats = self.calculate_performance_metrics(exact_threshold_df, f"non_other_exactly_{threshold}_train_examples")
                results.append(exact_stats)
        
        # Statistics by test set size (for non-other reactions only)
        # Group by reaction name and count test set size
        test_set_counts = non_other_reaction_df.groupby('ground_truth_rxn_insight_name').size()
        
        for threshold in example_thresholds:
            # Reactions with at most 'threshold' test examples (5 or less, 4 or less, etc.)
            reaction_names_max = test_set_counts[test_set_counts <= threshold].index
            threshold_test_df = non_other_reaction_df[non_other_reaction_df['ground_truth_rxn_insight_name'].isin(reaction_names_max)]
            if len(threshold_test_df) > 0:
                threshold_test_stats = self.calculate_performance_metrics(threshold_test_df, f"non_other_max_{threshold}_test_examples")
                results.append(threshold_test_stats)
            
            # Reactions with exactly 'threshold' test examples
            reaction_names_exact = test_set_counts[test_set_counts == threshold].index
            exact_test_df = non_other_reaction_df[non_other_reaction_df['ground_truth_rxn_insight_name'].isin(reaction_names_exact)]
            if len(exact_test_df) > 0:
                exact_test_stats = self.calculate_performance_metrics(exact_test_df, f"non_other_exactly_{threshold}_test_examples")
                results.append(exact_test_stats)
        
        # Convert to DataFrame and set category as index
        results_df = pd.DataFrame(results)
        results_df = results_df.set_index('category')
        
        return results_df
    
    def generate_summary_report(self, df: pd.DataFrame, stats_df: pd.DataFrame) -> str:
        """Generate a human-readable summary report"""
        report_lines = []
        report_lines.append("=== CHEMICAL REACTION EVALUATION SUMMARY ===\n")
        
        # Overall statistics
        overall_row = stats_df.loc['overall']
        
        report_lines.append(f"Total Samples: {overall_row['total_samples']}")
        report_lines.append(f"Failed JSON Parsing: {overall_row['failed_json_parsing']} ({overall_row['failed_json_parsing_rate']:.2%})")
        report_lines.append("")
        
        # Performance Summary
        report_lines.append("=== PERFORMANCE SUMMARY ===")
        report_lines.append("Overall Performance:")
        report_lines.append(f"  Reactants Accuracy (with stereo):    {overall_row['reactants_accuracy_with_stereochemistry']:.3f}")
        report_lines.append(f"  Reactants Accuracy (without stereo): {overall_row['reactants_accuracy_without_stereochemistry']:.3f}")
        report_lines.append(f"  Template Accuracy (with stereo):     {overall_row['template_accuracy_with_stereochemistry']:.3f}")
        report_lines.append(f"  Template Accuracy (without stereo):  {overall_row['template_accuracy_without_stereochemistry']:.3f}")
        report_lines.append(f"  Either Accuracy (with stereo):       {overall_row['either_accuracy_with_stereochemistry']:.3f}")
        report_lines.append(f"  Either Accuracy (without stereo):    {overall_row['either_accuracy_without_stereochemistry']:.3f}")
        report_lines.append("")
        
        # Other Reaction vs Non-Other Reaction comparison
        other_row = stats_df.loc['other_reaction']
        non_other_row = stats_df.loc['non_other_reaction']
        
        report_lines.append("=== REACTION TYPE COMPARISON ===")
        report_lines.append(f"OtherReaction samples: {other_row['total_samples']}")
        report_lines.append(f"Non-OtherReaction samples: {non_other_row['total_samples']}")
        report_lines.append("")
        
        report_lines.append("OtherReaction Performance:")
        report_lines.append(f"  Either Accuracy (without stereo): {other_row['either_accuracy_without_stereochemistry']:.3f}")
        report_lines.append(f"  Either Accuracy (with stereo):    {other_row['either_accuracy_with_stereochemistry']:.3f}")
        report_lines.append("")
        
        report_lines.append("Non-OtherReaction Performance:")
        report_lines.append(f"  Either Accuracy (without stereo): {non_other_row['either_accuracy_without_stereochemistry']:.3f}")
        report_lines.append(f"  Either Accuracy (with stereo):    {non_other_row['either_accuracy_with_stereochemistry']:.3f}")
        report_lines.append("")
        
        # Average statistics
        report_lines.append("=== AVERAGE STATISTICS ===")
        report_lines.append(f"Average predictions per sample: {overall_row['avg_predictions_created']:.1f}")
        report_lines.append(f"Average reactants per prediction: {overall_row['avg_reactants_per_prediction']:.1f}")
        report_lines.append(f"Average templates created: {overall_row['avg_templates_created']:.1f}")
        report_lines.append(f"Average non-templates created: {overall_row['avg_non_templates_created']:.1f}")
        report_lines.append(f"Average ground truth reaction examples per sample: {overall_row['avg_ground_truth_reaction_examples_per_sample']:.1f}")
        report_lines.append(f"Total ground truth reaction examples: {overall_row['total_ground_truth_reaction_examples']}")
        report_lines.append(f"avg_at_least_one_valid_non_template_reactant_pair_generated: {overall_row['avg_at_least_one_valid_non_template_reactant_pair_generated']:.3f}")
        report_lines.append("")
        
        # Training examples analysis
        report_lines.append("=== PERFORMANCE BY TRAINING EXAMPLES (Non-Other Reactions) ===")
        example_thresholds = [5, 4, 3, 2, 1]
        
        for threshold in example_thresholds:
            # Max threshold statistics
            max_key = f"non_other_max_{threshold}_train_examples"
            if max_key in stats_df.index:
                max_row = stats_df.loc[max_key]
                report_lines.append(f"Reactions with <= {threshold} training examples ({max_row['total_samples']} samples):")
                report_lines.append(f"  Either Accuracy (without stereo): {max_row['either_accuracy_without_stereochemistry']:.3f}")
                report_lines.append(f"  Either Accuracy (with stereo):    {max_row['either_accuracy_with_stereochemistry']:.3f}")
            
            # Exact threshold statistics
            exact_key = f"non_other_exactly_{threshold}_train_examples"
            if exact_key in stats_df.index:
                exact_row = stats_df.loc[exact_key]
                report_lines.append(f"Reactions with exactly {threshold} training examples ({exact_row['total_samples']} samples):")
                report_lines.append(f"  Either Accuracy (without stereo): {exact_row['either_accuracy_without_stereochemistry']:.3f}")
                report_lines.append(f"  Either Accuracy (with stereo):    {exact_row['either_accuracy_with_stereochemistry']:.3f}")
            
            report_lines.append("")
        
        # Test set examples analysis
        report_lines.append("=== PERFORMANCE BY TEST SET SIZE (Non-Other Reactions) ===")
        
        for threshold in example_thresholds:
            # Max threshold statistics (5 or less, 4 or less, etc.)
            max_test_key = f"non_other_max_{threshold}_test_examples"
            if max_test_key in stats_df.index:
                max_test_row = stats_df.loc[max_test_key]
                report_lines.append(f"Reactions with <= {threshold} test examples ({max_test_row['total_samples']} samples):")
                report_lines.append(f"  Either Accuracy (without stereo): {max_test_row['either_accuracy_without_stereochemistry']:.3f}")
                report_lines.append(f"  Either Accuracy (with stereo):    {max_test_row['either_accuracy_with_stereochemistry']:.3f}")
            
            # Exact threshold statistics
            exact_test_key = f"non_other_exactly_{threshold}_test_examples"
            if exact_test_key in stats_df.index:
                exact_test_row = stats_df.loc[exact_test_key]
                report_lines.append(f"Reactions with exactly {threshold} test examples ({exact_test_row['total_samples']} samples):")
                report_lines.append(f"  Either Accuracy (without stereo): {exact_test_row['either_accuracy_without_stereochemistry']:.3f}")
                report_lines.append(f"  Either Accuracy (with stereo):    {exact_test_row['either_accuracy_with_stereochemistry']:.3f}")
            
            report_lines.append("")

        return "\n".join(report_lines)


def calculate_statistics(input: str, output: str, summary: bool = False, log_level: str = 'INFO') -> pd.DataFrame | None:
    """
    Command-line interface to calculate performance statistics from evaluation results.
    
    Example usage:
    python calculate_statistics.py --input /path/to/evaluation_results.csv --output /path/to/statistics.csv --summary /path/to/summary.txt
    """

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # Load the evaluation results
        logger.info(f"Loading evaluation results from {input}")
        df = pd.read_csv(input)
        
        # Validate required columns
        required_columns = [
            'template_match_found_without_stereochemistry',
            'template_match_found_with_stereochemistry',
            'match_found_without_stereochemistry',
            'match_found_with_stereochemistry',
            'at_least_one_valid_non_template_reactant_pair_generated',
            'ground_truth_rxn_insight_name',
            'ground_truth_number_of_reaction_examples',
            'failed_json_parsing',
        ]
        
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")
        
        # Calculate statistics
        calculator = PerformanceCalculator()
        logger.info("Calculating performance statistics...")
        stats_df = calculator.calculate_statistics(df)
        
        # Save statistics with rows as categories and columns as metrics
        logger.info(f"Saving statistics to {output}")
        stats_df.to_csv(output)
        
        # Generate and save summary report if requested
        if summary:
            logger.info(f"Generating summary report...")
            summary_text = calculator.generate_summary_report(df, stats_df)
            
            with open(summary, 'w') as f:
                f.write(summary_text)
            
            logger.info(f"Summary report saved to {summary}")
            
            # Also print summary to console
            print("\n" + summary_text)
        
        logger.info("Statistics calculation completed successfully!")
        return stats_df
        
    except Exception as e:
        logger.error(f"Error during statistics calculation: {str(e)}")
        return None
    


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Calculate performance statistics for chemical reaction evaluation")
    parser.add_argument("--input", required=True, help="Path to the input CSV file containing evaluation results")
    parser.add_argument("--output", required=True, help="Path to save the statistics CSV")
    parser.add_argument("--summary", help="Path to save the summary report (optional)")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="INFO", 
                        help="Set logging level (default: INFO)")
    
    args = parser.parse_args()
    
    calculate_statistics(args.input, args.output, args.summary, args.log_level)