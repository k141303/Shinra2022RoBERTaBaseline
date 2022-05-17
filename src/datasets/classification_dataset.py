import os
import glob
import random

from multiprocessing import Pool
import multiprocessing as multi

import tqdm

import torch
from torch.utils.data import Dataset

from transformers import AutoTokenizer

from utils.data_utils import DataUtils
from utils.array_utils import padding
from utils.scoring_utils import classification_micro_f1


class ClassificationDataset(Dataset):
    def __init__(self, data, ene_id_list, model_name, num_tokens=512):
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.num_tokens = num_tokens
        self.data = data
        self.ene_id_list = ene_id_list
        self.num_labels = len(ene_id_list)

    def __len__(self):
        return len(self.data)

    def __getitem__(self, i):
        d = self.data[i]

        input_ids = [self.tokenizer.cls_token_id] + d["token_ids"] + [self.tokenizer.sep_token_id]
        attention_mask = [1] * len(input_ids)

        input_ids = padding(input_ids, self.tokenizer.pad_token_id, self.num_tokens)
        attention_mask = padding(attention_mask, 0, self.num_tokens)

        item = {
            "pageid": d["pageid"],
            "input_ids": torch.LongTensor(input_ids),
            "attention_mask": torch.LongTensor(attention_mask),
        }

        if d.get("ENEs") is not None:
            ene_indexes = [self.ene_id_list.index(ene_id) for ene_id in d["ENEs"]]
            labels = [i in ene_indexes for i in range(self.num_labels)]
            item["labels"] = torch.LongTensor(labels)

        return item

    def evaluation(self, outputs, labels, prefix="train"):
        return classification_micro_f1(outputs, labels, prefix=prefix)

    @classmethod
    def load_dataset(cls, file_dir, model_name, num_tokens=512, dev_size=1000, debug_mode=False):
        ene_id_list = DataUtils.Json.load(os.path.join(file_dir, "ene_id_list.json"))

        file_paths = glob.glob(os.path.join(file_dir, "data/*.json"))
        file_paths.sort()

        if debug_mode:
            file_paths = file_paths[:5]

        data = []
        with Pool(multi.cpu_count()) as p, tqdm.tqdm(desc="Loading", total=len(file_paths)) as t:
            for _data in p.imap(DataUtils.JsonL.load, file_paths):
                data += _data
                t.update()

        all_indexes = list(range(len(data)))
        random.shuffle(all_indexes)
        train_indexes = sorted(all_indexes[dev_size:])
        dev_indexes = sorted(all_indexes[:dev_size])

        train_data = [data[i] for i in train_indexes]
        dev_data = [data[i] for i in dev_indexes]

        train_dataset = cls(train_data, ene_id_list, model_name, num_tokens=num_tokens)
        dev_dataset = cls(dev_data, ene_id_list, model_name, num_tokens=num_tokens)

        return train_dataset, dev_dataset

    @classmethod
    def load_pred_dataset(cls, file_dir, model_name, ene_id_list, num_tokens=512, debug_mode=False):
        file_paths = glob.glob(os.path.join(file_dir, "data/*.json"))
        file_paths.sort()

        if debug_mode:
            file_paths = file_paths[:5]

        data = []
        with Pool(multi.cpu_count()) as p, tqdm.tqdm(desc="Loading", total=len(file_paths)) as t:
            for _data in p.imap(DataUtils.JsonL.load, file_paths):
                data += _data
                t.update()

        return cls(data, ene_id_list, model_name, num_tokens=num_tokens)
