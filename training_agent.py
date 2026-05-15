from tool_schemas import MLTrainInput, MLTrainOutput
import os

class TrainingAgent:
    """A tool to train a model from a configurable dataset file."""

    def train_startup_model(self, file_path: str = None, target_column: str = None) -> str:
        """Train a RandomForest model on the given CSV. Defaults to 50_startup.csv / Profit."""
        csv_path = file_path or os.path.expanduser("~/train/50_startup.csv")
        target = target_column or "Profit"
        try:
            import pandas as pd
            from sklearn.model_selection import train_test_split
            from sklearn.ensemble import RandomForestRegressor
            from sklearn.metrics import r2_score, mean_absolute_error
            import pickle

            df = pd.read_csv(csv_path)
            if target not in df.columns:
                return MLTrainOutput(
                    success=False, summary=f"Column '{target}' not found in {csv_path}",
                    error=f"Available columns: {list(df.columns)}"
                ).model_dump_json()

            df = pd.get_dummies(df, drop_first=True)
            X = df.drop(columns=[target])
            y = df[target]
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

            model = RandomForestRegressor(n_estimators=100, random_state=42)
            model.fit(X_train, y_train)
            preds = model.predict(X_test)

            metrics = {
                "r2": round(r2_score(y_test, preds), 4),
                "mae": round(mean_absolute_error(y_test, preds), 2),
            }

            model_path = "startup_model.pkl"
            with open(model_path, "wb") as f:
                pickle.dump(model, f)

            return MLTrainOutput(
                success=True,
                summary=f"Model trained. R2={metrics['r2']}, MAE={metrics['mae']}",
                model_path=model_path,
                metrics=metrics,
            ).model_dump_json()

        except Exception as e:
            return MLTrainOutput(
                success=False, summary=f"Training failed: {e}", error=str(e)
            ).model_dump_json()
