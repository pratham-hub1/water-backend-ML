from typing import Dict, Optional, List, Tuple, Any
import numpy as np
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import joblib
from pathlib import Path
import os
import logging

# Configure logging
logger = logging.getLogger(__name__)

class AnomalyDetector:
    def __init__(self, db: Session):
        self.db = db
        # Define normal ranges (can be tuned based on domain knowledge)
        self.normal_ranges = {
            'tds': (0, 500),        # ppm
            'turbidity': (0, 5),    # NTU
            'leak': (0, 0)          # 0 = no leak
        }
        
        # Load ML model if available
        self.model = self._load_ml_model()
        self.scaler = self._load_scaler()
        
        # Define cause mappings
        self.cause_mapping = {
            'tds': {
                'high': "High TDS level detected ({} ppm)",
                'low': "Low TDS level detected ({} ppm)",
                'sensor_fault': "TDS sensor may be malfunctioning",
                'spike': "Sudden spike in TDS levels detected"
            },
            'turbidity': {
                'high': "High turbidity detected ({} NTU)",
                'low': "Low turbidity detected ({} NTU)",
                'sensor_fault': "Turbidity sensor may be malfunctioning",
                'spike': "Sudden change in water turbidity"
            },
            'leak': {
                'leak_detected': "Water leak detected",
                'sensor_fault': "Leak sensor may be malfunctioning"
            }
        }
        
        # Store recent readings for spike detection
        self.recent_readings = []
        self.max_readings = 10

    def _load_ml_model(self) -> Any:
        """Load the trained anomaly detection model."""
        try:
            # Try database-trained model first, fallback to CSV-trained model
            model_path_db = Path('model/water_quality_anomaly_20260107_224715.pkl')
            model_path_csv = Path('model/anomaly_model_csv_legacy.pkl')
            
            if model_path_db.exists():
                return joblib.load(model_path_db)
            elif model_path_csv.exists():
                logger.info("Using CSV-trained anomaly model (database-trained not found)")
                return joblib.load(model_path_csv)
            else:
                logger.warning("No anomaly model found")
                return None
        except Exception as e:
            logger.error(f"Error loading ML model: {e}")
            return None
            
    def _load_scaler(self) -> Any:
        """Load the feature scaler."""
        try:
            # Try database-trained scaler first, fallback to CSV-trained scaler
            scaler_path_db = Path('model/water_quality_scaler_20260107_224715.pkl')
            scaler_path_csv = Path('model/scaler_csv_legacy.pkl')
            
            if scaler_path_db.exists():
                return joblib.load(scaler_path_db)
            elif scaler_path_csv.exists():
                logger.info("Using CSV-trained scaler (database-trained not found)")
                return joblib.load(scaler_path_csv)
            else:
                logger.warning("No scaler found")
                return None
        except Exception as e:
            logger.error(f"Error loading scaler: {e}")
            return None

    def _preprocess_features(self, tds: float, turbidity: float, leak: bool) -> np.ndarray:
        """Preprocess input features for the ML model."""
        # Convert to numpy array and reshape for single sample
        features = np.array([[tds, turbidity, float(leak)]])
        
        # Scale features if scaler is available
        if self.scaler is not None:
            try:
                features = self.scaler.transform(features)
            except Exception as e:
                logger.error(f"Error scaling features: {e}")
        return features

    def detect_anomalies_ml(self, tds: float, turbidity: float, leak: bool) -> Dict:
        """
        Detect anomalies using ML model.
        Returns dict with anomaly detection results.
        """
        if self.model is None:
            return {
                'anomaly_detected': False,
                'confidence': 0.0,
                'cause': 'ML model not available',
                'details': []
            }
            
        try:
            # Preprocess features
            features = self._preprocess_features(tds, turbidity, leak)
            
            # Predict anomaly (1 for anomaly, -1 for normal)
            prediction = self.model.predict(features)[0]
            
            # Get confidence score (distance to the separating hyperplane)
            confidence_scores = self.model.decision_function(features)
            confidence = float(np.abs(confidence_scores[0]))
            
            # Adjust confidence threshold (higher = less sensitive)
            min_confidence = 0.7  # Increased threshold to reduce false positives
            is_anomaly = prediction == 1 and confidence > min_confidence
            
            return {
                'anomaly_detected': is_anomaly,
                'confidence': min(confidence, 1.0),  # Cap at 1.0
                'cause': 'ML model detected potential issue' if is_anomaly else 'No ML anomaly detected',
                'details': [{
                    'sensor': 'ml_model',
                    'value': 1.0 if is_anomaly else 0.0,
                    'anomaly_type': 'ml_anomaly' if is_anomaly else 'normal',
                    'confidence': min(confidence, 1.0),
                    'cause': 'ML model detected potential issue' if is_anomaly else 'Normal'
                }]
            }
            
        except Exception as e:
            logger.error(f"Error in ML-based anomaly detection: {e}")
            return {
                'anomaly_detected': False,
                'confidence': 0.0,
                'cause': 'Error in ML detection',
                'details': [{
                    'sensor': 'ml_model',
                    'value': 0.0,
                    'anomaly_type': 'error',
                    'confidence': 0.0,
                    'cause': str(e)
                }]
            }

    def _check_value(self, value: float, sensor: str) -> Optional[Dict]:
        """Check if a sensor value is within normal range."""
        if sensor not in self.normal_ranges:
            return None
            
        min_val, max_val = self.normal_ranges[sensor]
        range_width = max_val - min_val
        
        if value > max_val:
            # Calculate confidence based on how far above the maximum the value is
            deviation = (value - max_val) / range_width
            confidence = min(0.9 + (deviation * 0.1), 0.99)  # Cap at 0.99
            return {
                'sensor': sensor,
                'value': value,
                'anomaly_type': 'high',
                'confidence': confidence,
                'cause': self.cause_mapping[sensor]['high'].format(value)
            }
            
        if value < min_val:
            # Calculate confidence based on how far below the minimum the value is
            deviation = (min_val - value) / range_width
            confidence = min(0.9 + (deviation * 0.1), 0.99)  # Cap at 0.99
            return {
                'sensor': sensor,
                'value': value,
                'anomaly_type': 'low',
                'confidence': confidence,
                'cause': self.cause_mapping[sensor]['low'].format(value)
            }
            
        return None

    def _check_leak(self, leak: bool) -> Optional[Dict]:
        """Check for water leak."""
        if leak:
            return {
                'sensor': 'leak',
                'value': leak,
                'anomaly_type': 'leak_detected',
                'confidence': 0.95,  # High confidence for binary leak detection
                'cause': self.cause_mapping['leak']['leak_detected']
            }
        return None

    def _check_sensor_consistency(self, tds: float, turbidity: float, leak: bool) -> Optional[Dict]:
        """Check for inconsistent sensor readings that might indicate sensor issues."""
        # Check for leak with normal TDS and turbidity (possible false leak)
        if leak and tds < self.normal_ranges['tds'][1] * 0.9 and turbidity < self.normal_ranges['turbidity'][1] * 0.9:
            return {
                'sensor': 'leak',
                'value': leak,
                'anomaly_type': 'sensor_fault',
                'confidence': 0.8,  # Increased confidence
                'cause': self.cause_mapping['leak']['sensor_fault']
            }
            
        # Check for very high TDS with normal turbidity (possible TDS sensor issue)
        if tds > self.normal_ranges['tds'][1] * 2 and turbidity < self.normal_ranges['turbidity'][1] * 0.8:
            return {
                'sensor': 'tds',
                'value': tds,
                'anomaly_type': 'sensor_fault',
                'confidence': 0.75,
                'cause': self.cause_mapping['tds']['sensor_fault']
            }
            
        return None

    def _detect_anomalies_rule_based(self, tds: float, turbidity: float, leak: bool) -> Dict:
        """Rule-based anomaly detection."""
        anomalies = []
        confidence = 0.0
        causes = []
        
        # Check TDS
        tds_anomaly = self._check_value(tds, 'tds')
        if tds_anomaly:
            anomalies.append(tds_anomaly)
            confidence = max(confidence, tds_anomaly['confidence'])
            causes.append(tds_anomaly['cause'])
        
        # Check turbidity
        turbidity_anomaly = self._check_value(turbidity, 'turbidity')
        if turbidity_anomaly:
            anomalies.append(turbidity_anomaly)
            confidence = max(confidence, turbidity_anomaly['confidence'])
            causes.append(turbidity_anomaly['cause'])
        
        # Check for leaks
        leak_anomaly = self._check_leak(leak)
        if leak_anomaly:
            anomalies.append(leak_anomaly)
            confidence = max(confidence, leak_anomaly['confidence'])
            causes.append(leak_anomaly['cause'])
        
        # Check sensor consistency
        consistency_anomaly = self._check_sensor_consistency(tds, turbidity, leak)
        if consistency_anomaly:
            anomalies.append(consistency_anomaly)
            confidence = max(confidence, consistency_anomaly['confidence'])
            causes.append(consistency_anomaly['cause'])
        
        return {
            'anomaly_detected': len(anomalies) > 0,
            'confidence': confidence,
            'most_probable_cause': '; '.join(causes) if causes else '',
            'conclusion': 'Anomaly detected' if len(anomalies) > 0 else 'No anomalies detected',
            'details': anomalies
        }

    def _detect_anomalies_rule_based_adaptive(self, tds: Optional[float], turbidity: Optional[float], leak: Optional[bool], ph_value: Optional[float], available_sensors: List[str]) -> Dict:
        """Adaptive rule-based anomaly detection that handles missing sensors."""
        anomalies = []
        confidence = 0.0
        causes = []
        
        # Check TDS if available
        if tds is not None and 'TDS' in available_sensors:
            tds_anomaly = self._check_value(tds, 'tds')
            if tds_anomaly:
                anomalies.append(tds_anomaly)
                confidence = max(confidence, tds_anomaly['confidence'])
                causes.append(tds_anomaly['cause'])
        
        # Check turbidity if available
        if turbidity is not None and 'turbidity' in available_sensors:
            turbidity_anomaly = self._check_value(turbidity, 'turbidity')
            if turbidity_anomaly:
                anomalies.append(turbidity_anomaly)
                confidence = max(confidence, turbidity_anomaly['confidence'])
                causes.append(turbidity_anomaly['cause'])
        
        # Check leak if available
        if leak is not None and 'leak' in available_sensors:
            leak_anomaly = self._check_leak(leak)
            if leak_anomaly:
                anomalies.append(leak_anomaly)
                confidence = max(confidence, leak_anomaly['confidence'])
                causes.append(leak_anomaly['cause'])
        
        # Check pH if available (NEW)
        if ph_value is not None and 'pH' in available_sensors:
            ph_anomaly = self._check_ph_value(ph_value)
            if ph_anomaly:
                anomalies.append(ph_anomaly)
                confidence = max(confidence, ph_anomaly['confidence'])
                causes.append(ph_anomaly['cause'])
        
        # Check sensor consistency only if all sensors are available
        if all(sensor in available_sensors for sensor in ['TDS', 'turbidity', 'leak']):
            consistency_anomaly = self._check_sensor_consistency(tds, turbidity, leak)
            if consistency_anomaly:
                anomalies.append(consistency_anomaly)
                confidence = max(confidence, consistency_anomaly['confidence'])
                causes.append(consistency_anomaly['cause'])
        
        return {
            'anomaly_detected': len(anomalies) > 0,
            'confidence': confidence,
            'most_probable_cause': '; '.join(causes) if causes else '',
            'conclusion': 'Anomaly detected' if len(anomalies) > 0 else 'No anomalies detected',
            'details': anomalies
        }
    
    def _check_ph_value(self, ph_value: float) -> Optional[Dict]:
        """Check pH value for anomalies using rule-based thresholds."""
        if ph_value < 0 or ph_value > 14:
            # Invalid pH reading - possible sensor fault
            return {
                'sensor': 'ph',
                'value': ph_value,
                'anomaly_type': 'sensor_fault',
                'confidence': 0.9,
                'cause': f'pH sensor reading ({ph_value}) is outside valid range (0-14)'
            }
        
        # Define pH anomaly thresholds
        if ph_value < 6.0:
            # Too acidic
            deviation = 6.0 - ph_value
            confidence = min(0.8, 0.5 + (deviation * 0.1))
            return {
                'sensor': 'ph',
                'value': ph_value,
                'anomaly_type': 'low',
                'confidence': confidence,
                'cause': f'Water is too acidic (pH: {ph_value}) - below safe range'
            }
        
        if ph_value > 9.0:
            # Too alkaline
            deviation = ph_value - 9.0
            confidence = min(0.8, 0.5 + (deviation * 0.1))
            return {
                'sensor': 'ph',
                'value': ph_value,
                'anomaly_type': 'high',
                'confidence': confidence,
                'cause': f'Water is too alkaline (pH: {ph_value}) - above safe range'
            }
        
        return None  # pH is in normal range (6.0-9.0)

    def detect_anomalies(self, tds: Optional[float] = None, turbidity: Optional[float] = None, leak: Optional[bool] = None, ph_value: Optional[float] = None) -> Dict:
        """
        Detect anomalies using both rule-based and ML-based approaches.
        Combines results from both methods for more robust detection.
        
        Returns:
            Dict: A dictionary containing anomaly detection results with the following structure:
                {
                    'anomaly_detected': bool,
                    'most_probable_cause': str,
                    'confidence': float,
                    'conclusion': str,
                    'details': List[Dict]
                }
        """
        # Log input values for debugging
        logger.info(f"Detecting anomalies - TDS: {tds}, Turbidity: {turbidity}, Leak: {leak}")
        
        # Check available sensors
        available_sensors = []
        missing_sensors = []
        
        if tds is not None:
            available_sensors.append('TDS')
        else:
            missing_sensors.append('TDS')
            
        if turbidity is not None:
            available_sensors.append('turbidity')
        else:
            missing_sensors.append('turbidity')
            
        if leak is not None:
            available_sensors.append('leak')
        else:
            missing_sensors.append('leak')
        
        if ph_value is not None:
            available_sensors.append('pH')
        else:
            missing_sensors.append('pH')
        
        # Default response structure
        default_response = {
            'anomaly_detected': False,
            'most_probable_cause': 'No anomalies detected',
            'confidence': 0.0,
            'conclusion': 'No anomalies detected',
            'details': []
        }
        
        try:
            # If no sensors available, return appropriate response
            if not available_sensors:
                return {
                    'anomaly_detected': False,
                    'most_probable_cause': 'No sensor data available for anomaly detection',
                    'confidence': 0.0,
                    'conclusion': 'Unable to perform anomaly detection - all sensors unavailable',
                    'details': [{
                        'sensor': 'system',
                        'value': None,
                        'anomaly_type': 'sensor_unavailable',
                        'confidence': 1.0,
                        'cause': 'All sensors (TDS, turbidity, leak) are unavailable'
                    }]
                }
            
            # Validate input values for available sensors
            for sensor_name, value in [('TDS', tds), ('turbidity', turbidity), ('leak', leak), ('pH', ph_value)]:
                if value is not None and not isinstance(value, (int, float)):
                    logger.error(f"Invalid input type for {sensor_name}: {type(value)}")
                    return {
                        'anomaly_detected': True,
                        'most_probable_cause': f'Invalid {sensor_name} sensor reading',
                        'confidence': 1.0,
                        'conclusion': f'{sensor_name} sensor error detected',
                        'details': [{
                            'sensor': sensor_name.lower(),
                            'value': 'invalid',
                            'anomaly_type': 'sensor_error',
                            'confidence': 1.0,
                            'cause': f'Invalid {sensor_name} input value received'
                        }]
                    }

            # Get ML-based detection (only if we have enough sensors)
            ml_result = {'anomaly_detected': False, 'confidence': 0.0, 'details': []}
            if len(available_sensors) >= 2:
                try:
                    # Use conservative defaults for missing sensors in ML detection
                    tds_val = tds if tds is not None else 200.0
                    turbidity_val = turbidity if turbidity is not None else 2.0
                    leak_val = leak if leak is not None else False
                    
                    ml_result = self.detect_anomalies_ml(tds_val, turbidity_val, leak_val)
                    logger.info(f"ML Detection Result: {ml_result}")
                except Exception as e:
                    logger.error(f"ML detection failed: {e}")
                    ml_result = {'anomaly_detected': False, 'confidence': 0.0, 'details': []}
            else:
                logger.info("Skipping ML detection - insufficient sensor data")
            
            # Get rule-based detection (adapt for missing sensors)
            rule_result = self._detect_anomalies_rule_based_adaptive(tds, turbidity, leak, ph_value, available_sensors)
            logger.info(f"Rule-based Detection Result: {rule_result}")
            
            # Safely combine results
            combined_anomaly = ml_result.get('anomaly_detected', False) or rule_result.get('anomaly_detected', False)
            
            # Calculate combined confidence
            ml_confidence = float(ml_result.get('confidence', 0))
            rule_confidence = float(rule_result.get('confidence', 0))
            combined_confidence = max(ml_confidence, rule_confidence)
            
            # Adjust confidence based on missing sensors
            missing_sensor_penalty = len(missing_sensors) * 0.15  # Reduce confidence for missing sensors
            combined_confidence = max(0.1, combined_confidence - missing_sensor_penalty)
            
            # Initialize causes list
            causes = []
            
            # Add ML result cause if anomaly was detected
            if ml_result.get('anomaly_detected', False):
                ml_cause = ml_result.get('cause', 'ML model detected potential issue')
                causes.append(ml_cause)
            
            # Add rule-based causes
            if rule_result.get('anomaly_detected', False):
                rule_cause = rule_result.get('most_probable_cause', '')
                if rule_cause:
                    causes.append(rule_cause)
            
            # Combine details
            details = []
            if 'details' in rule_result and rule_result['details']:
                details.extend(rule_result['details'])
            if 'details' in ml_result and ml_result['details']:
                details.extend(ml_result['details'])
            
            # Add missing sensor information to details
            if missing_sensors and not combined_anomaly:
                details.append({
                    'sensor': 'system',
                    'value': None,
                    'anomaly_type': 'missing_sensors',
                    'confidence': len(missing_sensors) * 0.1,
                    'cause': f'Missing sensors: {", ".join(missing_sensors)}'
                })
            
            # If no details but we have an anomaly, add a generic detail
            if combined_anomaly and not details:
                details.append({
                    'sensor': 'combined_analysis',
                    'value': 1.0,
                    'anomaly_type': 'anomaly_detected',
                    'confidence': combined_confidence,
                    'cause': 'Anomaly detected by combined analysis'
                })
            
            # Create conclusion with missing sensor context
            conclusion = 'Anomaly detected' if combined_anomaly else 'No anomalies detected'
            if missing_sensors:
                if combined_anomaly:
                    conclusion += f' (analysis based on available sensors: {", ".join(available_sensors)})'
                else:
                    conclusion += f' (limited by missing sensors: {", ".join(missing_sensors)})'
            
            # Create final result with all required fields
            result = {
                'anomaly_detected': combined_anomaly,
                'most_probable_cause': '; '.join(causes) if causes else f'No anomalies detected{f" - missing sensors: {", ".join(missing_sensors)}" if missing_sensors else ""}',
                'confidence': combined_confidence,
                'conclusion': conclusion,
                'details': details or []  # Ensure details is always a list
            }
            
            logger.info(f"Combined Anomaly Detection Result: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error in detect_anomalies: {str(e)}", exc_info=True)
            # Return default response with error information
            default_response.update({
                'anomaly_detected': True,
                'most_probable_cause': f'Error during anomaly detection: {str(e)}',
                'confidence': 1.0,
                'conclusion': 'Error in anomaly detection',
                'details': [{
                    'sensor': 'error',
                    'value': 'error',
                    'anomaly_type': 'system_error',
                    'confidence': 1.0,
                    'cause': str(e)
                }]
            })
            return default_response
