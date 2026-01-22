import os
import joblib
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
import sys

# Add parent directory to path to import database models
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.database_models import SensorReading, Base
from backend.database import SQLALCHEMY_DATABASE_URL

class ModelTrainer:
    def __init__(self, db_url=SQLALCHEMY_DATABASE_URL):
        """Initialize the model trainer with database connection."""
        self.engine = create_engine(db_url)
        self.Session = sessionmaker(bind=self.engine)
        self.model_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'model')
        os.makedirs(self.model_dir, exist_ok=True)
    
    def fetch_training_data(self, limit=10000):
        """Fetch training data directly from the database."""
        session = self.Session()
        try:
            # Get the most recent records up to the limit
            stmt = select(SensorReading).order_by(SensorReading.timestamp.desc()).limit(limit)
            result = session.execute(stmt)
            
            # Convert to DataFrame
            data = [{
                'tds': row.SensorReading.tds,
                'turbidity': row.SensorReading.turbidity,
                'leak': row.SensorReading.leak,
                'class': 1 if row.SensorReading.is_safe else 0  # Convert boolean to int for classification
            } for row in result]
            
            if not data:
                raise ValueError("No training data found in the database")
                
            return pd.DataFrame(data)
        except Exception as e:
            print(f"Error fetching training data: {str(e)}")
            raise
        finally:
            session.close()
    
    def preprocess_data(self, df):
        """Preprocess the data and split into features/target."""
        # Handle null values by filling with appropriate defaults
        # This is realistic for sensor data where sensors can be disconnected
        df_processed = df.copy()
        
        # Fill null turbidity with median (sensor disconnected)
        if df_processed['turbidity'].isnull().any():
            median_turbidity = df_processed['turbidity'].median()
            df_processed['turbidity'].fillna(median_turbidity, inplace=True)
            print(f"Filled {df_processed['turbidity'].isnull().sum()} null turbidity values with median: {median_turbidity:.2f}")
        
        # Features and target
        X = df_processed[['tds', 'turbidity', 'leak']]
        y = df_processed['class']
        
        return X, y
    
    def train_model(self, X, y):
        """Train a RandomForest classifier."""
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.model_selection import train_test_split
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        # Train model
        model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1
        )
        
        model.fit(X_train, y_train)
        return model, (X_test, y_test)
    
    def evaluate_model(self, model, X_test, y_test):
        """Evaluate model performance."""
        from sklearn.metrics import accuracy_score, classification_report
        
        y_pred = model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        report = classification_report(y_test, y_pred)
        
        print(f"\nModel Evaluation:")
        print(f"Accuracy: {accuracy:.4f}")
        print("\nClassification Report:")
        print(report)
        
        return accuracy
    
    def save_model(self, model, model_name=None):
        """Save model with timestamp and update current_model.txt."""
        # Create models directory if it doesn't exist
        os.makedirs(self.model_dir, exist_ok=True)
        
        # Generate model filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if model_name:
            model_filename = f"{model_name}_{timestamp}.pkl"
        else:
            model_filename = f"model_{timestamp}.pkl"
            
        model_path = os.path.join(self.model_dir, model_filename)
        
        # Save the model
        joblib.dump(model, model_path)
        print(f"Model saved to {model_path}")
        
        # Update current_model.txt
        current_model_file = os.path.join(self.model_dir, 'current_model.txt')
        with open(current_model_file, 'w') as f:
            f.write(model_filename)
        
        print(f"Updated current model reference in {current_model_file}")
        return model_path

def main():
    try:
        print("Starting model training...")
        
        # Initialize trainer
        trainer = ModelTrainer()
        
        # Fetch and prepare data
        print("Fetching training data from database...")
        df = trainer.fetch_training_data()
        print(f"Retrieved {len(df)} records for training")
        
        # Preprocess data
        print("Preprocessing data...")
        X, y = trainer.preprocess_data(df)
        
        # Train model
        print("Training model...")
        model, (X_test, y_test) = trainer.train_model(X, y)
        
        # Evaluate model
        print("Evaluating model...")
        trainer.evaluate_model(model, X_test, y_test)
        
        # Save model
        print("\nSaving model...")
        trainer.save_model(model, "water_quality_model")
        
        print("\nTraining completed successfully!")
        
    except Exception as e:
        print(f"Error during model training: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
