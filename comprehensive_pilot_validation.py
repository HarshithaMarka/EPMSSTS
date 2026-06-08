"""
Comprehensive pilot validation analysis
Direct classification of all pilot files with detailed metrics
"""
import os
import soundfile as sf
import numpy as np
from epmssts.services.emotion.audio_emotion import AudioEmotionService

def calculate_energy_metrics(audio_data, sr):
    """Calculate detailed energy metrics"""
    # Calculate RMS in dBFS
    rms = np.sqrt(np.mean(audio_data ** 2))
    if rms > 0:
        rms_dbfs = 20 * np.log10(rms)
    else:
        rms_dbfs = -np.inf
    
    # Estimate energy band (simple heuristic)
    if rms_dbfs < -35:
        energy_band = "very_low"
    elif rms_dbfs < -25:
        energy_band = "low"
    elif rms_dbfs < -15:
        energy_band = "normal"
    else:
        energy_band = "high"
    
    return {
        'rms_dbfs': rms_dbfs,
        'energy_band': energy_band
    }

def classify_file(filepath, classifier):
    """Classify a single audio file and return detailed results"""
    try:
        # Load audio
        audio_data, sr = sf.read(filepath)
        # Ensure mono
        if len(audio_data.shape) > 1:
            audio_data = np.mean(audio_data, axis=1)

        # Ensure float32
        if audio_data.dtype != np.float32:
            audio_data = audio_data.astype(np.float32)
        
        
        # Calculate energy metrics
        energy_metrics = calculate_energy_metrics(audio_data, sr)
        
        # Get emotion prediction
        prediction = classifier.predict(audio_data, sr)
        
        return {
            'filepath': filepath,
            'filename': os.path.basename(filepath),
            'folder': os.path.dirname(filepath).replace(os.getcwd() + os.sep, ''),
            'predicted_emotion': prediction.emotion,
            'confidence': prediction.confidence,
            'rms_dbfs': energy_metrics['rms_dbfs'],
            'energy_band': energy_metrics['energy_band'],
            'duration': len(audio_data) / sr,
            'sample_rate': sr
        }
    except Exception as e:
        return {
            'filepath': filepath,
            'filename': os.path.basename(filepath),
            'error': str(e)
        }

def main():
    print("=" * 90)
    print("COMPREHENSIVE PILOT VALIDATION ANALYSIS")
    print("=" * 90)
    
    # Initialize emotion classifier
    print("\n🔧 Initializing emotion classifier...")
    classifier = AudioEmotionService()
    print("✅ Classifier initialized\n")
    
    # Define pilot files to analyze
    pilot_files = [
        "data/sad/whisper/sad_whisper_pilot_01.wav",
        "data/angry/loud/angry_loud_pilot_01.wav",
        "data/sad/normal/sad_normal_pilot_01.wav",
        "data/sad/normal/sad_normal_pilot_02.wav",
        "data/happy/normal/happy_normal_pilot_01.wav",
        "data/happy/normal/happy_normal_pilot_02.wav",
    ]
    
    print("📊 Analyzing Pilot Files...")
    print("=" * 90)
    
    results = []
    for filepath in pilot_files:
        if os.path.exists(filepath):
            print(f"\n🔍 Processing: {filepath}")
            result = classify_file(filepath, classifier)
            results.append(result)
            
            if 'error' not in result:
                print(f"   ✅ Predicted: {result['predicted_emotion']} (confidence: {result['confidence']:.3f})")
                print(f"   📊 RMS: {result['rms_dbfs']:.2f} dBFS")
                print(f"   📶 Energy Band: {result['energy_band']}")
            else:
                print(f"   ❌ Error: {result['error']}")
        else:
            print(f"\n❌ File not found: {filepath}")
    
    # Print comprehensive report
    print("\n" + "=" * 90)
    print("DETAILED VALIDATION REPORT")
    print("=" * 90)
    
    for result in results:
        if 'error' not in result:
            print(f"\n📁 {result['filename']}")
            print(f"   Location: {result['folder']}")
            print(f"   Predicted Emotion: {result['predicted_emotion']}")
            print(f"   Confidence Score: {result['confidence']:.4f}")
            print(f"   RMS Level: {result['rms_dbfs']:.2f} dBFS")
            print(f"   Energy Band: {result['energy_band']}")
            print(f"   Duration: {result['duration']:.2f}s")
            print(f"   Sample Rate: {result['sample_rate']} Hz")
    
    # Critical validation checks
    print("\n" + "=" * 90)
    print("CRITICAL VALIDATION CHECKS")
    print("=" * 90)
    
    # Check whisper file
    whisper_results = [r for r in results if 'whisper' in r.get('filename', '')]
    if whisper_results:
        whisper = whisper_results[0]
        print(f"\n🔇 WHISPER FILE: {whisper['filename']}")
        print(f"   Predicted: {whisper['predicted_emotion']} (confidence: {whisper['confidence']:.3f})")
        print(f"   RMS: {whisper['rms_dbfs']:.2f} dBFS")
        print(f"   Energy Band: {whisper['energy_band']}")
        
        # Validation
        if whisper['energy_band'] in ['very_low', 'low']:
            print(f"   ✅ PASS: Correctly assigned to {whisper['energy_band']} band")
        else:
            print(f"   ❌ FAIL: Should be very_low/low, but assigned to {whisper['energy_band']}")
        
        if whisper['predicted_emotion'] != 'happy':
            print(f"   ✅ PASS: Not misclassified as happy")
        else:
            print(f"   ⚠️  WARNING: Misclassified as happy")
    
    # Check loud file
    loud_results = [r for r in results if 'loud' in r.get('filename', '')]
    if loud_results:
        loud = loud_results[0]
        print(f"\n📢 LOUD FILE: {loud['filename']}")
        print(f"   Predicted: {loud['predicted_emotion']} (confidence: {loud['confidence']:.3f})")
        print(f"   RMS: {loud['rms_dbfs']:.2f} dBFS")
        print(f"   Energy Band: {loud['energy_band']}")
        
        # Validation
        if loud['energy_band'] == 'high':
            print(f"   ✅ PASS: Correctly assigned to high band")
        else:
            print(f"   ❌ FAIL: Should be high, but assigned to {loud['energy_band']}")
        
        if loud['predicted_emotion'] != 'neutral':
            print(f"   ✅ PASS: Not collapsed to neutral")
        else:
            print(f"   ⚠️  WARNING: Collapsed to neutral")
    
    # Check emotion predictions
    print(f"\n📊 EMOTION PREDICTION SUMMARY:")
    emotion_counts = {}
    for result in results:
        if 'predicted_emotion' in result:
            emotion = result['predicted_emotion']
            emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1
    
    for emotion, count in sorted(emotion_counts.items()):
        print(f"   {emotion}: {count} files")
    
    # Final verdict
    print("\n" + "=" * 90)
    print("FINAL VALIDATION VERDICT")
    print("=" * 90)
    
    passes = 0
    fails = 0
    
    # Check whisper
    if whisper_results:
        whisper = whisper_results[0]
        if whisper['energy_band'] in ['very_low', 'low']:
            passes += 1
            print("✅ Whisper volume band detection: PASS")
        else:
            fails += 1
            print("❌ Whisper volume band detection: FAIL")
    
    # Check loud
    if loud_results:
        loud = loud_results[0]
        if loud['energy_band'] == 'high':
            passes += 1
            print("✅ Loud volume band detection: PASS")
        else:
            fails += 1
            print("❌ Loud volume band detection: FAIL")
    
    # Overall verdict
    print(f"\n📊 Score: {passes}/{passes+fails} checks passed")
    
    if fails == 0:
        print("\n🎉 ✅ OVERALL VERDICT: PASS")
        print("   Volume band detection is working correctly")
    else:
        print("\n⚠️  ❌ OVERALL VERDICT: FAIL")
        print(f"   {fails} validation check(s) failed")
    
    print("\n" + "=" * 90)

if __name__ == "__main__":
    main()
