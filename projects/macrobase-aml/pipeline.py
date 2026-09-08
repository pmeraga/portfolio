"""
MacroBase-style Anomaly Detection Pipeline
Based on Bailis et al., SIGMOD 2017

This pipeline implements three independent stages:
1. Scoring: Unsupervised anomaly detection using IsolationForest
2. Classification: Threshold-based partitioning into Anomalous (A) and Normal (P) sets
3. Explanation: Finding predicates with high Support and Risk Ratio
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import LabelEncoder
from typing import Tuple, Dict, List, Optional
import warnings
warnings.filterwarnings('ignore')


class DataIngestion:
    """Handles data loading and stratified sampling with label separation."""
    
    def __init__(self, data_path: str, sample_fraction: float = 0.1, random_state: int = 42):
        """
        Args:
            data_path: Path to SAML-D dataset CSV file
            sample_fraction: Fraction of data to sample (0.1 = 10%). Set to 1.0 for full dataset
            random_state: Random seed for reproducibility
        """
        self.data_path = data_path
        self.sample_fraction = sample_fraction
        self.random_state = random_state
        self.ground_truth_labels = None
    
    def load_and_sample(self) -> pd.DataFrame:
        """
        Load dataset, perform stratified sampling, and separate ground-truth labels.
        
        Returns:
            DataFrame with typology and doubt columns removed
        """
        print(f"Loading data from {self.data_path}...")
        df = pd.read_csv(self.data_path)
        print(f"Original dataset size: {len(df):,} rows")
        
        # Map column names to standard format (handle both test and real SAML-D formats)
        column_mapping = {}
        
        # Map transaction date
        if 'transaction_date' not in df.columns:
            if 'Date' in df.columns and 'Time' in df.columns:
                # Combine Date and Time into transaction_date
                df['transaction_date'] = pd.to_datetime(df['Date'].astype(str) + ' ' + df['Time'].astype(str))
                column_mapping['transaction_date'] = 'transaction_date'
            elif 'Date' in df.columns:
                df['transaction_date'] = pd.to_datetime(df['Date'])
                column_mapping['transaction_date'] = 'transaction_date'
        
        # Map typology/laundering_type
        if 'typology' not in df.columns:
            if 'Laundering_type' in df.columns:
                df['typology'] = df['Laundering_type']
                column_mapping['typology'] = 'Laundering_type'
        
        # Map doubt/is_laundering
        if 'doubt' not in df.columns:
            if 'Is_laundering' in df.columns:
                df['doubt'] = df['Is_laundering']
                column_mapping['doubt'] = 'Is_laundering'
        
        # Map other common columns
        if 'account_id' not in df.columns:
            if 'Sender_account' in df.columns:
                df['account_id'] = df['Sender_account']
            elif 'Receiver_account' in df.columns:
                df['account_id'] = df['Receiver_account']
        
        if 'amount' not in df.columns and 'Amount' in df.columns:
            df['amount'] = df['Amount']
        
        if 'payment_method' not in df.columns and 'Payment_type' in df.columns:
            df['payment_method'] = df['Payment_type']
        
        if 'currency' not in df.columns and 'Payment_currency' in df.columns:
            df['currency'] = df['Payment_currency']
        
        if 'receiver_country' not in df.columns and 'Receiver_bank_location' in df.columns:
            df['receiver_country'] = df['Receiver_bank_location']
        
        if 'sender_country' not in df.columns and 'Sender_bank_location' in df.columns:
            df['sender_country'] = df['Sender_bank_location']
        
        # Check for required columns after mapping
        required_cols = ['typology', 'doubt', 'transaction_date']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns after mapping: {missing_cols}. Available columns: {list(df.columns)}")
        
        # Store ground-truth labels BEFORE sampling
        self.ground_truth_labels = df[['typology', 'doubt']].copy()
        
        # Perform stratified sampling if sample_fraction < 1.0
        if self.sample_fraction < 1.0:
            print(f"Performing stratified sampling ({self.sample_fraction*100:.1f}%)...")
            df_sampled = df.groupby('typology', group_keys=False).apply(
                lambda x: x.sample(frac=self.sample_fraction, random_state=self.random_state)
            )
            # Update ground truth labels to match sampled data
            self.ground_truth_labels = self.ground_truth_labels.loc[df_sampled.index]
            df = df_sampled.reset_index(drop=True)
            self.ground_truth_labels = self.ground_truth_labels.reset_index(drop=True)
            print(f"Sampled dataset size: {len(df):,} rows")
        else:
            print("Using full dataset...")
        
        # CRITICAL: Drop ground-truth labels immediately to prevent data leakage
        # Only drop columns that exist
        cols_to_drop = [col for col in ['typology', 'doubt'] if col in df.columns]
        if cols_to_drop:
            df = df.drop(columns=cols_to_drop)
        
        return df
    
    def get_ground_truth_labels(self) -> pd.DataFrame:
        """Retrieve the stored ground-truth labels for evaluation."""
        if self.ground_truth_labels is None:
            raise ValueError("Labels not available. Call load_and_sample() first.")
        return self.ground_truth_labels.copy()


class FeatureEngineering:
    """Handles feature engineering: temporal, continuous, and categorical."""
    
    def __init__(self):
        self.label_encoders = {}
        self.categorical_cols = []
        self.raw_categorical_cols = None  # Store raw values for explanation stage
    
    def engineer_features(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Engineer features from raw data.
        
        Args:
            df: Input DataFrame
            
        Returns:
            Tuple of (engineered_features_df, raw_categorical_df)
            - engineered_features_df: Features for model training
            - raw_categorical_df: Raw categorical values for explanation stage
        """
        df = df.copy()
        
        # ========== TEMPORAL FEATURES ==========
        print("Engineering temporal features...")
        df['transaction_date'] = pd.to_datetime(df['transaction_date'])
        df['year'] = df['transaction_date'].dt.year
        df['month'] = df['transaction_date'].dt.month
        df['day_of_week'] = df['transaction_date'].dt.dayofweek
        df['day_of_month'] = df['transaction_date'].dt.day
        df['hour'] = df['transaction_date'].dt.hour
        
        # Rolling transaction frequencies per account (if account_id exists)
        # Using a simpler approach: count total transactions per account (more efficient)
        if 'account_id' in df.columns:
            # Count total transactions per account (simpler proxy for activity)
            account_counts = df.groupby('account_id').size()
            df['total_transactions_per_account'] = df['account_id'].map(account_counts)
            
            # For rolling windows, use a simplified version: transactions in same month
            df['year_month'] = df['transaction_date'].dt.to_period('M')
            monthly_counts = df.groupby(['account_id', 'year_month']).size()
            df['transactions_per_account_this_month'] = df.set_index(['account_id', 'year_month']).index.map(monthly_counts).fillna(1)
            df = df.drop(columns=['year_month'])
            
            # Set default rolling window features (can be enhanced later for production)
            df['transactions_per_account_7d'] = df['transactions_per_account_this_month'] / 4  # Approximate
            df['transactions_per_account_30d'] = df['transactions_per_account_this_month']
        
        # ========== CONTINUOUS FEATURES ==========
        print("Engineering continuous features...")
        if 'amount' in df.columns:
            # Log10 transformation to handle massive variance
            df['log_amount'] = np.log10(df['amount'] + 1)
        else:
            # Try common alternative column names
            amount_cols = [col for col in df.columns if 'amount' in col.lower() or 'value' in col.lower()]
            if amount_cols:
                df['log_amount'] = np.log10(df[amount_cols[0]] + 1)
            else:
                print("Warning: No amount column found. Skipping log_amount feature.")
        
        # ========== CATEGORICAL FEATURES ==========
        print("Engineering categorical features...")
        # Identify categorical columns (common in AML datasets)
        potential_categorical = ['payment_method', 'currency', 'receiver_country', 
                                'sender_country', 'transaction_type', 'channel']
        self.categorical_cols = [col for col in potential_categorical if col in df.columns]
        
        # Store raw categorical values for explanation stage
        raw_categorical_df = df[self.categorical_cols].copy() if self.categorical_cols else pd.DataFrame()
        
        # Encode categorical features for model
        for col in self.categorical_cols:
            le = LabelEncoder()
            df[f'{col}_encoded'] = le.fit_transform(df[col].astype(str))
            self.label_encoders[col] = le
        
        # Select final feature columns for model
        feature_cols = []
        feature_cols.extend(['year', 'month', 'day_of_week', 'day_of_month', 'hour'])
        if 'log_amount' in df.columns:
            feature_cols.append('log_amount')
        if 'transactions_per_account_7d' in df.columns:
            feature_cols.extend(['transactions_per_account_7d', 'transactions_per_account_30d'])
        feature_cols.extend([f'{col}_encoded' for col in self.categorical_cols])
        
        # Remove any columns that don't exist
        feature_cols = [col for col in feature_cols if col in df.columns]
        
        engineered_df = df[feature_cols].copy()
        
        print(f"Created {len(feature_cols)} engineered features")
        print(f"Feature columns: {feature_cols}")
        
        return engineered_df, raw_categorical_df


class ScoringStage:
    """Unsupervised anomaly scoring using IsolationForest."""
    
    def __init__(self, contamination: float = 0.1, random_state: int = 42, n_estimators: int = 100):
        """
        Args:
            contamination: Expected proportion of anomalies (used for calibration)
            random_state: Random seed
            n_estimators: Number of trees in IsolationForest
        """
        self.model = IsolationForest(
            contamination=contamination,
            random_state=random_state,
            n_estimators=n_estimators,
            n_jobs=-1  # Use all CPU cores
        )
        self.is_fitted = False
    
    def fit_and_score(self, X: pd.DataFrame) -> np.ndarray:
        """
        Fit IsolationForest and generate anomaly scores.
        
        Args:
            X: Feature matrix
            
        Returns:
            Array of anomaly scores (lower = more anomalous)
        """
        print("Fitting IsolationForest...")
        self.model.fit(X)
        self.is_fitted = True
        
        print("Generating anomaly scores...")
        # IsolationForest returns -1 for anomalies, 1 for normal
        # We convert to scores where lower = more anomalous
        scores = self.model.score_samples(X)
        # Negate so that higher scores = more anomalous (for percentile calculation)
        anomaly_scores = -scores
        
        print(f"Score range: [{anomaly_scores.min():.4f}, {anomaly_scores.max():.4f}]")
        
        return anomaly_scores


class ClassificationStage:
    """Threshold-based classification into Anomalous (A) and Normal (P) sets."""
    
    def __init__(self, percentile_thresholds: List[float] = None):
        """
        Args:
            percentile_thresholds: List of percentile cutoffs to test (e.g., [0.05, 0.1, 0.5])
        """
        if percentile_thresholds is None:
            # Default thresholds: top 0.05%, 0.1%, 0.5%, 1%
            self.percentile_thresholds = [99.95, 99.9, 99.5, 99.0]
        else:
            self.percentile_thresholds = sorted(percentile_thresholds, reverse=True)
    
    def classify(self, scores: np.ndarray, threshold_percentile: float) -> Tuple[np.ndarray, np.ndarray]:
        """
        Partition data into Anomalous (A) and Normal (P) sets based on threshold.
        
        Args:
            scores: Anomaly scores
            threshold_percentile: Percentile threshold (e.g., 99.9 for top 0.1%)
            
        Returns:
            Tuple of (anomalous_indices, normal_indices)
        """
        threshold_value = np.percentile(scores, threshold_percentile)
        anomalous_mask = scores >= threshold_value
        normal_mask = ~anomalous_mask
        
        anomalous_indices = np.where(anomalous_mask)[0]
        normal_indices = np.where(normal_mask)[0]
        
        return anomalous_indices, normal_indices
    
    def test_thresholds(self, scores: np.ndarray) -> Dict[float, Tuple[np.ndarray, np.ndarray]]:
        """
        Test multiple thresholds and return partitions for each.
        
        Args:
            scores: Anomaly scores
            
        Returns:
            Dictionary mapping percentile -> (anomalous_indices, normal_indices)
        """
        results = {}
        for threshold in self.percentile_thresholds:
            anomalous_idx, normal_idx = self.classify(scores, threshold)
            results[threshold] = (anomalous_idx, normal_idx)
            print(f"Threshold {threshold}%: {len(anomalous_idx):,} anomalous, {len(normal_idx):,} normal")
        
        return results


class ExplanationStage:
    """Find explanatory predicates with high Support and Risk Ratio."""
    
    def __init__(self, min_support: float = 0.01, min_risk_ratio: float = 2.0):
        """
        Args:
            min_support: Minimum support threshold (fraction of A that must have predicate)
            min_risk_ratio: Minimum risk ratio threshold
        """
        self.min_support = min_support
        self.min_risk_ratio = min_risk_ratio
    
    def calculate_support(self, predicate_mask: np.ndarray, A_size: int) -> float:
        """Calculate support: frequency of predicate in Anomalous set."""
        return np.sum(predicate_mask) / A_size if A_size > 0 else 0.0
    
    def calculate_risk_ratio(self, predicate_mask_A: np.ndarray, predicate_mask_P: np.ndarray, 
                           A_size: int, P_size: int) -> float:
        """
        Calculate risk ratio: (predicate_freq_in_A) / (predicate_freq_in_P).
        
        Returns 0 if predicate never appears in P (to avoid division by zero).
        """
        support_A = np.sum(predicate_mask_A) / A_size if A_size > 0 else 0.0
        support_P = np.sum(predicate_mask_P) / P_size if P_size > 0 else 0.0
        
        if support_P == 0:
            return float('inf') if support_A > 0 else 0.0
        
        return support_A / support_P
    
    def find_predicates(self, raw_categorical_df: pd.DataFrame, 
                       anomalous_indices: np.ndarray, 
                       normal_indices: np.ndarray) -> pd.DataFrame:
        """
        Find predicates (combinations of categorical attributes) that explain anomalies.
        
        Args:
            raw_categorical_df: DataFrame with raw categorical values
            anomalous_indices: Indices of anomalous records
            normal_indices: Indices of normal records
            
        Returns:
            DataFrame with columns: predicate, support, risk_ratio, count_in_A, count_in_P
        """
        print("Finding explanatory predicates...")
        
        if raw_categorical_df.empty:
            print("Warning: No categorical columns available for explanation.")
            return pd.DataFrame()
        
        A_size = len(anomalous_indices)
        P_size = len(normal_indices)
        
        A_df = raw_categorical_df.iloc[anomalous_indices].copy()
        P_df = raw_categorical_df.iloc[normal_indices].copy()
        
        results = []
        
        # Test single-attribute predicates
        for col in raw_categorical_df.columns:
            for value in A_df[col].unique():
                predicate = f"{col}={value}"
                
                predicate_mask_A = (A_df[col] == value).values
                predicate_mask_P = (P_df[col] == value).values
                
                support = self.calculate_support(predicate_mask_A, A_size)
                risk_ratio = self.calculate_risk_ratio(predicate_mask_A, predicate_mask_P, A_size, P_size)
                
                if support >= self.min_support and risk_ratio >= self.min_risk_ratio:
                    results.append({
                        'predicate': predicate,
                        'support': support,
                        'risk_ratio': risk_ratio,
                        'count_in_A': np.sum(predicate_mask_A),
                        'count_in_P': np.sum(predicate_mask_P),
                        'predicate_type': 'single'
                    })
        
        # Test two-attribute predicates (combinations)
        if len(raw_categorical_df.columns) >= 2:
            for i, col1 in enumerate(raw_categorical_df.columns):
                for col2 in raw_categorical_df.columns[i+1:]:
                    # Get frequent combinations in A
                    combo_counts = A_df.groupby([col1, col2]).size()
                    combo_counts = combo_counts[combo_counts >= (A_size * self.min_support)]
                    
                    for (val1, val2), count_A in combo_counts.items():
                        predicate = f"{col1}={val1} & {col2}={val2}"
                        
                        predicate_mask_A = ((A_df[col1] == val1) & (A_df[col2] == val2)).values
                        predicate_mask_P = ((P_df[col1] == val1) & (P_df[col2] == val2)).values
                        
                        support = self.calculate_support(predicate_mask_A, A_size)
                        risk_ratio = self.calculate_risk_ratio(predicate_mask_A, predicate_mask_P, A_size, P_size)
                        
                        if support >= self.min_support and risk_ratio >= self.min_risk_ratio:
                            results.append({
                                'predicate': predicate,
                                'support': support,
                                'risk_ratio': risk_ratio,
                                'count_in_A': np.sum(predicate_mask_A),
                                'count_in_P': np.sum(predicate_mask_P),
                                'predicate_type': 'pair'
                            })
        
        if not results:
            print("No predicates found meeting the thresholds.")
            return pd.DataFrame()
        
        results_df = pd.DataFrame(results)
        results_df = results_df.sort_values('risk_ratio', ascending=False)
        
        print(f"Found {len(results_df)} explanatory predicates")
        
        return results_df


class EvaluationStage:
    """Semi-supervised evaluation using ground-truth labels."""
    
    def evaluate(self, anomalous_indices: np.ndarray, normal_indices: np.ndarray,
                ground_truth_labels: pd.DataFrame) -> Dict[str, float]:
        """
        Calculate recovery rate (recall) and precision proxy.
        
        Args:
            anomalous_indices: Indices classified as anomalous
            normal_indices: Indices classified as normal
            ground_truth_labels: DataFrame with 'typology' and 'doubt' columns
            
        Returns:
            Dictionary with metrics
        """
        # Consider a transaction suspicious if typology is not null/normal or doubt is True/1
        # Adjust based on actual label encoding in your dataset
        suspicious_mask = pd.Series(False, index=ground_truth_labels.index)
        
        if 'typology' in ground_truth_labels.columns:
            # Assuming non-null or non-"normal" typology indicates suspicious
            typology_col = ground_truth_labels['typology']
            if typology_col.dtype == 'object':
                # Check for non-null and non-"normal" values
                suspicious_mask |= (typology_col.notna()) & (typology_col.astype(str).str.lower() != 'normal')
            else:
                # For numeric typology, assume non-zero or non-null indicates suspicious
                suspicious_mask |= (typology_col.notna()) & (typology_col != 0)
        
        if 'doubt' in ground_truth_labels.columns:
            # Assuming 1/True/"1"/"true" indicates suspicious
            doubt_col = ground_truth_labels['doubt']
            if doubt_col.dtype == 'object':
                suspicious_mask |= doubt_col.astype(str).str.lower().isin(['1', 'true', 'yes'])
            else:
                suspicious_mask |= (doubt_col == 1) | (doubt_col == True) | (doubt_col.astype(float) > 0)
        
        total_suspicious = suspicious_mask.sum()
        total_normal = (~suspicious_mask).sum()
        
        # Recovery rate (Recall): fraction of known suspicious in A
        suspicious_in_A = suspicious_mask.iloc[anomalous_indices].sum()
        recovery_rate = suspicious_in_A / total_suspicious if total_suspicious > 0 else 0.0
        
        # Precision proxy: fraction of A that are labeled suspicious
        precision_proxy = suspicious_in_A / len(anomalous_indices) if len(anomalous_indices) > 0 else 0.0
        
        return {
            'recovery_rate': recovery_rate,
            'precision_proxy': precision_proxy,
            'suspicious_in_A': suspicious_in_A,
            'total_suspicious': total_suspicious,
            'anomalous_set_size': len(anomalous_indices),
            'normal_set_size': len(normal_indices)
        }
    
    def evaluate_all_thresholds(self, threshold_results: Dict[float, Tuple[np.ndarray, np.ndarray]],
                                ground_truth_labels: pd.DataFrame) -> pd.DataFrame:
        """
        Evaluate all tested thresholds and return comparison table.
        
        Args:
            threshold_results: Dictionary from ClassificationStage.test_thresholds()
            ground_truth_labels: Ground-truth labels
            
        Returns:
            DataFrame with evaluation metrics for each threshold
        """
        results = []
        
        for threshold, (anomalous_idx, normal_idx) in threshold_results.items():
            metrics = self.evaluate(anomalous_idx, normal_idx, ground_truth_labels)
            metrics['threshold_percentile'] = threshold
            results.append(metrics)
        
        results_df = pd.DataFrame(results)
        results_df = results_df.sort_values('threshold_percentile', ascending=False)
        
        return results_df


def print_top_alerts(anomalous_indices: np.ndarray, 
                    raw_data: pd.DataFrame,
                    explanations: pd.DataFrame,
                    scores: np.ndarray,
                    top_n: int = 50) -> None:
    """
    Print top N alerts with transactions, explanations, support, and risk ratio.
    
    Args:
        anomalous_indices: Indices of anomalous transactions
        raw_data: Original raw data (for displaying transaction details)
        explanations: DataFrame from ExplanationStage
        scores: Anomaly scores
        top_n: Number of top alerts to display
    """
    print(f"\n{'='*80}")
    print(f"TOP {top_n} ALERTS")
    print(f"{'='*80}\n")
    
    # Get top N anomalous transactions by score
    anomalous_scores = scores[anomalous_indices]
    top_indices_in_A = np.argsort(anomalous_scores)[::-1][:top_n]
    top_global_indices = anomalous_indices[top_indices_in_A]
    
    # Display transactions
    print("TRANSACTIONS:")
    print("-" * 80)
    for i, idx in enumerate(top_global_indices, 1):
        print(f"\nAlert #{i} (Global Index: {idx}, Score: {scores[idx]:.4f})")
        print(f"  {raw_data.iloc[idx].to_dict()}")
    
    # Display top explanations
    if not explanations.empty:
        print(f"\n\nTOP EXPLANATORY PREDICATES:")
        print("-" * 80)
        top_explanations = explanations.head(20)
        for i, row in top_explanations.iterrows():
            print(f"\nPredicate: {row['predicate']}")
            print(f"  Support: {row['support']:.4f} ({row['count_in_A']} occurrences in A)")
            print(f"  Risk Ratio: {row['risk_ratio']:.2f}")
            print(f"  Count in Normal set: {row['count_in_P']}")
    else:
        print("\nNo explanatory predicates found.")


def run_pipeline(data_path: str, 
                sample_fraction: float = 0.1,
                percentile_thresholds: List[float] = None,
                min_support: float = 0.01,
                min_risk_ratio: float = 2.0,
                random_state: int = 42) -> Dict:
    """
    Run the complete MacroBase pipeline.
    
    Args:
        data_path: Path to SAML-D dataset
        sample_fraction: Fraction to sample (1.0 for full dataset)
        percentile_thresholds: List of percentile thresholds to test
        min_support: Minimum support for explanations
        min_risk_ratio: Minimum risk ratio for explanations
        random_state: Random seed
        
    Returns:
        Dictionary containing all pipeline results
    """
    print("="*80)
    print("MACROBASE ANOMALY DETECTION PIPELINE")
    print("="*80)
    
    # Stage 1: Data Ingestion
    print("\n[STAGE 1] DATA INGESTION")
    print("-" * 80)
    ingestion = DataIngestion(data_path, sample_fraction, random_state)
    raw_data = ingestion.load_and_sample()
    ground_truth = ingestion.get_ground_truth_labels()
    
    # Stage 2: Feature Engineering
    print("\n[STAGE 2] FEATURE ENGINEERING")
    print("-" * 80)
    feature_engineer = FeatureEngineering()
    engineered_features, raw_categorical = feature_engineer.engineer_features(raw_data)
    
    # Stage 3A: Scoring
    print("\n[STAGE 3A] SCORING (Unsupervised)")
    print("-" * 80)
    scoring = ScoringStage(random_state=random_state)
    anomaly_scores = scoring.fit_and_score(engineered_features)
    
    # Stage 3B: Classification
    print("\n[STAGE 3B] CLASSIFICATION")
    print("-" * 80)
    classification = ClassificationStage(percentile_thresholds)
    threshold_results = classification.test_thresholds(anomaly_scores)
    
    # Stage 3C: Explanation (for best threshold)
    print("\n[STAGE 3C] EXPLANATION")
    print("-" * 80)
    # Use the most restrictive threshold (highest percentile) for explanation
    best_threshold = max(threshold_results.keys())
    anomalous_idx, normal_idx = threshold_results[best_threshold]
    
    explanation = ExplanationStage(min_support, min_risk_ratio)
    explanations = explanation.find_predicates(raw_categorical, anomalous_idx, normal_idx)
    
    # Stage 4: Evaluation
    print("\n[STAGE 4] EVALUATION")
    print("-" * 80)
    evaluation = EvaluationStage()
    evaluation_results = evaluation.evaluate_all_thresholds(threshold_results, ground_truth)
    
    print("\nPrecision/Recall Trade-off Across Thresholds:")
    print("-" * 80)
    print(evaluation_results[['threshold_percentile', 'recovery_rate', 'precision_proxy', 
                              'anomalous_set_size', 'suspicious_in_A']].to_string(index=False))
    
    # Print top alerts
    print_top_alerts(anomalous_idx, raw_data, explanations, anomaly_scores, top_n=50)
    
    return {
        'raw_data': raw_data,
        'engineered_features': engineered_features,
        'anomaly_scores': anomaly_scores,
        'threshold_results': threshold_results,
        'explanations': explanations,
        'evaluation_results': evaluation_results,
        'ground_truth': ground_truth
    }


if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python pipeline.py <path_to_saml_d_dataset.csv> [sample_fraction]")
        print("Example: python pipeline.py data/saml_d.csv 0.1")
        sys.exit(1)
    
    data_path = sys.argv[1]
    sample_fraction = float(sys.argv[2]) if len(sys.argv) > 2 else 0.1
    
    results = run_pipeline(
        data_path=data_path,
        sample_fraction=sample_fraction,
        percentile_thresholds=[99.95, 99.9, 99.5, 99.0, 98.0],  # Top 0.05%, 0.1%, 0.5%, 1%, 2%
        min_support=0.01,
        min_risk_ratio=2.0,
        random_state=42
    )

