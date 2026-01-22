import os
import joblib
import pandas as pd
import numpy as np
from datetime import datetime
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import sys

# Add parent directory to path to import database models
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.database_models import SensorReading
from backend.database import SQLALCHEMY_DATABASE_URL

class AnomalyDetectorTrainer:
    def __init__(self, db_url=SQLALCHEMY_DATABASE_URL):
        """Initialize the anomaly detector trainer with database connection."""
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
                'leak': int(row.SensorReading.leak)  # Convert boolean to int
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
        """Preprocess the data for anomaly detection."""
        # Handle null values by filling with appropriate defaults
        # This is realistic for sensor data where sensors can be disconnected
        df_processed = df.copy()
        
        # Fill null turbidity with median (sensor disconnected)
        if df_processed['turbidity'].isnull().any():
            median_turbidity = df_processed['turbidity'].median()
            df_processed['turbidity'].fillna(median_turbidity, inplace=True)
            print(f"Filled {df_processed['turbidity'].isnull().sum()} null turbidity values with median: {median_turbidity:.2f}")
        
        # Select features for anomaly detection
        features = ['tds', 'turbidity', 'leak']
        return df_processed[features].values
    
    def train_anomaly_detector(self, X, contamination=0.1):
        """Train an Isolation Forest anomaly detector."""
        # Scale the features
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)
        
        # Train Isolation Forest
        print("Training Isolation Forest model...")
        model = IsolationForest(
            n_estimators=100,
            contamination=contamination,
            random_state=42,
            n_jobs=-1
        )
        
        model.fit(X_scaled)
        return model
    
    def evaluate_model(self, model, X):
        """Evaluate the anomaly detection model."""
        X_scaled = self.scaler.transform(X)
        predictions = model.predict(X_scaled)
        anomaly_ratio = (predictions == -1).mean()
        
        print("\nAnomaly Detection Model Evaluation:")
        print(f"- Anomaly ratio in training data: {anomaly_ratio:.2%}")
        return anomaly_ratio
    
    def save_artifacts(self, model, model_name=None):
        """Save model and scaler with timestamps and update current_anomaly_model.txt."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Generate filenames
        if model_name:
            model_filename = f"{model_name}_anomaly_{timestamp}.pkl"
            scaler_filename = f"{model_name}_scaler_{timestamp}.pkl"
        else:
            model_filename = f"anomaly_model_{timestamp}.pkl"
            scaler_filename = f"anomaly_scaler_{timestamp}.pkl"
        
        # Save model and scaler
        model_path = os.path.join(self.model_dir, model_filename)
        scaler_path = os.path.join(self.model_dir, scaler_filename)
        
        joblib.dump(model, model_path)
        joblib.dump(self.scaler, scaler_path)
        
        print(f"Anomaly model saved to {model_path}")
        print(f"Scaler saved to {scaler_path}")
        
        # Update current model references
        current_model_file = os.path.join(self.model_dir, 'current_anomaly_model.txt')
        with open(current_model_file, 'w') as f:
            f.write(f"model={model_filename}\n")
            f.write(f"scaler={scaler_filename}")
        
        print(f"Updated current model reference in {current_model_file}")
        return model_path, scaler_path

def main():
    try:
        print("Starting anomaly detector training...")
        
        # Initialize trainer
        trainer = AnomalyDetectorTrainer()
        
        # Fetch and prepare data
        print("Fetching training data from database...")
        df = trainer.fetch_training_data()
        print(f"Retrieved {len(df)} records for training")
        
        # Preprocess data
        print("Preprocessing data...")
        X = trainer.preprocess_data(df)
        
        # Train model
        print("Training anomaly detection model...")
        model = trainer.train_anomaly_detector(X)
        
        # Evaluate model
        print("Evaluating model...")
        trainer.evaluate_model(model, X)
        
        # Save model and scaler
        print("\nSaving model artifacts...")
        trainer.save_artifacts(model, "water_quality")
        
        print("\nAnomaly detector training completed successfully!")
        
    except Exception as e:
        print(f"Error during anomaly detector training: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
