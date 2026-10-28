import numpy as np
import pandas as pd

import flim.tools.ml as ml
from flim.plugin import plugin, AbstractPlugin

COVAR_OPTIONS = ["spherical", "tied", "diag", "full"]
METHOD_OPTIONS = ["EM", "Variational Bayesian"]


def full_matrix(values, covar_type, n_components, n_features):
    if (
        covar_type == "full"
    ):  # each component has it's own unconstrained covariance matrix
        return values
    elif covar_type == "tied":  # all components share single common covariance matrrix
        return np.array([values for _ in range(n_components)])
    elif covar_type == "diag":  # for each component the covar is axis-aligned
        return np.array([np.diag(values[i]) for i in range(n_components)])
    elif (
        covar_type == "spherical"
    ):  # each component is a spherical Gaussian with single variance
        return np.array(
            [np.diag(np.full(n_features, values[i])) for i in range(n_components)]
        )
    else:
        return None


@plugin(plugintype="Analysis")
class GaussianMixedModel(AbstractPlugin):
    def __init__(self, name="Gaussian Mixed Model", **kwargs):
        super().__init__(name=name, **kwargs)

    def get_required_categories(self):
        return []

    def get_required_features(self):
        return ["any"]

    def get_default_parameters(self):
        params = super().get_default_parameters()
        params.update(
            {
                "method": "EM",
                "n_components": 2,
                "covar_type": "full",
            }
        )
        return params

    def output_definition(self):
        return {"Table: Gaussian Mixed Model BIC": pd.DataFrame}

    def execute(self):
        return self.run_tool(ml.GaussianMixedModel, list(self.input.values())[0])
