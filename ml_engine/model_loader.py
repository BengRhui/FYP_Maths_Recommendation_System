"""
This file handles the loading of the champion CatBoost model and the prediction of probabilities.
"""

import json
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

# The list of features used by the CatBoost model
DEFAULT_FEATURE_ORDER = [
    "sq_prev_attempt_count",
    "sq_is_first_attempt",
    "sq_last_attempt_outcome",
    "sq_recency_sec",
    "s_overall_accuracy",
    "s_time_since_last",
    "s_total_attempts",
    "s_correct_streak",
    "ss_micro_mastery",
    "ss_micro_avg_attempts",
    "ss_macro_mastery",
    "ss_macro_avg_attempts",
    "ss_micro_recent_sec",
    "ss_micro_correct_streak",
    "ss_micro_wrong_streak",
    "bkt_mastery",
    "q_global_attempt_count",
    "q_global_accuracy",
    "is_selection_based",
    "is_input_based",
    "is_cold_start",
]

# The filename for the model and its feature order
MODEL_FILENAME = "champion_catboost.cbm"
FEATURE_ORDER_FILENAME = "feature_order.json"

# The class to handle the CatBoost model
class ChampionModel:

    # Model is initially missing
    _instance = None

    # Constructor
    def __init__(self):
        self.model = None
        self.feature_order = DEFAULT_FEATURE_ORDER
        self._load()

    # A method to ensure that even new declaration of the class will return the same instance
    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # Method to initialize the model
    def _load(self):

        # Declare the path
        model_path = settings.ML_MODEL_DIR / MODEL_FILENAME
        order_path = settings.ML_MODEL_DIR / FEATURE_ORDER_FILENAME

        # Load the feature order and use default if it does not exist
        if order_path.exists():
            try:
                self.feature_order = json.loads(order_path.read_text())
            except (ValueError, OSError):
                logger.warning("Could not read %s; using default feature order.", order_path)

        # Check if model exist, if not use baseline BKT
        if not model_path.exists():
            logger.info(
                "No champion model at %s — recommender will use the BKT heuristic. "
                "Run 3_training.ipynb to enable CatBoost predictions.",
                model_path,
            )
            return

        try:
            from catboost import CatBoostClassifier

            # Load the CatBoost model
            model = CatBoostClassifier()
            model.load_model(str(model_path))
            self.model = model
            logger.info("Loaded champion CatBoost model from %s", model_path)

        except Exception as exc:
            logger.warning("Failed to load champion model (%s); using heuristic.", exc)
            self.model = None

    # A method to check if the model is loaded
    @property
    def is_ready(self):
        return self.model is not None

    # A method to predict the probability for one question
    def predict_proba(self, feature_dict):

        # Use the predict_proba_batch to get probability
        result = self.predict_proba_batch([feature_dict])
        return None if result is None else result[0]

    # A method to predict the probability for more than one questions
    def predict_proba_batch(self, feature_dicts):

        # Check if the model is loaded
        if self.model is None or not feature_dicts:
            return None

        # Extract the features for prediction
        rows = [
            [features.get(name, -1) for name in self.feature_order]     # Use -1 for missing features (imputation)
            for features in feature_dicts
        ]

        # Perform prediction in batch and return probability
        try:
            probs = self.model.predict_proba(rows)
            return [float(p[1]) for p in probs]

        except Exception as exc:
            logger.warning("CatBoost prediction failed (%s); using heuristic.", exc)
            return None

# A function to return the instance of the CatBoost model
def get_model():
    return ChampionModel.instance()
