#!/usr/bin/env python3
"""
Join split CSV files back into a single file.

This script takes a directory containing split CSV files (created by split.py)
and joins them back together in the correct order.
"""

import pandas as pd
import os
import re
import argparse
from pathlib import Path


def join_csv_parts(input_dir, output_file, pattern=None, verify_continuity=True):
    """
    Join split CSV files back into a single file.
    
    Args:
        input_dir (str): Directory containing the split CSV files
        output_file (str): Path for the output joined CSV file
        pattern (str): Optional regex pattern to match files (default: looks for _part_ pattern)
        verify_continuity (bool): Whether to verify that part numbers are continuous
    
    Returns:
        dict: Information about the join operation
    """
    
    # Default pattern to match files like "filename_part_001.csv"
    if pattern is None:
        pattern = r'(.+)_part_(\d+)\.csv$'
    
    # Find all matching files
    input_path = Path(input_dir)
    if not input_path.exists():
        raise FileNotFoundError(f"Input directory does not exist: {input_dir}")
    
    files_info = []
    base_names = set()
    
    for file_path in input_path.glob("*.csv"):
        match = re.match(pattern, file_path.name)
        if match:
            base_name = match.group(1)
            part_number = int(match.group(2))
            files_info.append({
                'path': file_path,
                'base_name': base_name,
                'part_number': part_number,
                'filename': file_path.name
            })
            base_names.add(base_name)
    
    if not files_info:
        raise ValueError(f"No files matching pattern found in {input_dir}")
    
    # Check if we have multiple base names (different file sets)
    if len(base_names) > 1:
        print(f"Warning: Found multiple file sets: {base_names}")
        print("Will process all files together. Use a more specific pattern if needed.")
    
    # Sort files by part number
    files_info.sort(key=lambda x: x['part_number'])
    
    # Verify continuity if requested
    if verify_continuity:
        part_numbers = [f['part_number'] for f in files_info]
        expected_numbers = list(range(1, len(part_numbers) + 1))
        
        if part_numbers != expected_numbers:
            missing = set(expected_numbers) - set(part_numbers)
            extra = set(part_numbers) - set(expected_numbers)
            
            error_msg = "Part number sequence is not continuous:\n"
            if missing:
                error_msg += f"  Missing parts: {sorted(missing)}\n"
            if extra:
                error_msg += f"  Extra parts: {sorted(extra)}\n"
            error_msg += f"  Found parts: {part_numbers}\n"
            error_msg += f"  Expected parts: {expected_numbers}"
            
            raise ValueError(error_msg)
    
    print(f"Found {len(files_info)} part files to join")
    print(f"Part numbers: {[f['part_number'] for f in files_info]}")
    
    # Read and concatenate all files
    dataframes = []
    total_rows = 0
    
    for file_info in files_info:
        print(f"Reading {file_info['filename']}...")
        df = pd.read_csv(file_info['path'])
        dataframes.append(df)
        total_rows += len(df)
        print(f"  - {len(df)} rows")
    
    # Concatenate all dataframes
    print("Joining all parts...")
    combined_df = pd.concat(dataframes, ignore_index=True)
    
    # Create output directory if it doesn't exist
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Save the combined dataframe
    print(f"Saving joined file to {output_file}...")
    combined_df.to_csv(output_file, index=False)
    
    # Return summary information
    result = {
        'input_dir': input_dir,
        'output_file': output_file,
        'num_parts': len(files_info),
        'total_rows': total_rows,
        'output_rows': len(combined_df),
        'part_files': [f['filename'] for f in files_info],
        'base_names': list(base_names)
    }
    
    print(f"Join complete!")
    print(f"  - Combined {result['num_parts']} part files")
    print(f"  - Total rows: {result['total_rows']}")
    print(f"  - Output file: {output_file}")
    
    # Verify row count matches
    if result['total_rows'] != result['output_rows']:
        print(f"Warning: Row count mismatch! Input: {result['total_rows']}, Output: {result['output_rows']}")
    
    return result


def main():
    # Dictionary of input directories and their corresponding output files
    path_combinations = {
        "uspto_train": {
            "enabled": True,
            "input_dir": "/home/user02/workspace/paper/retro_llm/runs/results/uspto_50k/split/train_parts/",
            "output_file": "/home/user02/workspace/paper/retro_llm/runs/results/uspto_50k/full/uspto50_atom_bond_changes_splitted_product_reagents_reactants/uspto50k_train_atom_and_bond_changes_final.csv"
        },
        "uspto_val": {
            "enabled": True,
            "input_dir": "/home/user02/workspace/paper/retro_llm/runs/results/uspto_50k/split/val_parts/",
            "output_file": "/home/user02/workspace/paper/retro_llm/runs/results/uspto_50k/full/uspto50_atom_bond_changes_splitted_product_reagents_reactants/uspto50k_validation_atom_and_bond_changes_final.csv"
        },
        "uspto_test": {
            "enabled": True,
            "input_dir": "/home/user02/workspace/paper/retro_llm/runs/results/uspto_50k/split/test_parts/",
            "output_file": "/home/user02/workspace/paper/retro_llm/runs/results/uspto_50k/full/uspto50_atom_bond_changes_splitted_product_reagents_reactants/uspto50k_test_atom_and_bond_changes_final.csv"
        },
        "paroutes": {
            "enabled": False,
            "input_dir": "/home/user02/workspace/paper/retro_llm/runs/results/paroutes/split/",
            "output_file": "/home/user02/workspace/paper/retro_llm/runs/results/paroutes/full/paroutes_reactions_with_models_matter_splits_annotated.csv"
        }
    }

    pattern = None  # Default pattern (matches files like 'name_part_001.csv')
    verify_continuity = True  # Set to False to skip verification of continuous part numbers
    
    for name, paths in path_combinations.items():
        if not paths.get("enabled", False):
            print(f"\n--- Skipping: {name} (disabled) ---")
            continue
            
        print(f"\n--- Processing: {name} ---")
        input_dir = paths["input_dir"]
        output_file = paths["output_file"]
        
        try:
            result = join_csv_parts(
                input_dir=input_dir,
                output_file=output_file,
                pattern=pattern,
                verify_continuity=verify_continuity
            )
            
            print(f"\nJoin operation for '{name}' completed successfully!")
            print(f"Total files processed: {result['num_parts']}")
            print(f"Total rows joined: {result['total_rows']}")
            
            # Additional verification
            if result['total_rows'] == result['output_rows']:
                print("All rows successfully joined!")
            else:
                print(f"Warning: Row count mismatch! Input: {result['total_rows']}, Output: {result['output_rows']}")
                
        except Exception as e:
            print(f"Error processing '{name}': {e}")
            # Continue to the next item in the dictionary
    
    return 0


if __name__ == "__main__":
    exit(main())
