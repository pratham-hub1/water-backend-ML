import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report
import joblib
import os

def load_data(filepath):
    """Load and return the dataset from CSV."""
    return pd.read_csv(filepath)

def preprocess_data(df):
    """Split features and target, then split into train/test sets."""
    # Features and target
    X = df[['tds', 'turbidity', 'leak']]
    y = df['class']
    
    # Split into train and test sets
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    return X_train, X_test, y_train, y_test

def train_model(X_train, y_train):
    """Train and return a RandomForestClassifier."""
    # Initialize model with some basic parameters
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        min_samples_split=5,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1  # Use all available cores
    )
    
    # Train the model
    model.fit(X_train, y_train)
    return model

def evaluate_model(model, X_train, X_test, y_train, y_test):
    """Evaluate the model and print metrics."""
    # Make predictions
    y_train_pred = model.predict(X_train)
    y_test_pred = model.predict(X_test)
    
    # Calculate accuracies
    train_accuracy = accuracy_score(y_train, y_train_pred)
    test_accuracy = accuracy_score(y_test, y_test_pred)
    
    # Print metrics
    print("\nModel Evaluation")
    print("----------------")
    print(f"Training Accuracy: {train_accuracy:.4f}")
    print(f"Test Accuracy: {test_accuracy:.4f}\n")
    
    # Print confusion matrix
    print("Confusion Matrix (Test Set):")
    conf_matrix = confusion_matrix(y_test, y_test_pred)
    conf_matrix_df = pd.DataFrame(
        conf_matrix,
        index=['Actual 0', 'Actual 1', 'Actual 2'],
        columns=['Predicted 0', 'Predicted 1', 'Predicted 2']
    )
    print(conf_matrix_df)
    
    # Print classification report
    print("\nClassification Report (Test Set):")
    print(classification_report(y_test, y_test_pred, target_names=['Class 0', 'Class 1', 'Class 2']))
    
    return test_accuracy

def save_model(model, filepath):
    """Save the trained model to disk."""
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(filepath) or '.', exist_ok=True)
    joblib.dump(model, filepath)
    print(f"\nModel saved to {os.path.abspath(filepath)}")

def main():
    # File paths - using absolute paths to avoid any path resolution issues
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(base_dir, "..", "data", "water_quality.csv")
    model_path = os.path.join(base_dir, "water_model.pkl")
    
    print("Starting model training...")
    
    try:
        # Load and prepare data
        print("Loading data...")
        df = load_data(data_path)
        
        print("Preprocessing data...")
        X_train, X_test, y_train, y_test = preprocess_data(df)
        
        # Train model
        print("Training model...")
        model = train_model(X_train, y_train)
        
        # Evaluate model
        print("Evaluating model...")
        evaluate_model(model, X_train, X_test, y_train, y_test)
        
        # Save model
        save_model(model, model_path)
        
        print("\nModel training completed successfully!")
        
    except Exception as e:
        print(f"\nAn error occurred: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    main()
