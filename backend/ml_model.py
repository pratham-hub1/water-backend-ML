import joblib
import os
from typing import Optional
import glob

# Load trained scikit-learn model once
# Automatically find and load the most recent trained model

def find_latest_model(pattern):
    """Find the most recent model file matching pattern."""
    model_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'model'))
    model_files = glob.glob(os.path.join(model_dir, pattern))
    if not model_files:
        return None
    
    # Sort by modification time, get the latest
    latest_model = max(model_files, key=os.path.getmtime)
    return latest_model

# Try database-trained models first, fallback to CSV-trained models
_MODEL_PATH_DB = find_latest_model('water_quality_model_*.pkl')
_MODEL_PATH_CSV = find_latest_model('water_model_csv_legacy.pkl')
_MODEL_PATH = _MODEL_PATH_DB if _MODEL_PATH_DB and os.path.exists(_MODEL_PATH_DB) else (_MODEL_PATH_CSV if _MODEL_PATH_CSV and os.path.exists(_MODEL_PATH_CSV) else None)
_model = None
if os.path.exists(_MODEL_PATH):
    _model = joblib.load(_MODEL_PATH)
else:
    raise FileNotFoundError(f"Model file not found at {_MODEL_PATH}")

def predict_water_quality(tds: Optional[float] = None, turbidity: Optional[float] = None, leak: Optional[bool] = None, ph_value: Optional[float] = None) -> dict:
    """
    Predict water quality class and safety using trained ML model.
    
    Args:
        tds: Total dissolved solids in ppm (float > 0) - Optional
        turbidity: Turbidity in NTU (float >= 0) - Optional  
        leak: Boolean indicating if there's a leak (True/False) - Optional
        
    Returns:
        dict with keys: 'class' (int), 'is_safe' (bool), 'replacement_needed' (bool), 'confidence' (float), 'reasoning' (str)
    """
    if _model is None:
        raise RuntimeError("ML model is not loaded.")
    
    # Check if we have enough sensor data for ML prediction
    available_sensors = []
    missing_sensors = []
    
    if tds is not None:
        available_sensors.append('tds')
    else:
        missing_sensors.append('tds')
        
    if turbidity is not None:
        available_sensors.append('turbidity')
    else:
        missing_sensors.append('turbidity')
        
    if leak is not None:
        available_sensors.append('leak')
    else:
        missing_sensors.append('leak')
    
    # If critical sensors are missing, use rule-based fallback
    if len(available_sensors) < 2:
        return {
            "class": 0,  # Default to safe
            "is_safe": True,
            "replacement_needed": False,
            "confidence": 0.3,  # Low confidence due to missing data
            "reasoning": f"Insufficient sensor data for ML prediction. Missing sensors: {', '.join(missing_sensors)}. Defaulting to safe status."
        }
    
    # For ML prediction, we need to handle missing values
    # Use conservative defaults for missing sensors
    tds_val = tds if tds is not None else 200.0  # Conservative middle value
    turbidity_val = turbidity if turbidity is not None else 2.0  # Conservative low value
    leak_val = leak if leak is not None else False  # Assume no leak
    
    # Convert leak to int as required by the model
    leak_numeric = 1 if leak_val else 0
    features = [float(tds_val), float(turbidity_val), leak_numeric]
    pred_class = int(_model.predict([features])[0])
    is_safe = pred_class == 0
    replacement_needed = (pred_class != 0)
    
    # Adjust confidence based on missing sensors
    base_confidence = 0.9
    confidence_penalty = len(missing_sensors) * 0.2  # Reduce confidence for each missing sensor
    final_confidence = max(0.3, base_confidence - confidence_penalty)
    
    reasoning = f"ML prediction based on available sensors: {', '.join(available_sensors)}"
    if missing_sensors:
        reasoning += f". Missing sensors: {', '.join(missing_sensors)} - prediction has reduced confidence."
    
    return {
        "class": pred_class,
        "is_safe": is_safe,
        "replacement_needed": replacement_needed,
        "confidence": final_confidence,
        "reasoning": reasoning
    }


def calculate_filter_health(tds: Optional[float] = None, turbidity: Optional[float] = None, ph_value: Optional[float] = None) -> int:
    """
    Calculate filter health score based on TDS, turbidity, and pH.
    
    Args:
        tds: Total dissolved solids in ppm - Optional
        turbidity: Turbidity in NTU - Optional
        ph_value: pH sensor reading (0-14) - Optional
        
    Returns:
        Health score between 0-100 (100 = best)
    """
    # If all sensors are missing, return moderate health score
    if tds is None and turbidity is None and ph_value is None:
        return 70  # Moderate health when no data available
    
    # Initialize scores for available sensors
    tds_score = 0
    turbidity_score = 0
    ph_score = 0
    available_sensors = 0
    
    # Calculate TDS score if available
    if tds is not None:
        tds_score = max(0, min(100, 100 - (tds / 10)))  # 0-1000 maps to 100-0
        available_sensors += 1
    
    # Calculate turbidity score if available
    if turbidity is not None:
        turbidity_score = max(0, min(100, 100 - (turbidity * 3.33)))  # 0-30 maps to 100-0
        available_sensors += 1
    
    # Calculate pH score if available
    if ph_value is not None:
        if ph_value < 6.5:
            # Too acidic
            deviation = 6.5 - ph_value
            ph_score = max(0, min(100, 100 - (deviation * 20)))  # Penalty for acidic water
        elif ph_value > 8.5:
            # Too alkaline
            deviation = ph_value - 8.5
            ph_score = max(0, min(100, 100 - (deviation * 20)))  # Penalty for alkaline water
        else:
            # pH is in optimal range
            ph_score = 100
        available_sensors += 1
    
    # Calculate weighted average based on available sensors
    if available_sensors == 0:
        return 70  # No sensors available
    
    # Weight factors: TDS (40%), Turbidity (30%), pH (30%)
    total_weight = tds_score * 0.4 + turbidity_score * 0.3 + ph_score * 0.3
    health_score = int(total_weight / available_sensors)
    
    return max(0, min(100, health_score))  # Ensure within 0-100


def generate_reasons(tds: Optional[float] = None, turbidity: Optional[float] = None, leak: Optional[bool] = None, ph_value: Optional[float] = None, is_safe: bool = True, needs_replacement: bool = False) -> list[str]:
    """
    Generate human-readable reasons for water quality status and filter condition.
    
    Args:
        tds: Total dissolved solids in ppm - Optional
        turbidity: Turbidity in NTU - Optional
        leak: Boolean indicating if there's a leak - Optional
        ph_value: pH sensor reading (0-14) - Optional
        is_safe: Boolean indicating if water is safe
        needs_replacement: Boolean indicating if filter needs replacement
        
    Returns:
        List of human-readable reason strings
    """
    reasons = []
    available_sensors = []
    missing_sensors = []
    
    # Check available sensors
    if tds is not None:
        available_sensors.append('TDS')
        if tds > 500:
            reasons.append("TDS level is higher than safe drinking limits")
    else:
        missing_sensors.append('TDS')
    
    if turbidity is not None:
        available_sensors.append('turbidity')
        if turbidity > 5:
            reasons.append("High turbidity indicates poor filtration")
    else:
        missing_sensors.append('turbidity')
    
    if leak is not None:
        available_sensors.append('leak detection')
        if leak:
            reasons.append("Leak detected in water system")
    else:
        missing_sensors.append('leak detection')
    
    # Check pH sensor
    if ph_value is not None:
        available_sensors.append('pH')
        if ph_value < 6.5:
            reasons.append("Water is too acidic - pH below recommended range")
        elif ph_value > 8.5:
            reasons.append("Water is too alkaline - pH above recommended range")
        else:
            reasons.append("pH level is within normal range")
    else:
        missing_sensors.append('pH')
    
    # Add information about missing sensors
    if missing_sensors:
        reasons.append(f"Missing sensor data for: {', '.join(missing_sensors)}")
    
    # Add replacement reason if needed
    if needs_replacement:
        reasons.append("Filter performance has degraded and replacement is required")
    
    # Add safety status if no specific issues found
    if is_safe and not any("higher than safe" in reason or "High turbidity" in reason or "Leak detected" in reason or "too acidic" in reason or "too alkaline" in reason for reason in reasons):
        if available_sensors:
            reasons.append(f"Water quality is within acceptable limits based on available sensors: {', '.join(available_sensors)}")
        else:
            reasons.append("No sensor data available - unable to assess water quality")
    
    return reasons
