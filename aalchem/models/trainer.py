import time
import pprint
import os
import wandb
import google.generativeai as genai
import pandas as pd
from aalchem.config import TrainingConfig, paths
from aalchem.models.gemini import GeminiModel
from aalchem.data.datasets import ReactionDataset
from aalchem.data.preprocessing import dataset_to_gemini


class GeminiTrainer:
    def __init__(self, config: TrainingConfig):

        ## Training dataset
        self.train_set = ReactionDataset(name=config.dataset_name)
        self.finetuning_data = None ## For finetuning using a specific format

        ## Config
        self.config = config

    def init_wandb(self):
        output_path = os.path.join(paths.MODELS, self.config.name)
        wandb.init(
            project=self.config.wandb_project,
            entity=self.config.wandb_entity,
            name=self.config.name,
            config=self.config.to_dict(),
            dir=output_path,
            reinit=True,
        )

    def prepare_finetuning_data(self):
        preprompt = self.config.system_prompt if self.config.system_prompt else ""
        self.finetuning_data = dataset_to_gemini(
            df=self.train_set.df,
            reaction_name_column='rxn_insight_name',
            reaction_class_column='rxn_insight_class',
            preprompt=preprompt,
        )

    def finetune(self, config: TrainingConfig = None) -> None:
        """
        Fine-tune the model on the dataset.
        Everything passed via configs.
        """
        output_path = os.path.join(paths.MODELS, self.config.name)
        os.makedirs(output_path, exist_ok=True)
        if self.config.wandb:
            self.init_wandb()

        if config is not None:
            self.config = config

        # n_checkpoints = self.config.model.epoch_count // self.config.checkpoint_interval
        n_checkpoints = 1 # TODO: Change in the future with APIs that support checkpointing 
        self.config.model.epoch_count = self.config.checkpoint_interval

        if not self.finetuning_data:
            self.prepare_finetuning_data()
        
        print('Finetuning data example:')
        pprint.pprint(self.finetuning_data[0])

        ## Initial eval
        model = GeminiModel(name=self.config.source_model)  ## Default model (untrained)

        try:
            self.config.to_yaml(os.path.join(output_path, "config.yaml"))
            for checkpoint in range(1, n_checkpoints + 1):
                # Checkpoint naming
                epochs_trained = checkpoint * self.config.checkpoint_interval
                if checkpoint != n_checkpoints:
                    checkpoint_name = f"{self.config.name}-checkpoint-{checkpoint}"
                else:
                    checkpoint_name = f"{self.config.name}"  # Final checkpoint

                print(
                    f"\nFinetuning model {self.config.name} | Checkpoint #{checkpoint}/{n_checkpoints} ({epochs_trained} epochs total)\n"
                )
                self.config.epochs_trained = epochs_trained

                print(self.config.to_dict())

                try:
                    training_op = genai.create_tuned_model(
                        id=checkpoint_name,
                        source_model=self.config.source_model,
                        display_name=checkpoint_name,
                        description=self.config.name,
                        training_data=self.finetuning_data,
                        epoch_count=self.config.epoch_count,
                        batch_size=self.config.batch_size,
                        temperature=self.config.temperature,
                        top_p=self.config.model.top_p,
                        top_k=self.config.model.top_k,
                    )
                    ## Wait for training to finish
                    for status in training_op.wait_bar():
                        time.sleep(10)

                except Exception as e:
                    print(f"Error creating tuned model: {e}")
                    continue

                result = training_op.result()
                print(result)
                ## Wandb logging
                snapshot = result.tuning_task.snapshots
                snapshot_df = pd.DataFrame(snapshot)
                snapshot_df.to_csv(os.path.join(output_path, "tuning.csv"), index=False)
                if self.config.wandb:
                    print(snapshot_df)
                    wandb.log({"tuning": snapshot_df})
                    for i, row in snapshot_df.iterrows():
                        wandb.log(
                            {
                                "epoch": row["epoch"]
                                + epochs_trained
                                - self.config.checkpoint_interval
                            }
                        )
                        wandb.log({"loss": row["mean_loss"]})

                ## Evaluate the model
                self.config.model.system_prompt = self.config.system_prompt
                model = GeminiModel(name=checkpoint_name, config=self.config.model)
                model.config.temperature = 0.0
                for test_set in self.test_sets:
                    test_set.evaluate(
                        model=model, 
                        postprocessor=self.train_set.config.postprocessor, 
                        verbose=self.train_set.config.verbose,
                        timeout=self.train_set.config.timeout,
                        cutoff=self.train_set.config.cutoff,
                    )
                    test_set.plot_evals()

                ## Set the source model for the next checkpoint
                self.config.model.source_model = f"tunedModels/{checkpoint_name}"

        except KeyboardInterrupt:
            training_op.cancel()  ## Cancel on google cloud as well
            print("Interrupted. Saving model and exiting.")
            self.config.to_yaml(os.path.join(output_path, "config.yaml"))
            return
        finally:
            wandb.finish()
        
