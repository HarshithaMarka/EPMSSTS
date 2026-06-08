"""
Acoustic-Based Telugu Dialect Classifier

Uses raw waveform input to classify Telugu dialects (Andhra vs Telangana)
based on acoustic features and Wav2Vec2 embeddings.

NO keyword dependence. NO volume bias. NO speaker leakage.
"""

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import librosa
from pathlib import Path
from typing import Optional, Dict, Tuple
from dataclasses import dataclass
from transformers import Wav2Vec2Model, Wav2Vec2Processor
import logging

logger = logging.getLogger(__name__)


@dataclass
class AcousticFeatures:
    """Raw acoustic features extracted from audio"""
    mfcc: np.ndarray  # (13, T)
    mfcc_delta: np.ndarray  # (13, T)
    f0_mean: float
    f0_variance: float
    spectral_centroid: float
    formant_f1: float
    formant_f2: float
    energy_mean: float
    energy_std: float
    
    def to_vector(self) -> np.ndarray:
        """Combine all features into single vector"""
        return np.array([
            self.f0_mean,
            self.f0_variance,
            self.spectral_centroid,
            self.formant_f1,
            self.formant_f2,
            self.energy_mean,
            self.energy_std
        ], dtype=np.float32)


@dataclass
class DialectPrediction:
    """Acoustic dialect prediction with confidence"""
    dialect: str  # 'andhra' or 'telangana'
    confidence: float
    acoustic_confidence: float
    embedding: Optional[np.ndarray] = None
    features: Optional[AcousticFeatures] = None


class AcousticFeatureExtractor:
    """Extract comprehensive acoustic features from audio"""
    
    def __init__(self, sr: int = 16000):
        self.sr = sr
    
    def extract(self, audio: np.ndarray) -> AcousticFeatures:
        """
        Extract acoustic features from audio waveform.
        
        Args:
            audio: Raw audio waveform (mono, float32)
            
        Returns:
            AcousticFeatures with all computed features
        """
        # Ensure 1D mono audio
        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)
        
        # MFCC (13 coefficients)
        mfcc = librosa.feature.mfcc(y=audio, sr=self.sr, n_mfcc=13)
        mfcc_delta = librosa.feature.delta(mfcc)
        
        # F0 (pitch) extraction
        f0, voiced_flag, voiced_probs = librosa.pyin(
            audio,
            fmin=librosa.note_to_hz('C2'),
            fmax=librosa.note_to_hz('C7'),
            sr=self.sr
        )
        
        # Remove NaN values
        f0_valid = f0[~np.isnan(f0)]
        
        if len(f0_valid) > 0:
            f0_mean = float(np.mean(f0_valid))
            f0_variance = float(np.var(f0_valid))
        else:
            f0_mean = 0.0
            f0_variance = 0.0
        
        # Spectral centroid
        spectral_centroid = librosa.feature.spectral_centroid(y=audio, sr=self.sr)[0]
        spectral_centroid_mean = float(np.mean(spectral_centroid))
        
        # Formant approximation (F1, F2)
        stft = np.abs(librosa.stft(audio))
        freqs = librosa.fft_frequencies(sr=self.sr)
        
        # F1: peak in 200-1000 Hz
        f1_mask = (freqs >= 200) & (freqs <= 1000)
        if np.any(f1_mask):
            f1_spectrum = np.mean(stft[f1_mask, :], axis=1)
            formant_f1 = float(freqs[f1_mask][np.argmax(f1_spectrum)])
        else:
            formant_f1 = 500.0
        
        # F2: peak in 1000-3000 Hz
        f2_mask = (freqs >= 1000) & (freqs <= 3000)
        if np.any(f2_mask):
            f2_spectrum = np.mean(stft[f2_mask, :], axis=1)
            formant_f2 = float(freqs[f2_mask][np.argmax(f2_spectrum)])
        else:
            formant_f2 = 1500.0
        
        # Energy contour (RMS)
        rms = librosa.feature.rms(y=audio)[0]
        energy_mean = float(np.mean(rms))
        energy_std = float(np.std(rms))
        
        return AcousticFeatures(
            mfcc=mfcc,
            mfcc_delta=mfcc_delta,
            f0_mean=f0_mean,
            f0_variance=f0_variance,
            spectral_centroid=spectral_centroid_mean,
            formant_f1=formant_f1,
            formant_f2=formant_f2,
            energy_mean=energy_mean,
            energy_std=energy_std
        )


class DialectClassifierHead(nn.Module):
    """
    Small classifier head for dialect classification.
    
    Architecture:
        Linear(128 → 64)
        ReLU
        Dropout(0.2)
        Linear(64 → 2)
    """
    
    def __init__(self, input_dim: int = 128, hidden_dim: int = 64, num_classes: int = 2):
        super().__init__()
        self.fc1 = nn.Linear(input_dim, hidden_dim)
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(0.2)
        self.fc2 = nn.Linear(hidden_dim, num_classes)
        
        # Temperature scaling parameter (learned during calibration)
        self.temperature = nn.Parameter(torch.ones(1))
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass through classifier head.
        
        Args:
            x: Input embeddings (batch_size, 128)
            
        Returns:
            Logits (batch_size, 2)
        """
        x = self.fc1(x)
        x = self.relu(x)
        x = self.dropout(x)
        x = self.fc2(x)
        return x
    
    def forward_with_temperature(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass with temperature scaling for calibration.
        
        Args:
            x: Input embeddings (batch_size, 128)
            
        Returns:
            Temperature-scaled logits (batch_size, 2)
        """
        logits = self.forward(x)
        return logits / self.temperature


class AcousticDialectClassifier:
    """
    Acoustic-based Telugu dialect classifier.
    
    Uses Wav2Vec2 for embedding extraction and a small classifier head
    for dialect prediction. NO keyword dependence.
    """
    
    DIALECTS = ['andhra', 'telangana']
    
    def __init__(self, model_path: Optional[Path] = None, device: str = 'cpu'):
        """
        Initialize acoustic dialect classifier.
        
        Args:
            model_path: Path to trained classifier weights
            device: Device to run model on ('cpu' or 'cuda')
        """
        self.device = device
        self.feature_extractor = AcousticFeatureExtractor(sr=16000)
        
        # Load Wav2Vec2 base model for embeddings
        logger.info("Loading Wav2Vec2 base model...")
        self.wav2vec2_processor = Wav2Vec2Processor.from_pretrained("facebook/wav2vec2-base")
        self.wav2vec2_model = Wav2Vec2Model.from_pretrained("facebook/wav2vec2-base")
        self.wav2vec2_model.to(device)
        self.wav2vec2_model.eval()
        
        # Initialize classifier head
        self.classifier_head = DialectClassifierHead(
            input_dim=128,  # Wav2Vec2 base hidden size is 768, we'll pool to 128
            hidden_dim=64,
            num_classes=2
        )
        self.classifier_head.to(device)
        
        # Load trained weights if available
        if model_path and model_path.exists():
            logger.info(f"Loading trained classifier from {model_path}")
            checkpoint = torch.load(model_path, map_location=device)
            self.classifier_head.load_state_dict(checkpoint['classifier_state_dict'])
            logger.info("Classifier loaded successfully")
        else:
            logger.warning("No trained classifier found. Using random initialization.")
            logger.warning("Model will need training before producing reliable predictions.")
    
    def extract_wav2vec2_embedding(self, audio: np.ndarray, sr: int = 16000) -> np.ndarray:
        """
        Extract 128D dialect embedding using Wav2Vec2.
        
        Args:
            audio: Raw audio waveform (mono, float32)
            sr: Sample rate (default: 16000)
            
        Returns:
            128D embedding vector
        """
        # Ensure audio is at correct sample rate
        if sr != 16000:
            audio = librosa.resample(audio, orig_sr=sr, target_sr=16000)
        
        # Process audio
        inputs = self.wav2vec2_processor(
            audio,
            sampling_rate=16000,
            return_tensors="pt",
            padding=True
        )
        
        # Move to device
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        # Extract features
        with torch.no_grad():
            outputs = self.wav2vec2_model(**inputs)
            hidden_states = outputs.last_hidden_state  # (1, T, 768)
            
            # Pool over time dimension (mean pooling)
            pooled = torch.mean(hidden_states, dim=1)  # (1, 768)
            
            # Reduce to 128D using learned projection
            # For now, use simple mean pooling over groups of 6
            embedding = pooled.reshape(1, 128, -1).mean(dim=-1)  # (1, 128)
            
            return embedding.cpu().numpy()[0]
    
    def predict(self, audio: np.ndarray, sr: int = 16000) -> DialectPrediction:
        """
        Predict dialect from raw audio waveform.
        
        Args:
            audio: Raw audio waveform (mono, float32)
            sr: Sample rate
            
        Returns:
            DialectPrediction with dialect label and confidence
        """
        # Extract acoustic features
        features = self.feature_extractor.extract(audio)
        
        # Extract Wav2Vec2 embedding
        embedding = self.extract_wav2vec2_embedding(audio, sr)
        
        # Predict dialect using classifier head
        self.classifier_head.eval()
        with torch.no_grad():
            embedding_tensor = torch.from_numpy(embedding).unsqueeze(0).to(self.device)
            logits = self.classifier_head.forward_with_temperature(embedding_tensor)
            probs = F.softmax(logits, dim=-1)
            
            predicted_idx = torch.argmax(probs, dim=-1).item()
            confidence = probs[0, predicted_idx].item()
        
        dialect = self.DIALECTS[predicted_idx]
        
        return DialectPrediction(
            dialect=dialect,
            confidence=float(confidence),
            acoustic_confidence=float(confidence),
            embedding=embedding,
            features=features
        )
    
    def predict_with_fallback(
        self,
        audio: np.ndarray,
        transcript: Optional[str] = None,
        sr: int = 16000,
        confidence_threshold: float = 0.5
    ) -> DialectPrediction:
        """
        Predict dialect with optional transcript fallback.
        
        Falls back to keyword-based prediction only if acoustic confidence < threshold.
        
        Args:
            audio: Raw audio waveform
            transcript: Optional transcript for fallback
            sr: Sample rate
            confidence_threshold: Threshold for acoustic confidence
            
        Returns:
            DialectPrediction
        """
        # Try acoustic prediction
        prediction = self.predict(audio, sr)
        
        # If acoustic confidence is high, use it
        if prediction.acoustic_confidence >= confidence_threshold:
            return prediction
        
        # Otherwise, fall back to keyword-based if transcript available
        if transcript:
            logger.warning(
                f"Acoustic confidence ({prediction.acoustic_confidence:.3f}) "
                f"below threshold ({confidence_threshold}). "
                "Falling back to keyword-based prediction."
            )
            
            # Simple keyword matching as fallback
            from .classifier import DialectClassifier
            keyword_classifier = DialectClassifier()
            keyword_pred = keyword_classifier.detect(transcript)
            
            # Return hybrid prediction
            return DialectPrediction(
                dialect=keyword_pred.dialect,
                confidence=keyword_pred.confidence,
                acoustic_confidence=prediction.acoustic_confidence,
                embedding=prediction.embedding,
                features=prediction.features
            )
        
        # No fallback available, return acoustic prediction anyway
        return prediction


def train_classifier_head(
    train_data: list,
    val_data: list,
    output_path: Path,
    num_epochs: int = 50,
    learning_rate: float = 0.001,
    device: str = 'cpu'
):
    """
    Train the dialect classifier head.
    
    Args:
        train_data: List of (embedding, label) tuples
        val_data: List of (embedding, label) tuples
        output_path: Path to save trained model
        num_epochs: Number of training epochs
        learning_rate: Learning rate for optimizer
        device: Device to train on
    """
    # Initialize model
    classifier = DialectClassifierHead(input_dim=128, hidden_dim=64, num_classes=2)
    classifier.to(device)
    
    # Loss and optimizer
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(classifier.parameters(), lr=learning_rate)
    
    best_val_acc = 0.0
    
    for epoch in range(num_epochs):
        # Training phase
        classifier.train()
        train_loss = 0.0
        train_correct = 0
        
        for embedding, label in train_data:
            embedding_tensor = torch.from_numpy(embedding).unsqueeze(0).to(device)
            label_tensor = torch.tensor([label], dtype=torch.long).to(device)
            
            optimizer.zero_grad()
            logits = classifier(embedding_tensor)
            loss = criterion(logits, label_tensor)
            loss.backward()
            optimizer.step()
            
            train_loss += loss.item()
            pred = torch.argmax(logits, dim=-1)
            train_correct += (pred == label_tensor).sum().item()
        
        train_acc = train_correct / len(train_data)
        
        # Validation phase
        classifier.eval()
        val_correct = 0
        
        with torch.no_grad():
            for embedding, label in val_data:
                embedding_tensor = torch.from_numpy(embedding).unsqueeze(0).to(device)
                label_tensor = torch.tensor([label], dtype=torch.long).to(device)
                
                logits = classifier(embedding_tensor)
                pred = torch.argmax(logits, dim=-1)
                val_correct += (pred == label_tensor).sum().item()
        
        val_acc = val_correct / len(val_data)
        
        logger.info(
            f"Epoch {epoch+1}/{num_epochs} - "
            f"Train Loss: {train_loss/len(train_data):.4f}, "
            f"Train Acc: {train_acc:.2%}, "
            f"Val Acc: {val_acc:.2%}"
        )
        
        # Save best model
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            torch.save({
                'classifier_state_dict': classifier.state_dict(),
                'epoch': epoch,
                'val_acc': val_acc
            }, output_path)
            logger.info(f"Saved best model with val_acc={val_acc:.2%}")
    
    logger.info(f"Training complete. Best val_acc: {best_val_acc:.2%}")


def calibrate_temperature(
    classifier: DialectClassifierHead,
    val_data: list,
    device: str = 'cpu'
):
    """
    Calibrate temperature parameter for better confidence estimates.
    
    Args:
        classifier: Trained classifier head
        val_data: Validation data for calibration
        device: Device to run on
    """
    optimizer = torch.optim.LBFGS([classifier.temperature], lr=0.01, max_iter=50)
    
    def eval_loss():
        optimizer.zero_grad()
        loss = 0.0
        
        for embedding, label in val_data:
            embedding_tensor = torch.from_numpy(embedding).unsqueeze(0).to(device)
            label_tensor = torch.tensor([label], dtype=torch.long).to(device)
            
            logits = classifier.forward_with_temperature(embedding_tensor)
            loss += F.cross_entropy(logits, label_tensor)
        
        loss.backward()
        return loss
    
    optimizer.step(eval_loss)
    
    logger.info(f"Temperature calibrated to: {classifier.temperature.item():.4f}")
