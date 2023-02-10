from transformers import DataCollatorForLanguageModeling, PreTrainedTokenizerBase, RobertaTokenizer
from torch.utils.data import DataLoader
import datasets
from pytorch_lightning import LightningDataModule

_HOST_URL = "https://the-eye.eu"
_TRAIN_SOURCE_FILES = [(i, f"{_HOST_URL}/public/AI/pile/train/{i:0>2}.jsonl.zst") for i in range(30)]


class PileDataModule(LightningDataModule):
    """
    Data Module specifically for the_pile dataset. Works with any tokenizer (even custom ones).
    If you get SSL certificate errors with these, go to https://mystic.the-eye.eu/ and download the certificate,
    and install it into trusted root certification authorities.
    """

    def __init__(
            self,
            tokenizer: PreTrainedTokenizerBase,
            stream: bool = False,
            buffer_size: int = 10000,
            max_seq_length: int = 128,
            train_batch_size: int = 32,
            eval_batch_size: int = 32,
            **kwargs,
    ):
        super().__init__()
        self.tokenizer = tokenizer
        self.stream = stream
        self.buffer_size = buffer_size
        self.max_seq_length = max_seq_length
        self.train_batch_size = train_batch_size
        self.eval_batch_size = eval_batch_size

        self.dataset = None

    def setup(self, stage: str = None):
        if self.stream:
            self.dataset = datasets.load_dataset("the_pile", streaming=True, split="train", subsets=["all"])
            self.dataset = self.dataset.shuffle(seed=69, buffer_size=self.buffer_size)
        else:
            # the problem is that if the internet cuts out for a while during download, it cancels the whole 815GB
            # dataset download, and you have to start from scratch. Downloading each as individual datasets allows the
            # caching to be complete and registered by huggingface datasets, so when it does crash, huggingface will
            # load the cached splits instead.
            individual_pilesplits = []
            for i, url in _TRAIN_SOURCE_FILES:
                individual_pilesplits.append(datasets.load_dataset(f"pile_split_{i}", data_files={"train": url}))

            self.dataset = datasets.concatenate_datasets(individual_pilesplits)
            self.dataset = self.dataset.shuffle(seed=69)

        # tokenize the dataset. scuffed af to manually remove denote the remove_columns but it works
        self.dataset = self.dataset.map(self.encode, batched=True, remove_columns=["text", "meta"]).with_format("torch")

    # since the dataset is a stream and masking is dynamic we can't exactly split it. train/val/test splits are
    # basically the same.
    def train_dataloader(self):
        return DataLoader(self.dataset, batch_size=self.train_batch_size,
                          collate_fn=DataCollatorForLanguageModeling(self.tokenizer))

    def val_dataloader(self):
        return DataLoader(self.dataset, batch_size=self.eval_batch_size,
                          collate_fn=DataCollatorForLanguageModeling(self.tokenizer))

    def test_dataloader(self):
        return DataLoader(self.dataset, batch_size=self.eval_batch_size,
                          collate_fn=DataCollatorForLanguageModeling(self.tokenizer))

    def encode(self, example_batch):
        # tokenize the text
        features = self.tokenizer(example_batch["text"], max_length=self.max_seq_length, padding="max_length",
                                  truncation=True, return_tensors="pt")
        return features


if __name__ == "__main__":
    tokenizer = RobertaTokenizer.from_pretrained("roberta-base")

    pile_datamodule = PileDataModule(tokenizer)
    pile_datamodule.setup()
    pile_dataset = pile_datamodule.dataset

    print(list(pile_dataset.take(3)))
