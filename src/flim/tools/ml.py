"""Machine learning tools (scikit-learn) and rule-based categorization."""

import logging
from collections.abc import Sequence
from typing import Any, Union

import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from threadpoolctl import threadpool_limits

from flim.configs.analysis import (
    CategorizerConfig,
    GMMConfig,
    KMeansConfig,
    PCAConfig,
    RandomForestConfig,
)
from flim.core.config import Issue
from flim.core.registry import register_tool
from flim.core.tool import Tool, pyplot_lock
from flim.core.types import OutputSpec, TableType
from flim.core.columns import free_names
from flim.tools.common import categories_first, category_columns, selected_features

logger = logging.getLogger(__name__)


def complete_rows(data: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    """Return the rows without missing values in `features`, renumbered from 0.

    Args:
        data: The table.
        features: The feature columns.

    Returns:
        The category columns and `features` of these rows.
    """
    rows = data[features].dropna(how="any", axis=0).index
    return data.loc[rows, category_columns(data) + features].reset_index(drop=True)


def standardized(values: np.ndarray) -> np.ndarray:
    """Return the values scaled to mean 0 and standard deviation 1 per column.

    The scaling is scikit-learn's `StandardScaler`, fitted on all rows.

    Args:
        values: The values, shape (rows, columns).

    Returns:
        The scaled values, of the same shape.
    """
    from sklearn.preprocessing import StandardScaler

    return StandardScaler().fit_transform(values)


def prepared(
    values: Union[pd.DataFrame, np.ndarray], standardize: bool
) -> np.ndarray:
    """Return a tool's input for fitting, as floats, standardized if `standardize`.

    Args:
        values: The features, e.g. `data[features]`, shape (rows, features).
        standardize: The tool's `standardize_input`; True scales each feature to
            mean 0 and standard deviation 1 (see `standardized`).

    Returns:
        The values as a float array of the same shape.
    """
    values = np.asarray(values, dtype=float)
    return standardized(values) if standardize else values


def bar_chart(table: pd.DataFrame, index: str) -> Figure:
    """Return a bar chart of the table's values, with a bar group per row.

    The figure is not registered with pyplot.

    Args:
        table: The table.
        index: The column whose values label the bar groups.

    Returns:
        The figure.
    """
    figure = Figure()
    ax = figure.add_subplot()
    with pyplot_lock:  # pandas plotting may use pyplot state
        table.set_index(index).plot.bar(ax=ax)
    return figure


@register_tool
class PCAnalysis(Tool[PCAConfig]):
    """Principal component analysis (scikit-learn) of the features."""

    name = "PCA"
    category = "Analysis"
    description = (
        "Principal component analysis of the features, standardized by default."
        " Components to keep: a number, a fraction (0..1) of the variance to explain,"
        " or all."
    )
    icon = "pca.png"

    def run(self, data: pd.DataFrame, *, config: PCAConfig) -> dict[str, Any]:
        """Compute the principal components of the selected features.

        Rows with missing values in the features are left out.

        Args:
            data: The table.
            config: The features; whether they are standardized before the analysis
                (`standardize_input`); the number of components (`n_components`: a
                number, a fraction of the variance to explain, or None for all); the
                columns kept besides the categories (`keep_original`,
                `keep_standardized`); `explained_plot`; and `random_seed`.

        Returns:
            `PCA Components`: the category columns, the kept features, and a column
            `PC <n>` per component (numbered if the table has the name already).
            `PCA Explained`: the ratio of the variance each component explains.
            `PCA Eigen`: the components' coefficients, a row per component and a
            column per feature. With `explained_plot`, `PCA Explained Plot`: a bar
            chart of the explained ratios.
        """
        from sklearn.decomposition import PCA

        features = selected_features(data, config.features)
        data = complete_rows(data, features)
        values = prepared(data[features], config.standardize_input)
        pca = PCA(n_components=config.n_components, random_state=config.random_seed)
        with threadpool_limits(self.context.threads):
            components = pca.fit_transform(values)
        parts = [data[category_columns(data)]]
        if config.keep_original:
            parts.append(data[features])
        taken = [c for part in parts for c in part.columns]
        if config.keep_standardized:
            standard = values if config.standardize_input else prepared(data[features], True)
            names = free_names([f"{f}\nstandardized" for f in features], taken)
            parts.append(pd.DataFrame(standard, columns=names))
            taken += names
        # new names that the table has (e.g. from an earlier PCA) are numbered
        component_df = pd.DataFrame(
            components,
            columns=free_names(
                [f"PC {i}" for i in range(1, components.shape[1] + 1)], taken
            ),
        )
        parts.append(component_df)
        explained = pd.DataFrame(
            {
                "PC": [
                    str(i) for i in range(1, len(pca.explained_variance_ratio_) + 1)
                ],
                "explained var ratio": pca.explained_variance_ratio_,
            }
        )
        explained["PC"] = explained["PC"].astype("category")
        results = {
            "PCA Components": pd.concat(parts, axis=1),
            "PCA Explained": explained,
            "PCA Eigen": pd.DataFrame(pca.components_, columns=features),
        }
        if config.explained_plot:
            results["PCA Explained Plot"] = bar_chart(explained, "PC")
        return results


@register_tool
class KMeansClustering(Tool[KMeansConfig]):
    """K-means clustering (scikit-learn) of the rows by their features."""

    name = "K-Means"
    category = "Analysis"
    description = "K-means clustering of the features, standardized by default."
    icon = "kmeans.png"
    outputs = (OutputSpec("K-Means", TableType),)

    def run(self, data: pd.DataFrame, *, config: KMeansConfig) -> dict[str, Any]:
        """Cluster the rows by the selected features.

        Rows with missing values in the features are left out. A column that has the
        name of the cluster column is replaced, with a warning.

        Args:
            data: The table.
            config: The features; `standardize_input`; the number of clusters
                (`n_clusters`); the name of the cluster column (`cluster_prefix`); and
                the settings of scikit-learn's `KMeans`: `init`, `algorithm`,
                `n_init`, `max_iter`, `tolerance` and `random_seed`.

        Returns:
            `K-Means`: the category columns and features of the rows, and a category
            column named `cluster_prefix` with the values `<cluster_prefix> 1`,
            `<cluster_prefix> 2`, and so on, after the other category columns.
        """
        from sklearn.cluster import KMeans

        features = selected_features(data, config.features)
        data = complete_rows(data, features)
        kmeans = KMeans(
            n_clusters=config.n_clusters,
            init=config.init,
            algorithm=config.algorithm,
            n_init=config.n_init,
            max_iter=config.max_iter,
            tol=config.tolerance,
            random_state=config.random_seed,
        )
        with threadpool_limits(self.context.threads):
            kmeans.fit(prepared(data[features], config.standardize_input))
        label = config.cluster_prefix
        table = data.copy()
        if label in table.columns:  # a name the user chose: replaced, as Calculate
            self.warn(f"the column '{label}' is replaced by the clusters")
        table[label] = pd.Categorical([f"{label} {i + 1}" for i in kmeans.labels_])
        return {"K-Means": categories_first(table)}


def full_covariances(
    values: np.ndarray, covariance: str, n_components: int, n_features: int
) -> np.ndarray:
    """Return a mixture model's covariances as one full matrix per component.

    Args:
        values: The model's `covariances_`, whose shape depends on `covariance`.
        covariance: The covariance type: `full`, `tied`, `diag` or `spherical`.
        n_components: The number of components.
        n_features: The number of features.

    Returns:
        The matrices, shape (n_components, n_features, n_features).
    """
    if covariance == "full":  # each component has its own matrix
        return values
    if covariance == "tied":  # all components share one matrix
        return np.array([values for _ in range(n_components)])
    if covariance == "diag":  # axis-aligned per component
        return np.array([np.diag(values[i]) for i in range(n_components)])
    # spherical: one variance per component
    return np.array(
        [np.diag(np.full(n_features, values[i])) for i in range(n_components)]
    )


@register_tool
class GaussianMixedModel(Tool[GMMConfig]):
    """Gaussian mixture model clustering (scikit-learn) of the rows."""

    name = "Gaussian Mixed Model"
    category = "Analysis"
    description = (
        "Gaussian mixture model clustering (EM or variational Bayesian), with BIC"
        " and AIC for 1 to n components."
    )
    icon = "gmm.png"

    def run(self, data: pd.DataFrame, *, config: GMMConfig) -> dict[str, Any]:
        """Fit a Gaussian mixture model to the selected features and cluster the rows.

        Rows with missing values in the features are left out. Models with 1 to
        `n_components` components are fitted for the information criteria.

        Args:
            data: The table.
            config: The features; `standardize_input`; the fitting `method` (`EM`, or
                `Variational Bayesian`, for which `n_components` is the largest
                number of components); `n_components`; the `covariance` type; and
                `random_seed`.

        Returns:
            `GMM <covariance>, Feature Clustering`: the category columns and features
            of the rows, a category column `GMM <covariance>` with each row's
            component, and a column `GMM Prob Component <n>` per component with the
            row's probability (generated names the table has are numbered).
            `GMM <covariance>, Covariance, component <n>`: a matrix per component,
            feature by feature, with ` (standardized)` after `Covariance` for
            standardized input. `GMM <covariance>, Component Information Criteria`:
            BIC and AIC of the models with 1 to `n_components` components.
        """
        from sklearn.mixture import BayesianGaussianMixture, GaussianMixture

        features = selected_features(data, config.features)
        data = complete_rows(data, features)
        values = prepared(data[features], config.standardize_input)
        n, covariance = config.n_components, config.covariance
        seed = config.random_seed
        with threadpool_limits(self.context.threads):
            # information criteria for 1..n components
            models = [
                GaussianMixture(k, covariance_type=covariance, random_state=seed).fit(
                    values
                )
                for k in range(1, n + 1)
            ]
            self.check_cancelled()
            criteria = pd.DataFrame(
                {
                    "Component": list(range(1, n + 1)),
                    "BIC": [m.bic(values) for m in models],
                    "AIC": [m.aic(values) for m in models],
                }
            )
            criteria["Component"] = criteria["Component"].astype("category")
            if config.method == "EM":
                model = GaussianMixture(
                    n_components=n, covariance_type=covariance, random_state=seed
                )
            else:
                model = BayesianGaussianMixture(
                    n_components=n,  # max number of components
                    covariance_type=covariance,
                    weight_concentration_prior=1e-3,  # low: sparse weights
                    random_state=seed,
                )
            model.fit(values)
            probabilities = model.predict_proba(values)
            predictions = model.predict(values)

        matrices = full_covariances(model.covariances_, covariance, n, len(features))
        label = f"GMM {covariance}"
        table = data.copy()
        # generated names the table has (e.g. from an earlier GMM) are numbered
        (column,) = free_names([label], table.columns)
        table[column] = pd.Categorical([f"{label} {i + 1}" for i in predictions])
        names = free_names([f"GMM Prob Component {i}" for i in range(1, n + 1)], table.columns)
        table = pd.concat(
            [table, pd.DataFrame(probabilities, columns=names, index=table.index)],
            axis=1,
        )
        # standardized input: the covariances are in standardized units
        units = " (standardized)" if config.standardize_input else ""
        results = {
            f"{label}, Covariance{units}, component {i + 1}": pd.DataFrame(
                matrix, index=features, columns=features
            )
            for i, matrix in enumerate(matrices)
        }
        results[f"{label}, Feature Clustering"] = categories_first(table)
        results[f"{label}, Component Information Criteria"] = criteria
        return results


@register_tool
class RandomForest(Tool[RandomForestConfig]):
    """Random forest classifier (scikit-learn) that predicts a category column."""

    name = "Random Forest"
    category = "Analysis"
    description = (
        "Trains a random forest to predict the target category from the features"
        " and reports the features' importance and the accuracy on test data."
    )
    icon = "randomforest.png"

    def run(
        self, data: pd.DataFrame, *, config: RandomForestConfig
    ) -> dict[str, Any]:
        """Train a random forest on part of the rows and test it on the others.

        Rows with a missing value in any column are left out. Features that are also
        grouping columns are not used.

        Args:
            data: The table.
            config: The features; the category column to predict (`target`); the
                number of trees (`n_estimators`); the fraction of rows for testing
                (`test_size`); `importance_plot`; and `random_seed`.

        Returns:
            `Importance Score Data`: each feature's importance, largest first.
            `Accuracy Data`: the accuracy on the test rows and the numbers of
            training and test rows. With `importance_plot`, `Importance Score Plot`:
            a bar chart of the importances, labelled with the accuracy.

        Raises:
            ValueError: If no target column is selected.
        """
        from sklearn import metrics
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.model_selection import train_test_split

        if config.target is None:
            raise ValueError(f"{self.name}: no target column selected")
        data = data.dropna(how="any", axis=0)
        features = [
            f
            for f in selected_features(data, config.features)
            if f not in config.grouping
        ]
        x_train, x_test, y_train, y_test = train_test_split(
            data[features],
            data[config.target],
            test_size=config.test_size,
            random_state=config.random_seed,
        )
        classifier = RandomForestClassifier(
            n_estimators=config.n_estimators,
            n_jobs=self.context.threads,
            random_state=config.random_seed,
        )
        classifier.fit(x_train, y_train)
        accuracy = metrics.accuracy_score(y_test, classifier.predict(x_test))
        importance = pd.DataFrame(
            {"Feature": features, "Importance Score": classifier.feature_importances_}
        )
        importance["Feature"] = importance["Feature"].astype("category")
        importance = importance.sort_values(by="Importance Score", ascending=False)
        results = {}
        if config.importance_plot:
            figure = bar_chart(importance, "Feature")
            ax = figure.axes[0]
            ax.text(
                0.95,
                0.80,
                f"accuracy={accuracy:.3f}",
                horizontalalignment="right",
                verticalalignment="center",
                transform=ax.transAxes,
            )
            results["Importance Score Plot"] = figure
        results["Importance Score Data"] = importance
        results["Accuracy Data"] = pd.DataFrame(
            {
                "Accuracy": [accuracy],
                "Training rows": [len(y_train)],
                "Test rows": [len(y_test)],
            }
        )
        return results

    @classmethod
    def validate(
        cls, config: RandomForestConfig, inputs: Sequence[Any]
    ) -> list[Issue]:
        """Check the config; a missing target column is an error."""
        issues = super().validate(config, inputs)
        if config.target is None:
            issues.append(Issue("target", "Select the category column to predict"))
        return issues


@register_tool
class Categorizer(Tool[CategorizerConfig]):
    """A new category column from rules on ranges of feature values."""

    name = "Categorize Data"
    category = "Analysis"
    description = (
        "Adds a category column: rows whose feature value lies in a rule's range"
        " (min < value <= max) get the rule's value, all others the default."
    )
    icon = "categorize.png"

    def run(self, data: pd.DataFrame, *, config: CategorizerConfig) -> dict[str, Any]:
        """Add a category column whose values come from the first rule each row meets.

        A row meets a rule if the rule's feature has a value `min < value <= max`.
        Rows that meet no rule get the default value. A column that has the new
        column's name is replaced, with a warning.

        Args:
            data: The table.
            config: The new column's `name`; the `rules` (value, feature, min, max);
                the `default` value; and whether all input columns are kept
                (`merge_input`), otherwise only the category columns and the
                selected `features`.

        Returns:
            `Categorized`: the table with the new column inserted after the first n
            columns, n being the number of other category columns (after them in a
            table whose category columns come first). Its categories are the rules'
            values, then the default value.
        """
        categories = [c for c in category_columns(data) if c != config.name]
        if config.merge_input:
            table = data.copy()
        else:
            features = selected_features(data, config.features)
            table = data[categories + features].copy()
        values = pd.Series(config.default, index=data.index, dtype=object)
        assigned = pd.Series(False, index=data.index)
        for rule in config.rules:  # a row gets the value of the first rule it matches
            x = data[rule.feature]
            match = (x > rule.min) & (x <= rule.max) & ~assigned
            values[match] = rule.value
            assigned |= match
        labels = list(dict.fromkeys([r.value for r in config.rules] + [config.default]))
        if config.name in table.columns:  # a name the user chose: replaced
            self.warn(f"the column '{config.name}' is replaced")
            table = table.drop(columns=config.name)
        table.insert(
            len(categories), config.name, pd.Categorical(values, categories=labels)
        )
        return {"Categorized": table}
