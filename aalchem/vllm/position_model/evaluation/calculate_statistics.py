import pandas as pd
import argparse

def extract_best_example(group):
    max_jaccard = group['result_jaccard_similarity'].max()

    # All predictions are completely wrong - just take the first one as a negative example    
    if max_jaccard == 0.0:
        best_idx = group.index[0]
        best_example = group.loc[best_idx]
        return best_idx, best_example

    ties = group[group['result_jaccard_similarity'] == max_jaccard]

    # Single best example - no ties
    if len(ties) == 1:
        best_idx = group['result_jaccard_similarity'].idxmax()
        best_example = group.loc[best_idx]
        return best_idx, best_example
    
    # Multiple examples with the same jaccard distance - handle ties
    print(f"Found {len(ties)} ties with Jaccard similarity {max_jaccard}")
    
    # Check if recall and precision are the same (they should be if Jaccard is the same)
    assert ties['result_recall'].nunique() == 1 and ties['result_precision'].nunique() == 1, "Ties have different recall/precision values - this is unexpected. This means that we found an example where two predictions predict different points but share the same jaccard similarity."

    # Prefer correct reactions if available
    correct_reactions = ties[ties['result_is_rxn_name_correct'] == True]
    if len(correct_reactions) == 1:
        print("Found a single correct reaction among ties.")
        # If multiple correct reactions, take the first one
        best_idx = correct_reactions.index[0]
        best_example = group.loc[best_idx]
        return best_idx, best_example
    elif len(correct_reactions) > 1:
        # assert that they all share the same values
        assert correct_reactions['result_jaccard_similarity'].nunique() == 1
        assert correct_reactions['result_precision'].nunique() == 1
        assert correct_reactions['result_recall'].nunique() == 1
        assert correct_reactions['result_is_exact_match'].nunique() == 1
        assert correct_reactions['result_is_partial_match'].nunique() == 1
        assert correct_reactions['result_is_rxn_name_correct'].nunique() == 1


        best_idx = correct_reactions['predicted_priority'].idxmin()
        min_priority = correct_reactions['predicted_priority'].min()
        print(f"Multiple correct reactions found among ties. Taking the highest predicted_priority (LOWEST VALUE = {min_priority}) as they share the same values.")
        best_example = group.loc[best_idx]
        return best_idx, best_example
    else:
        # assert that they all share the same values
        assert ties['result_jaccard_similarity'].nunique() == 1
        assert ties['result_precision'].nunique() == 1
        assert ties['result_recall'].nunique() == 1
        assert ties['result_is_exact_match'].nunique() == 1
        assert ties['result_is_partial_match'].nunique() == 1
        assert ties['result_is_rxn_name_correct'].nunique() == 1
        
        best_idx = ties['predicted_priority'].idxmin()
        min_priority = ties['predicted_priority'].min()
        print(f"No correct reactions found among ties. Taking the highest priority (LOWEST VALUE = {min_priority}) as they share the same values.")

        best_example = group.loc[best_idx]
        return best_idx, best_example

    raise AssertionError("No valid best example found.")


def evaluate_by_template_subset(df):
    """
    Evaluate performance on subsets grouped by template_id.
    For each template group, find the best example based on Jaccard similarity.
    """
    assert 'template_id' in df.columns, "Warning: 'template_id' column not found. Skipping subset evaluation."
    
    # Group by template_id
    grouped = df.groupby('template_id')
    
    best_examples = []
    
    for template_id, group in grouped:
        try:
            best_idx, best_example = extract_best_example(group)
        except AssertionError as e:
            print(f"Warning: {e} at row {len(group)}")
            continue
        
        best_example_values = {
            'template_id': template_id,
            'number_of_predicted_disconnections': len(group),
            'best_example_idx': best_idx,
            'best_jaccard': best_example['result_jaccard_similarity'],
            'best_precision': best_example['result_precision'],
            'best_recall': best_example['result_recall'],
            'best_is_exact_match': best_example['result_is_exact_match'],
            'best_is_partial_match': best_example['result_is_partial_match'],
            'best_rxn_correct': best_example['result_is_rxn_name_correct']
        }
        best_examples.append(best_example_values)
    
    best_examples_df = pd.DataFrame(best_examples)
    
    return best_examples_df

def calculate_aggregated_subset_stats(best_examples_df):
    """Calculate aggregated statistics across all subsets."""
    if best_examples_df is None:
        return None
    
    # Aggregate statistics across subsets
    total_templates = len(best_examples_df)
    total_samples = best_examples_df['number_of_predicted_disconnections'].sum()
    
    # Performance based on best examples from each template
    best_exact_matches = best_examples_df['best_is_exact_match'].sum()
    best_partial_matches = best_examples_df['best_is_partial_match'].sum()
    best_correct_reactions = best_examples_df['best_rxn_correct'].sum()
    
    aggregated_stats = {
        'metric': [
            'total_evaluated_molecules',
            'total_reactions_across_all_molecules',
            'best_examples_exact_matches',
            'best_examples_exact_match_rate',
            'best_examples_partial_matches',
            'best_examples_partial_match_rate',
            'best_examples_correct_reactions',
            'best_examples_reaction_accuracy',
            'average_group_size',
            'average_best_jaccard',
            'average_best_precision',
            'average_best_recall'
        ],
        'value': [
            total_templates,
            total_samples,
            best_exact_matches,
            round((best_exact_matches / total_templates) * 100, 2),
            best_partial_matches,
            round((best_partial_matches / total_templates) * 100, 2),
            best_correct_reactions,
            round((best_correct_reactions / total_templates) * 100, 2),
            round(best_examples_df['number_of_predicted_disconnections'].mean(), 1),
            round(best_examples_df['best_jaccard'].mean(), 3),
            round(best_examples_df['best_precision'].mean(), 3),
            round(best_examples_df['best_recall'].mean(), 3)
        ]
    }
    
    return pd.DataFrame(aggregated_stats)

def calculate_statistics_position(input_csv: str, best_examples: str = None, aggregated_subset_stats: str = None):
    """Main function to calculate evaluation statistics and save them to CSV."""
   
    # Load CSV file
    df = pd.read_csv(input_csv)
    
    # Calculate subset statistics
    best_examples_df = evaluate_by_template_subset(df)
    
    if best_examples_df is not None:
        # Save best examples
        if best_examples:
            best_examples_df.to_csv(best_examples, index=False)
            print(f"Best examples saved to {best_examples}")
        
        # Calculate and save aggregated subset statistics
        aggregated_stats = calculate_aggregated_subset_stats(best_examples_df)
        if aggregated_stats is not None and aggregated_subset_stats:
            aggregated_stats.to_csv(aggregated_subset_stats, index=False)
            print(f"Aggregated subset statistics saved to {aggregated_subset_stats}")
            
            # Print aggregated subset statistics
            print("\nAggregated Subset Statistics:")
            print("=" * 50)
            for _, row in aggregated_stats.iterrows():
                print(f"{row['metric']}: {row['value']}")

    # return aggregated_stats
    return aggregated_stats

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Calculate evaluation statistics")
    parser.add_argument("input_csv", help="Path to input CSV file with evaluation results")
    parser.add_argument("--best_examples", help="Path to save best examples CSV", default=None)
    parser.add_argument("--aggregated_subset_stats", help="Path to save aggregated subset statistics CSV", default=None)
    
    args = parser.parse_args()
 
    calculate_statistics_position(args.input_csv, args.best_examples, args.aggregated_subset_stats)

