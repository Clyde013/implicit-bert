from transformers import DataCollatorForLanguageModeling, PreTrainedTokenizerBase, RobertaTokenizer
from torch.utils.data import DataLoader
import datasets
from datasets import DownloadConfig
from pytorch_lightning import LightningDataModule

_HOST_URL = "https://the-eye.eu"
_TRAIN_SOURCE_FILES = {"train": [f"{_HOST_URL}/public/AI/pile/train/{i:0>2}.jsonl.zst" for i in range(30)]}
_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) " \
              "Chrome/86.0.4240.75 Safari/537.36"


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
            config = DownloadConfig(resume_download=True,
                                    user_agent=_USER_AGENT,
                                    max_retries=10)
            self.dataset = datasets.load_dataset("json", data_files=_TRAIN_SOURCE_FILES, download_config=config)
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

    # i actually give up. there are too many https connection, ssl timeouts and connection reset by peer errors
    while True:
        try:
            pile_datamodule.setup()
            break
        except:
            continue

    pile_dataset = pile_datamodule.dataset

    print(list(pile_dataset.take(3)))
