# ML Model Guide - Xero Report Code Mapping

> **Status: Planned / Not Yet Implemented**
>
> This document describes the *planned* ML integration architecture. No ML
> inference code currently exists in the pipeline. The system currently uses
> a declarative rule engine (`rule_engine.py` + `rules.py`) for keyword-based
> classification. This guide serves as a design specification for future work.

## Overview

This guide explains the planned Machine Learning (ML) components of the Xero Report Code Mapping system, including model architecture, training procedures, and integration with the existing rule-based system.

## Architecture Overview

### Hybrid Approach

The system uses a hybrid approach combining:
1. **Rule-based heuristics** (existing keyword matching)
2. **Machine Learning models** (new ML-based predictions)
3. **Integrity validation** (constraint enforcement)

### Model Architecture

```
Input Features → Feature Extractor → ML Model → Prediction + Confidence
                     ↓
              Rule-based Fallback ← Confidence Threshold
                     ↓
              Integrity Validator → Final Output
```

## Feature Engineering

### 1. Text Features

**TF-IDF (Term Frequency-Inverse Document Frequency)**
- Converts account names and descriptions to numerical vectors
- Captures important terms while reducing noise
- Handles variations in terminology

**N-gram Features**
- Unigrams: Individual words ("office", "rent", "expense")
- Bigrams: Two-word phrases ("office rent", "rent expense")
- Trigrams: Three-word phrases ("monthly office rent")

**Word Embeddings**
- Pre-trained accounting vocabulary embeddings
- Captures semantic relationships between terms
- Handles synonyms and related concepts

### 2. Categorical Features

**Account Type**
- One-hot encoded account types
- Includes canonical type mappings
- Handles type variations

**Tax Code**
- GST treatment codes
- Tax-exempt classifications
- Compliance requirements

**Industry Context**
- Industry-specific terminology
- Sector-specific account patterns
- Regulatory requirements

### 3. Contextual Features

**Previous Row Context**
- Account code patterns
- Sequential relationships
- Hierarchical structures

**Template Context**
- Template chart influence
- Standard account structures
- Industry-specific templates

## Model Types

### 1. Gradient Boosting (Primary)

**XGBoost/LightGBM**
- Fast inference speed
- Interpretable feature importance
- Handles mixed data types well
- Robust to outliers

**Advantages:**
- Quick training and prediction
- Easy to debug and understand
- Good performance with limited data
- Feature importance analysis

### 2. Neural Network (Secondary)

**BERT-tiny Fine-tuned**
- Highest accuracy potential
- Captures complex text patterns
- Handles context and relationships
- State-of-the-art NLP capabilities

**Advantages:**
- Superior text understanding
- Context-aware predictions
- Handles ambiguous cases well
- Continuous learning capability

### 3. Ensemble (Combined)

**Weighted Combination**
- Combines both model types
- Uses confidence scores for weighting
- Fallback mechanisms
- Robust error handling

## Training Pipeline

### 1. Data Preparation

**Source Data:**
- Resolution decisions from staff corrections
- Original predictions vs. final approved codes
- Balance anomaly corrections
- Manual overrides and exceptions

**Data Structure:**
```json
{
  "account_code": "200",
  "account_name": "Sales Revenue",
  "account_type": "Revenue",
  "description": "Main revenue stream",
  "tax_code": "GST",
  "industry": "Retail",
  "original_prediction": "REV.TRA.GOO",
  "final_code": "REV.TRA.SER",
  "confidence": 0.85,
  "correction_reason": "Service-based business"
}
```

### 2. Feature Extraction

**Text Processing:**
```python
def extract_text_features(account_name, description):
    # Combine text fields
    text = f"{account_name} {description}".lower()
    
    # TF-IDF features
    tfidf_features = tfidf_vectorizer.transform([text])
    
    # N-gram features
    ngram_features = ngram_vectorizer.transform([text])
    
    # Word embeddings
    embedding_features = word2vec_model.encode(text)
    
    return np.concatenate([tfidf_features, ngram_features, embedding_features])
```

**Categorical Processing:**
```python
def extract_categorical_features(account_type, tax_code, industry):
    # One-hot encoding
    type_features = type_encoder.transform([account_type])
    tax_features = tax_encoder.transform([tax_code])
    industry_features = industry_encoder.transform([industry])
    
    return np.concatenate([type_features, tax_features, industry_features])
```

### 3. Model Training

**Gradient Boosting:**
```python
def train_gradient_boosting(X, y):
    model = XGBClassifier(
        n_estimators=1000,
        max_depth=6,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42
    )
    
    # Stratified split by account type
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )
    
    # Early stopping
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        early_stopping_rounds=50,
        verbose=False
    )
    
    return model
```

**Neural Network:**
```python
def train_neural_network(X, y):
    model = BertForSequenceClassification.from_pretrained(
        'bert-base-uncased',
        num_labels=len(unique_codes)
    )
    
    # Fine-tuning
    trainer = Trainer(
        model=model,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        args=TrainingArguments(
            output_dir='./results',
            num_train_epochs=3,
            per_device_train_batch_size=16,
            per_device_eval_batch_size=64,
            warmup_steps=500,
            weight_decay=0.01,
            logging_dir='./logs',
        ),
    )
    
    trainer.train()
    return model
```

### 4. Model Evaluation

**Metrics:**
- **Top-1 Accuracy**: Exact match percentage
- **Top-3 Accuracy**: Correct code in top 3 suggestions
- **Per-Type Accuracy**: Breakdown by account type
- **Confusion Matrix**: Common error patterns

**Evaluation Code:**
```python
def evaluate_model(model, X_test, y_test):
    predictions = model.predict(X_test)
    probabilities = model.predict_proba(X_test)
    
    # Top-1 accuracy
    top1_accuracy = accuracy_score(y_test, predictions)
    
    # Top-3 accuracy
    top3_predictions = np.argsort(probabilities, axis=1)[:, -3:]
    top3_accuracy = np.mean([y_test[i] in top3_predictions[i] for i in range(len(y_test))])
    
    # Per-type accuracy
    type_accuracy = {}
    for account_type in unique_types:
        mask = X_test['account_type'] == account_type
        type_accuracy[account_type] = accuracy_score(
            y_test[mask], predictions[mask]
        )
    
    return {
        'top1_accuracy': top1_accuracy,
        'top3_accuracy': top3_accuracy,
        'type_accuracy': type_accuracy,
        'confusion_matrix': confusion_matrix(y_test, predictions)
    }
```

## Integration with Existing System

### 1. Hybrid Predictor

```python
def predict_reporting_code(account_row, confidence_threshold=0.75):
    """
    Hybrid prediction combining ML and rule-based approaches
    """
    # 1. Run ML model first
    ml_prediction, ml_confidence = ml_model.predict(account_row)
    
    # 2. Check confidence threshold
    if ml_confidence >= confidence_threshold:
        prediction = ml_prediction
        source = 'ML'
    else:
        # 3. Fall back to rule-based
        rule_prediction, rule_source = keyword_match(account_row)
        prediction = rule_prediction
        source = f'Rule-{rule_source}'
    
    # 4. Run integrity validation
    validation_result = validator.validate_account_entry(
        account_row['*Type'], prediction, account_row['*Name']
    )
    
    # 5. Handle validation failures
    if not validation_result['valid']:
        # Try alternative predictions
        alternative = get_alternative_prediction(account_row, prediction)
        if alternative:
            prediction = alternative
            source += '-Corrected'
        else:
            # Final fallback
            prediction = get_safe_fallback(account_row['*Type'])
            source += '-Fallback'
    
    return prediction, source, ml_confidence
```

### 2. Confidence Scoring

**ML Model Confidence:**
- Probability of predicted class
- Uncertainty quantification
- Calibration for reliable thresholds

**Rule-based Confidence:**
- Keyword match strength
- Type guard compliance
- Historical accuracy

**Combined Confidence:**
```python
def calculate_combined_confidence(ml_confidence, rule_confidence, source):
    if source.startswith('ML'):
        return ml_confidence
    elif source.startswith('Rule'):
        return rule_confidence * 0.8  # Slightly lower confidence for rules
    else:
        return min(ml_confidence, rule_confidence)
```

## Model Deployment

### 1. Model Versioning

**Version Control:**
- Semantic versioning (v1.0.0, v1.1.0, etc.)
- Model metadata and performance metrics
- Rollback capabilities
- A/B testing support

**Deployment Process:**
```python
def deploy_model(model_version):
    # 1. Validate model performance
    performance = evaluate_model_on_test_set(model_version)
    if performance['top1_accuracy'] < 0.85:
        raise ValueError("Model performance below threshold")
    
    # 2. Backup current model
    backup_current_model()
    
    # 3. Deploy new model
    copy_model_files(model_version)
    update_model_config(model_version)
    
    # 4. Verify deployment
    test_model_inference()
    
    # 5. Update monitoring
    update_model_metrics(model_version)
```

### 2. Model Monitoring

**Performance Metrics:**
- Prediction accuracy over time
- Confidence score distribution
- Error rate by account type
- User satisfaction scores

**Monitoring Dashboard:**
- Real-time performance metrics
- Model drift detection
- Alert system for performance degradation
- Automated retraining triggers

## Retraining Procedures

### 1. Data Collection

**Resolution History:**
- Staff corrections and overrides
- Balance anomaly resolutions
- Manual code assignments
- Quality assurance feedback

**Data Quality:**
- Remove duplicate entries
- Validate correction accuracy
- Handle conflicting decisions
- Ensure data freshness

### 2. Incremental Learning

**Online Learning:**
- Update model with new decisions
- Maintain model performance
- Handle concept drift
- Preserve historical knowledge

**Batch Retraining:**
- Full model retraining
- Performance validation
- A/B testing
- Gradual rollout

### 3. Model Validation

**Cross-Validation:**
- Time-based splits
- Account type stratification
- Industry-specific validation
- Robustness testing

**Business Validation:**
- Accounting team review
- Edge case testing
- Performance benchmarking
- User acceptance testing

## Performance Optimization

### 1. Inference Speed

**Model Optimization:**
- Quantization for faster inference
- Model pruning to reduce size
- Batch processing for multiple accounts
- Caching for repeated predictions

**System Optimization:**
- GPU acceleration for neural networks
- Memory-efficient data structures
- Parallel processing
- Load balancing

### 2. Accuracy Improvement

**Feature Engineering:**
- Domain-specific features
- Temporal features
- Hierarchical features
- Interaction features

**Model Architecture:**
- Ensemble methods
- Multi-task learning
- Transfer learning
- Active learning

## Troubleshooting

### 1. Common Issues

**Low Accuracy:**
- Insufficient training data
- Poor feature engineering
- Model overfitting
- Data quality issues

**Slow Inference:**
- Model complexity
- Feature extraction overhead
- System resource constraints
- Network latency

**Model Drift:**
- Changing business patterns
- New account types
- Industry evolution
- Regulatory changes

### 2. Debugging Tools

**Model Interpretability:**
- Feature importance analysis
- SHAP values for predictions
- Attention weights for neural networks
- Decision tree visualization

**Performance Analysis:**
- Confusion matrix analysis
- Error pattern identification
- Confidence score analysis
- User feedback correlation

## Future Enhancements

### 1. Advanced ML Techniques

**Deep Learning:**
- Transformer architectures
- Graph neural networks
- Multi-modal learning
- Few-shot learning

**Reinforcement Learning:**
- Interactive learning from user feedback
- Adaptive confidence thresholds
- Dynamic feature selection
- Continuous improvement

### 2. Integration Improvements

**Real-time Learning:**
- Online model updates
- Immediate feedback incorporation
- Dynamic threshold adjustment
- Personalized predictions

**Multi-language Support:**
- International account terminology
- Cross-cultural business patterns
- Regulatory compliance variations
- Localized model training

## Conclusion

The ML model system provides a powerful complement to the existing rule-based approach, offering improved accuracy and adaptability. The hybrid architecture ensures reliability while leveraging the strengths of both approaches. Regular monitoring, retraining, and validation ensure the system continues to provide value as business needs evolve.

For technical implementation details, refer to the source code and configuration files. For business logic questions, consult with the accounting team and review the integrity rules documentation.
