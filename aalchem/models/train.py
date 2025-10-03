import argparse
import os

from aalchem.models.trainer import GeminiTrainer
from aalchem.config import TrainingConfig


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Train a model")

    parser.add_argument('--name', '-n', type=str, default=None, help="Name of the experiment")
    parser.add_argument('--config', '-c', type=str, default=None, help="Path to .yml config file")
    parser.add_argument('--dataset', '-d', type=str, default=None, help="Name of the dataset to use")
    args = parser.parse_args()

    if args.config and os.path.isfile(args.config):
        print(f"Loading config from {args.config}")
        config = TrainingConfig().from_yaml(args.config)
    else:
        config = TrainingConfig()

    if args.name:
        config.name = args.name

    if args.dataset:
        config.dataset_name = args.dataset

    runner = GeminiTrainer(config)
    runner.finetune()