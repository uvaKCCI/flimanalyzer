"""Machine learning tools (scikit-learn) and rule-based categorization."""

import logging

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
from flim.tools.common import categories_first, category_columns, selected_features


def complete_rows(data: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    """The rows without missing values in ``features``, with their category columns,
    renumbered from 0."""
    rows = data[features].dropna(how="any", axis=0).index
    return data.loc[rows, category_columns(data) + features].reset_index(drop=True)


def standardized(values: np.ndarray) -> np.ndarray:
    from sklearn.preprocessing import StandardScaler

    return StandardScaler().fit_transform(values)


def bar_chart(table: pd.DataFrame, index: str) -> Figure:
    """A bar chart of ``table``'s values by ``index``, without pyplot's figure registry."""
    figure = Figure()
    ax = figure.add_subplot()
    with pyplot_lock:  # pandas plotting may use pyplot state
        table.set_index(index).plot.bar(ax=ax)
    return figure


@register_tool
class PCAnalysis(Tool[PCAConfig]):
    name = "PCA"
    category = "Analysis"
    description = (
        "Principal component analysis of the standardized features. Components to"
        " keep: a number, a fraction (0..1) of the variance to explain, or all."
    )
    icon = "pca.png"

    def run(self, data, *, config):
        from sklearn.decomposition import PCA

        features = selected_features(data, config.features)
        data = complete_rows(data, features)
        standard = standardized(data[features].to_numpy())
        pca = PCA(n_components=config.n_components, random_state=config.random_seed)
        with threadpool_limits(self.context.threads):
            components = pca.fit_transform(standard)
        component_df = pd.DataFrame(
            components,
            columns=[f"PC {i}" for i in range(1, components.shape[1] + 1)],
        )
        parts = [data[category_columns(data)]]
        if config.keep_original:
            parts.append(data[features])
        if config.keep_standardized:
            parts.append(
                pd.DataFrame(standard, columns=[f"{f}\nstandardized" for f in features])
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
    name = "K-Means"
    category = "Analysis"
    description = "K-means clustering of the standardized features."
    icon = "kmeans.png"
    outputs = (OutputSpec("K-Means", TableType),)

    def run(self, data, *, config):
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
            kmeans.fit(standardized(data[features].to_numpy()))
        label = config.cluster_prefix
        table = data.copy()
        table[label] = pd.Categorical([f"{label} {i + 1}" for i in kmeans.labels_])
        return {"K-Means": categories_first(table)}


def full_covariances(values, covariance, n_components, n_features) -> np.ndarray:
    """Covariance matrices (n_components, n_features, n_features) of a mixture model."""
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
    name = "Gaussian Mixed Model"
    category = "Analysis"
    description = (
        "Gaussian mixture model clustering (EM or variational Bayesian), with BIC"
        " and AIC for 1 to n components."
    )
    icon = "gmm.png"

    def run(self, data, *, config):
        from sklearn.mixture import BayesianGaussianMixture, GaussianMixture

        features = selected_features(data, config.features)
        data = complete_rows(data, features)
        values = data[features]
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
        table[label] = pd.Categorical([f"{label} {i + 1}" for i in predictions])
        table = pd.concat(
            [
                table,
                pd.DataFrame(
                    probabilities,
                    columns=[f"GMM Prob Component {i}" for i in range(1, n + 1)],
                ),
            ],
            axis=1,
        )
        results = {
            f"{label}, Covariance, component {i + 1}": pd.DataFrame(
                matrix, index=features, columns=features
            )
            for i, matrix in enumerate(matrices)
        }
        results[f"{label}, Feature Clustering"] = categories_first(table)
        results[f"{label}, Component Information Criteria"] = criteria
        return results


@register_tool
class RandomForest(Tool[RandomForestConfig]):
    name = "Random Forest"
    category = "Analysis"
    description = (
        "Trains a random forest to predict the target category from the features"
        " and reports the features' importance and the accuracy on test data."
    )
    icon = "randomforest.png"

    def run(self, data, *, config):
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
        return results

    @classmethod
    def validate(cls, config, inputs):
        issues = super().validate(config, inputs)
        if config.target is None:
            issues.append(Issue("target", "Select the category column to predict"))
        return issues


@register_tool
class Categorizer(Tool[CategorizerConfig]):
    name = "Categorize Data"
    category = "Analysis"
    description = (
        "Adds a category column: rows whose feature value lies in a rule's range"
        " (min < value <= max) get the rule's value, all others the default."
    )
    icon = "categorize.png"

    def run(self, data, *, config):
        categories = [c for c in category_columns(data) if c != config.name]
        if config.merge_input:
            table = data.copy()
        else:
            features = selected_features(data, config.features)
            table = data[categories + features].copy()
        values = pd.Series(config.default, index=data.index, dtype=object)
        assigned = pd.Series(False, index=data.index)
        for rule in config.rules:  # the first matching rule wins
            x = data[rule.feature]
            match = (x > rule.min) & (x <= rule.max) & ~assigned
            values[match] = rule.value
            assigned |= match
        labels = list(dict.fromkeys([r.value for r in config.rules] + [config.default]))
        if config.name in table.columns:
            logging.info(f"{self.name}: replacing column '{config.name}'")
            table = table.drop(columns=config.name)
        table.insert(
            len(categories), config.name, pd.Categorical(values, categories=labels)
        )
        return {"Categorized": table}
