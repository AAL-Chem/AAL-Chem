def split_csv_into_parts(input_file, output_dir, part_size=10):
    """
    Split a CSV file into smaller parts with specified number of rows each.
    
    Args:
        input_file (str): Path to the input CSV file
        output_dir (str): Directory to save the split files
        part_size (int): Number of rows per part (default: 10)
    
    Returns:
        list: List of created file paths
    """
    import pandas as pd
    import os
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Read the CSV file
    df = pd.read_csv(input_file)
    
    # Get the base filename without extension
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    
    created_files = []
    
    # Split the dataframe into chunks
    for i in range(0, len(df), part_size):
        chunk = df.iloc[i:i + part_size]
        part_number = i // part_size + 1
        
        # Create output filename
        output_file = os.path.join(output_dir, f"{base_name}_part_{part_number}.csv")
        
        # Save the chunk d
        chunk.to_csv(output_file, index=False)
        created_files.append(output_file)
        
        print(f"Created {output_file} with {len(chunk)} rows")
    
    print(f"Split complete! Created {len(created_files)} files with {part_size} rows each (last file may have fewer)")
    return created_files

# Usage example for your specific file directory
if __name__ == "__main__":
    input_file = "/home/user02/workspace/paper/retro_llm/RetroLLM/data/uspto_50k/uspto50k_train.csv"
    output_dir = "/home/user02/workspace/paper/retro_llm/runs/splits/uspto_50k/train_parts/"

    print(f"Splitting {input_file} into {output_dir} rows each...")
    split_files = split_csv_into_parts(input_file, output_dir, part_size=100)
    print(split_files)
