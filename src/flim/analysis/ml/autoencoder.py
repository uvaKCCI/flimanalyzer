#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Time  : 10/27/20 3:22 PM
# @Author: Jiaxin_Zhang

"""Autoencoder architectures of the autoencoder tools, as PyTorch modules.

Each architecture is a subclass of `AbsAutoencoder`, found by the name it sets
(`get_autoencoder_classes`). A model returns its encoder output (the features) and
its decoder output (the reconstructed input).
"""

import os
import pkgutil
import importlib
import inspect
import logging
import torch
import torch.nn as nn
import numpy as np
from numpy.typing import ArrayLike
from typing import Any, Optional, Self
from sklearn.base import BaseEstimator, TransformerMixin
from abc import abstractmethod

logger = logging.getLogger(__name__)


def get_autoencoder_classes() -> "dict[str, type[AbsAutoencoder]]":
    """Return the autoencoder architectures by name.

    Imports every module of this package first, so that the subclasses defined in
    them are found. Only direct subclasses of `AbsAutoencoder` are included.

    Returns:
        The classes, by the name an instance created with default arguments has
        (`get_name`), e.g. `AE Simulator 1-6`.

    Raises:
        AttributeError: If a subclass cannot be created with default arguments.
    """
    pkdir = os.path.dirname(__file__)
    for module_loader, name, ispkg in pkgutil.iter_modules([pkdir]):
        importlib.import_module("." + name, __package__)
    available_aes = {
        create_instance(cls).get_name(): cls for cls in AbsAutoencoder.__subclasses__()
    }
    return available_aes


def init_autoencoders() -> "list[Optional[AbsAutoencoder]]":
    """Return one instance, created with default arguments, of each architecture.

    Returns:
        The instances; None for an instance that could not be created.
    """
    tools = get_autoencoder_classes()
    aes = [create_instance(tools[aname]) for aname in tools]
    return aes


def create_instance(clazz: str | type, **kwargs: Any) -> Any:
    """Create an instance of a class, given as a class or by its dotted path.

    Errors of the import or of the creation are logged, not raised.

    Args:
        clazz: The class, or its module and name, e.g.
            `flim.analysis.ml.autoencoder.Autoencoder_Two_Ten`.
        **kwargs: The arguments of the class, e.g. `nb_param`.

    Returns:
        The instance; None if the module cannot be imported or the instance cannot
        be created.

    Raises:
        UnboundLocalError: If `clazz` is neither a string nor a class (after an
            error is logged).
    """
    if isinstance(clazz, str):
        modulename, _, classname = clazz.rpartition(".")
    elif inspect.isclass(clazz):
        modulename = clazz.__module__
        classname = clazz.__name__
    else:
        logger.error(f"Error instantiating {clazz} autoencoder.")
    logger.debug(
        f"Autoencoder modulename={modulename}, classname={classname}, {kwargs}"
    )
    try:
        module = importlib.import_module(modulename)
        class_ = getattr(module, classname)
        toolinstance = class_(**kwargs)
    except Exception as err:
        logger.error(f"Error: {err}")
        logger.error(
            f"Error instantiating {modulename}.{classname} autoencoder, {kwargs}"
        )
        toolinstance = None

    return toolinstance


class AbsAutoencoder(nn.Module, BaseEstimator, TransformerMixin):
    """Base class of the autoencoders: a PyTorch module and a scikit-learn transformer.

    The models are trained with PyTorch. As the last step of a scikit-learn pipeline
    they are only applied (`transform`); `fit` does not train them.
    """

    def __init__(self) -> None:
        """Create the module; its name is the module name until a subclass sets it."""
        super(AbsAutoencoder, self).__init__()
        self.name = __name__

    def get_name(self) -> str:
        """Return the name of the architecture, e.g. `AE Simulator 1-6`."""
        return self.name

    def fit(self, X: Any) -> Self:
        """Return the model unchanged; the models are trained with PyTorch.

        Args:
            X: Ignored.

        Returns:
            The model.
        """
        return self

    def __sklearn_is_fitted__(self) -> bool:
        """Return True: scikit-learn treats the model as fitted."""
        # trained with PyTorch before it is put into a scikit-learn pipeline
        return True

    def transform(self, X: ArrayLike) -> tuple[torch.Tensor, torch.Tensor]:
        """Run the values through the model on the model's device, without gradients.

        Args:
            X: The values, shape (rows, `nb_param`); converted to 32-bit floats.

        Returns:
            The encoder output, shape (rows, encoder size), and the decoder output,
            shape (rows, `nb_param`), as tensors on the CPU, on whichever device
            (`cpu`, `cuda` or `mps`) the model runs.
        """
        device = next(self.parameters()).device
        X = torch.as_tensor(np.asarray(X), dtype=torch.float32, device=device)
        with torch.no_grad():
            encoder_out, decoder_out = self(X)
        return encoder_out.cpu(), decoder_out.cpu()

    @abstractmethod
    def get_description(self) -> Optional[str]:
        """Return a description of the architecture; None in the base class."""
        return None


class Autoencoder_One_Six(AbsAutoencoder):  # used for simulation
    """Autoencoder with one hidden layer of 6 units (ReLU), for simulating data."""

    def __init__(self, nb_param: int = 2, hidden_size: int = 6) -> None:
        """Create the layers.

        Args:
            nb_param: The number of input features. Defaults to 2.
            hidden_size: The number of units of the hidden layer (the encoder
                output). Defaults to 6.
        """
        super().__init__()
        self.name = "AE Simulator 1-6"
        self.fc1 = nn.Linear(nb_param, hidden_size)
        self.fc4 = nn.Linear(hidden_size, nb_param)
        self.activation2 = nn.ReLU()

    def fit(self, loaders: Any) -> Self:
        """Return the model unchanged; the models are trained with PyTorch."""
        return self

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Return the encoder output (hidden layer) and the decoder output.

        Args:
            x: The input, shape (rows, `nb_param`).

        Returns:
            The encoder output, shape (rows, `hidden_size`), and the decoder output,
            shape (rows, `nb_param`).
        """
        encoder_out = self.activation2(self.fc1(x))
        decoder_out = self.fc4(encoder_out)
        return encoder_out, decoder_out

    def get_description(self) -> str:
        """Return a description of the architecture for the user."""
        return (
            "This Autoencoder can be used to simulate new data based on an existing"
            " dataset."
        )


class Autoencoder_One_Three(AbsAutoencoder):  # for simulation; no workflow default
    """Autoencoder with one hidden layer of 3 units (ReLU), for simulating data."""

    def __init__(self, nb_param: int = 2, hidden_size: int = 3) -> None:
        """Create the layers.

        Args:
            nb_param: The number of input features. Defaults to 2.
            hidden_size: The number of units of the hidden layer (the encoder
                output). Defaults to 3.
        """
        super().__init__()
        self.name = "AE Simulator 1-3"
        self.fc1 = nn.Linear(nb_param, hidden_size)
        self.fc4 = nn.Linear(hidden_size, nb_param)
        self.activation2 = nn.ReLU()

    def fit(self, loaders: Any) -> Self:
        """Return the model unchanged; the models are trained with PyTorch."""
        return self

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Return the encoder output (hidden layer) and the decoder output.

        Args:
            x: The input, shape (rows, `nb_param`).

        Returns:
            The encoder output, shape (rows, `hidden_size`), and the decoder output,
            shape (rows, `nb_param`).
        """
        encoder_out = self.activation2(self.fc1(x))
        decoder_out = self.fc4(encoder_out)
        return encoder_out, decoder_out

    def get_description(self) -> str:
        """Return a description of the architecture for the user."""
        return (
            "This Autoencoder can be used to simulate new data based on an existing"
            " dataset."
        )


class Autoencoder_Two_Ten(AbsAutoencoder):
    """Autoencoder with hidden layers of 10, 1 and 10 units, to reduce features."""

    def __init__(
        self, nb_param: int = 2, hidden_size_1: int = 10, hidden_size_2: int = 1
    ) -> None:
        """Create the layers.

        Args:
            nb_param: The number of input features. Defaults to 2.
            hidden_size_1: The number of units of the first and the last hidden
                layer. Defaults to 10.
            hidden_size_2: The number of units of the middle layer (the encoder
                output). Defaults to 1.
        """
        super().__init__()
        self.name = "AE Dimensionality Reduction 2-10"
        self.fc1 = nn.Linear(nb_param, hidden_size_1)
        self.fc2 = nn.Linear(hidden_size_1, hidden_size_2)
        self.fc3 = nn.Linear(hidden_size_2, hidden_size_1)
        self.fc4 = nn.Linear(hidden_size_1, nb_param)
        self.activation2 = nn.ReLU()

    def fit(self, loaders: Any) -> Self:
        """Return the model unchanged; the models are trained with PyTorch."""
        return self

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Return the encoder output (middle layer) and the decoder output.

        Args:
            x: The input, shape (rows, `nb_param`).

        Returns:
            The encoder output, shape (rows, `hidden_size_2`), and the decoder
            output, shape (rows, `nb_param`).
        """
        x_out = self.activation2(self.fc1(x))
        encoder_out = self.activation2(self.fc2(x_out))
        y_out = self.activation2(self.fc3(encoder_out))
        decoder_out = self.fc4(y_out)
        return encoder_out, decoder_out

    def get_description(self) -> str:
        """Return a description of the architecture for the user."""
        return (
            "This Autoencoder is used for dimensionality reduction of the feature space"
            " of an existing dataset."
        )


class Autoencoder_Two_Five(AbsAutoencoder):  # no workflow default
    """Autoencoder with hidden layers of 5, 1 and 5 units, to reduce features."""

    def __init__(
        self, nb_param: int = 2, hidden_size_1: int = 5, hidden_size_2: int = 1
    ) -> None:
        """Create the layers.

        Args:
            nb_param: The number of input features. Defaults to 2.
            hidden_size_1: The number of units of the first and the last hidden
                layer. Defaults to 5.
            hidden_size_2: The number of units of the middle layer (the encoder
                output). Defaults to 1.
        """
        super().__init__()
        self.name = "AE Dimensionality Reduction 2-5"
        self.fc1 = nn.Linear(nb_param, hidden_size_1)
        self.fc2 = nn.Linear(hidden_size_1, hidden_size_2)
        self.fc3 = nn.Linear(hidden_size_2, hidden_size_1)
        self.fc4 = nn.Linear(hidden_size_1, nb_param)
        self.activation2 = nn.ReLU()

    def fit(self, loaders: Any) -> Self:
        """Return the model unchanged; the models are trained with PyTorch."""
        return self

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Return the encoder output (middle layer) and the decoder output.

        Args:
            x: The input, shape (rows, `nb_param`).

        Returns:
            The encoder output, shape (rows, `hidden_size_2`), and the decoder
            output, shape (rows, `nb_param`).
        """
        x_out = self.activation2(self.fc1(x))
        encoder_out = self.activation2(self.fc2(x_out))
        y_out = self.activation2(self.fc3(encoder_out))
        decoder_out = self.fc4(y_out)
        return encoder_out, decoder_out

    def get_description(self) -> str:
        """Return a description of the architecture for the user."""
        return (
            "This Autoencoder is used for dimensionality reduction of the feature space"
            " of an existing dataset."
        )
