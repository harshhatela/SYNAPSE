import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
import pickle
import os

class TrainingAgent:
    """A tool to train a hardcoded model from a local dataset file."""

    # THE FIX IS ON THE NEXT LINE:
    # We add a placeholder argument to accept the agent's default input.
    def train_startup_model(self, dummy_input: str = "") -> str:
        """
        Trains a model on the hardcoded '~/train/50_startup.csv' file
        to predict the 'Profit' column. It takes no real arguments.
        """
        # Hardcoded file path and target column
        file_path = os.path.expanduser('~/train/50_startup.csv')
        target_column = 'Profit'

        try:
            if not os.path.exists(file_path):
                return f"Error: The file was not found at {file_path}. Please ensure it exists."

            df = pd.read_csv(file_path)
            
            # One-hot encode the 'State' column as it's categorical
            df = pd.get_dummies(df, columns=['State'], drop_first=True)
            
            if target_column not in df.columns:
                return f"Error: Target column '{target_column}' not found."

            X = df.drop(target_column, axis=1)
            y = df[target_column]
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

            model = RandomForestRegressor(n_estimators=100, random_state=42)
            model.fit(X_train, y_train)
            score = model.score(X_test, y_test)

            model_path = "startup_model.pkl"
            with open(model_path, 'wb') as f:
                pickle.dump(model, f)
            
            return f"Startup model training complete. R^2 Score: {score:.2f}. Model saved to {model_path}"
        except Exception as e:
            return f"An error occurred during model training: {str(e)}"