import pytorch_lightning as pl
from TrainDatasets import oscar

from transformers import DataCollatorForLanguageModeling
from DEQBert.tokenization_deqbert import DEQBertTokenizer
from DEQBert.configuration_deqbert import DEQBertConfig
from transformers import Trainer, TrainingArguments
from DEQBert.modeling_deqbert import DEQBertForMaskedLM

import wandb
import torch
from torch.utils.data import IterableDataset

# To specify the GPU to use you have to set the CUDA_VISIBLE_DEVICES="0" environment variable
wandb.init(project="DEQBert",
           name="test-run")

config = DEQBertConfig.from_pretrained("DEQBert/model_card/config.json")
config.is_decoder = False
tokenizer = DEQBertTokenizer.from_pretrained("roberta-base")

model = DEQBertForMaskedLM(config=config)

oscar_datamodule = oscar.OSCARDataModule(tokenizer)
oscar_datamodule.setup()
oscar_dataset = oscar_datamodule.dataset

# The standard for doing comparing rained model performance is based
# upon batch_size and total steps, not epochs.
batch_size = 128
total_steps = oscar_dataset.dataset_size // batch_size

data_collator = DataCollatorForLanguageModeling(
    tokenizer=tokenizer, mlm=True, mlm_probability=0.15
)

training_args = TrainingArguments(
    output_dir="./models",
    overwrite_output_dir=True,
    max_steps=total_steps,
    per_device_train_batch_size=128,
    save_steps=100_000,
    save_total_limit=2,
    prediction_loss_only=True,
    logging_steps=100,
    report_to="wandb"
)


trainer = Trainer(
    model=model,
    args=training_args,
    data_collator=data_collator,
    train_dataset=oscar_dataset,
)

trainer.train()
