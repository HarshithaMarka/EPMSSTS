"""
Analyze audio metadata for pilot validation files
"""
import soundfile as sf
import numpy as np
import os

def analyze_audio(filepath):
    """Analyze audio file and return detailed metadata"""
    data, samplerate = sf.read(filepath)
    
    # Handle mono/stereo
    if len(data.shape) > 1:
        channels = data.shape[1]
        # Convert to mono for RMS calculation
        data_mono = np.mean(data, axis=1)
    else:
        channels = 1
        data_mono = data
    
    # Calculate duration
    duration = len(data_mono) / samplerate
    
    # Calculate RMS in dBFS
    rms = np.sqrt(np.mean(data_mono ** 2))
    if rms > 0:
        rms_dbfs = 20 * np.log10(rms)
    else:
        rms_dbfs = -np.inf
    
    # Calculate peak
    peak = np.max(np.abs(data_mono))
    if peak > 0:
        peak_dbfs = 20 * np.log10(peak)
    else:
        peak_dbfs = -np.inf
    
    # Estimate energy band based on RMS
    if rms_dbfs < -35:
        energy_band = "very_low (whisper)"
    elif rms_dbfs < -25:
        energy_band = "low"
    elif rms_dbfs < -15:
        energy_band = "normal"
    else:
        energy_band = "high (loud)"
    
    return {
        'filepath': filepath,
        'filename': os.path.basename(filepath),
        'samplerate': samplerate,
        'channels': channels,
        'duration': duration,
        'rms_dbfs': rms_dbfs,
        'peak_dbfs': peak_dbfs,
        'energy_band': energy_band,
        'filesize_kb': os.path.getsize(filepath) / 1024
    }

def main():
    print("=" * 80)
    print("STEP 1: Audio Metadata Analysis - Pilot Validation Files")
    print("=" * 80)
    
    files_to_analyze = [
        "data/sad/whisper/sad_whisper_pilot_01.wav",
        "data/angry/loud/angry_loud_pilot_01.wav",
        "data/sad/normal/sad_normal_pilot_01.wav",
        "data/happy/normal/happy_normal_pilot_01.wav"
    ]
    
    results = []
    for filepath in files_to_analyze:
        if os.path.exists(filepath):
            info = analyze_audio(filepath)
            results.append(info)
        else:
            print(f"\n❌ File not found: {filepath}")
    
    # Print results
    print("\n" + "─" * 80)
    print("📊 CRITICAL PILOT FILES - METADATA REPORT")
    print("─" * 80)
    
    for info in results:
        print(f"\n📁 {info['filename']}")
        print(f"   Folder: {os.path.dirname(info['filepath'])}")
        print(f"   File Size: {info['filesize_kb']:.1f} KB")
        print(f"   Duration: {info['duration']:.2f} seconds")
        print(f"   Sample Rate: {info['samplerate']} Hz {'✅' if info['samplerate'] == 16000 else '⚠️ NOT 16kHz'}")
        print(f"   Channels: {info['channels']} {'✅ (mono)' if info['channels'] == 1 else '⚠️ (stereo)'}")
        print(f"   RMS Level: {info['rms_dbfs']:.2f} dBFS")
        print(f"   Peak Level: {info['peak_dbfs']:.2f} dBFS")
        print(f"   Energy Band: {info['energy_band']}")
    
    # Validation checks
    print("\n" + "═" * 80)
    print("✅ VALIDATION CHECKS")
    print("═" * 80)
    
    whisper_file = [r for r in results if 'whisper' in r['filename']][0] if any('whisper' in r['filename'] for r in results) else None
    loud_file = [r for r in results if 'loud' in r['filename']][0] if any('loud' in r['filename'] for r in results) else None
    
    if whisper_file:
        print(f"\n🔇 WHISPER file:")
        print(f"   File: {whisper_file['filename']}")
        print(f"   RMS: {whisper_file['rms_dbfs']:.2f} dBFS")
        print(f"   Energy Band: {whisper_file['energy_band']}")
        if whisper_file['rms_dbfs'] < -30:
            print(f"   ✅ PASS: Very quiet (expected for whisper)")
        else:
            print(f"   ⚠️  WARNING: Not quiet enough for whisper")
    
    if loud_file:
        print(f"\n📢 LOUD file:")
        print(f"   File: {loud_file['filename']}")
        print(f"   RMS: {loud_file['rms_dbfs']:.2f} dBFS")
        print(f"   Energy Band: {loud_file['energy_band']}")
        if loud_file['rms_dbfs'] > -15:
            print(f"   ✅ PASS: Very loud (expected for loud)")
        else:
            print(f"   ⚠️  WARNING: Not loud enough")
    
    print("\n" + "═" * 80)
    print("⏭️  NEXT: Run emotion classification pipeline")
    print("═" * 80)

if __name__ == "__main__":
    main()
