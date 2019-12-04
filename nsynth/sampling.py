from typing import Tuple

import librosa
import torch
from torch import nn
from tqdm import trange

from .functional import encode_μ_law
from .modules import AutoEncoder


def load_model(fp: str, device: str, model: nn.Module, train: bool = False) \
        -> nn.Module:
    """

    :param fp:
    :param device:
    :param model:
    :param train:
    :return:
    """
    save_point = torch.load(fp, map_location=torch.device(device))
    model.load_state_dict(save_point)

    if not train:
        return model

    raise NotImplementedError


def load_audio(fp: str) -> torch.Tensor:
    """

    :param fp:
    :return:
    """
    raw, sr = librosa.load(fp, mono=True, sr=None)
    assert sr == 16000
    raw = torch.tensor(raw[None, ...], dtype=torch.float32)
    x = encode_μ_law(raw) / 128
    return x


def generate(model: AutoEncoder, x: torch.Tensor) \
        -> Tuple[torch.Tensor, torch.Tensor]:
    """

    :param model:
    :param x:
    :return:
    """
    embedding = model.encoder(x)

    # Build and upsample all the conditionals from the embedding:
    l_upsample = nn.Upsample(scale_factor=model.decoder.scale_factor,
                             mode='nearest')
    l_conds = [l_upsample(l_cond(embedding))
               for l_cond in model.decoder.conds]
    l_conds.append(l_upsample(model.decoder.final_cond(embedding)))

    d_size = model.decoder.receptive_field
    generation = x[0][:d_size]
    rem_length = x.size(-1) - d_size

    for _ in trange(rem_length):
        window = generation[-d_size:].view(1, 1, d_size)
        g_size = generation.numel() + 1
        conditionals = [l_conds[i][:, :, g_size - d_size:g_size]
                        for i in range(len(l_conds))]
        val = model(window, conditionals)[:, :, -1].squeeze().argmax().float()
        val = (val - 128.) / 128.
        generation = torch.cat((generation, val), 0)
    return generation, embedding