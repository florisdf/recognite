from typing import Callable, Optional, Tuple

import torch
from torch.utils.data import DataLoader
from torch import nn
from tqdm import tqdm


@torch.no_grad()
def get_score_matrix(
    model: nn.Module,
    device: torch.device,
    dl_gal: DataLoader,
    dl_quer: DataLoader,
    agg_gal_fn: Optional[Callable] = None,
    get_embeddings_fn: Optional[Callable] = None
) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Computes the score matrix for a given model, queries and gallery.

    The rows in the score matrix correspond to the queries, the columns
    correspond to the gallery.

    We first iterate over the gallery batches to compute the gallery
    embeddings and compose a gallery. Then we compute the embedding of each
    query image. Finally, we compute the score matrix as the dot product
    between each pair of gallery and query embeddings.

    The model should return a batch of embeddings when calling it with a batch
    of (transformed) images. You can also pass in a custom function
    `get_embeddings_fn(model, imgs)` that takes the model and the batch of
    images as input and returns the embeddings.

    Optionally, the embeddings of the gallery can be aggregated (e.g. averaged
    per class) with a custom `agg_gal_fn(gal_embeddings, gal_labels)` which
    takes the gallery embeddings and labels and returns their aggregated
    versions.

    Args:
        model: The model used for embedding extraction.
        device: The device on which to perform the computations.
        dl_gal: The data loader for the gallery data. It should yield a tuple
            `(imgs, labels)` containing the batch of images and labels when
            iterating over it.
        dl_quer: The data loader for the query data. It should yield a tuple
            `(imgs, labels)` containing the batch of images and labels when
            iterating over it.
        agg_gal_fn: A function that aggregates the gallery embeddings and
            labels. It should take two arguments: the gallery embeddings and
            the gallery labels.
        get_embeddings_fn: A custom function to use for embedding extraction.
            It should take two arguments: the model and the image batch.

    Returns:
        A tuple with three elements: the score matrix, the labels of the
        queries (rows) and the labels of the gallery items (columns).
    """
    assert not model.training
    model = model.to(device)

    gal_embeddings = []
    gal_labels = []
    for imgs, labels in tqdm(dl_gal, leave=False):
        imgs = imgs.to(device)
        labels = labels.to(device)
        if get_embeddings_fn is None:
            out = model(imgs)
        else:
            out = get_embeddings_fn(model, imgs)
        assert len(labels) == len(out)
        gal_embeddings.append(out)
        gal_labels.append(labels)
    gal_embeddings = torch.cat(gal_embeddings)
    gal_labels = torch.cat(gal_labels)

    if agg_gal_fn is not None:
        gal_embeddings, gal_labels = agg_gal_fn(gal_embeddings, gal_labels)

    scores = []
    quer_labels = []
    for imgs, labels in tqdm(dl_quer, leave=False):
        imgs = imgs.to(device)
        labels = labels.to(device)
        if get_embeddings_fn is None:
            q_embs = model(imgs)
        else:
            q_embs = get_embeddings_fn(model, imgs)
        scores.append(torch.matmul(q_embs, gal_embeddings.T))
        quer_labels.append(labels)
    scores = torch.cat(scores)
    quer_labels = torch.cat(quer_labels)

    return scores, quer_labels, gal_labels
