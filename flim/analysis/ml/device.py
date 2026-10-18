"""Selection of the PyTorch device for the autoencoder tools."""

import logging

import torch

# choices offered in the configuration dialogs; "auto" picks the best available
DEVICES = ["auto", "cpu", "cuda", "mps"]
DEFAULT_DEVICE = "auto"


def is_available(name):
    """Whether the device ``name`` (cpu, cuda or mps) can be used on this machine."""
    if name == "cpu":
        return True
    if name == "cuda":
        return torch.cuda.is_available()
    if name == "mps":
        mps = getattr(torch.backends, "mps", None)
        return bool(mps is not None and mps.is_available())
    return False


def resolve_device(name=DEFAULT_DEVICE):
    """Returns the torch.device to use for the device choice ``name``.

    "auto" picks a CUDA GPU, then the Apple GPU (mps), then the CPU. A device
    that is not available, or an unknown name, falls back to the CPU.
    """
    name = str(name or DEFAULT_DEVICE).lower()
    if name == "auto":
        name = next((n for n in ("cuda", "mps") if is_available(n)), "cpu")
        logging.info(f"Automatic device selection: using {name}")
    elif name not in DEVICES:
        logging.warning(f"Unknown device '{name}', using cpu")
        name = "cpu"
    elif not is_available(name):
        logging.warning(f"Device '{name}' selected, but not available on this machine, using cpu")
        name = "cpu"
    return torch.device(name)
