"""
Generate synthetic pilot samples for volume band testing
Creates whisper and loud variants from existing recordings
"""
import os
from pydub import AudioSegment

def create_whisper_sample(source_path, output_path, volume_reduction_db=-18):
    """
    Create whisper sample by reducing volume significantly
    
    Args:
        source_path: Path to source audio file
        output_path: Path to save whisper version
        volume_reduction_db: Volume reduction in dB (default -18dB for whisper)
    """
    print(f"\n🔇 Creating WHISPER sample")
    print(f"   Source: {source_path}")
    
    audio = AudioSegment.from_wav(source_path)
    
    # Get original RMS
    orig_rms = audio.dBFS
    print(f"   Original RMS: {orig_rms:.2f} dBFS")
    
    # Reduce volume
    whisper = audio + volume_reduction_db
    new_rms = whisper.dBFS
    print(f"   Whisper RMS: {new_rms:.2f} dBFS (reduced by {volume_reduction_db} dB)")
    
    # Export
    whisper.export(output_path, format='wav')
    print(f"   ✅ Saved: {output_path}")
    
    return whisper, new_rms

def create_loud_sample(source_path, output_path, volume_increase_db=12, pitch_shift_semitones=-2):
    """
    Create loud/angry sample by increasing volume and slightly lowering pitch
    
    Args:
        source_path: Path to source audio file
        output_path: Path to save loud version
        volume_increase_db: Volume increase in dB (default 12dB)
        pitch_shift_semitones: Pitch shift in semitones (negative = lower, for angry effect)
    """
    print(f"\n📢 Creating LOUD sample")
    print(f"   Source: {source_path}")
    
    audio = AudioSegment.from_wav(source_path)
    
    # Get original RMS
    orig_rms = audio.dBFS
    print(f"   Original RMS: {orig_rms:.2f} dBFS")
    
    # Lower pitch slightly for angry effect
    if pitch_shift_semitones != 0:
        # Change sample rate without resampling (pitch shift)
        new_sample_rate = int(audio.frame_rate * (2 ** (pitch_shift_semitones / 12.0)))
        pitched = audio._spawn(audio.raw_data, overrides={'frame_rate': new_sample_rate})
        # Resample back to 16kHz
        pitched = pitched.set_frame_rate(16000)
        print(f"   Pitch shifted: {pitch_shift_semitones} semitones")
    else:
        pitched = audio
    
    # Increase volume
    loud = pitched + volume_increase_db
    new_rms = loud.dBFS
    print(f"   Loud RMS: {new_rms:.2f} dBFS (increased by {volume_increase_db} dB)")
    
    # Apply light compression to prevent clipping
    if loud.max_dBFS > -1.0:
        # Normalize to -1 dBFS peak to prevent clipping
        headroom = loud.max_dBFS + 1.0
        loud = loud - headroom
        print(f"   Applied {headroom:.2f} dB compression to prevent clipping")
        new_rms = loud.dBFS
        print(f"   Final RMS: {new_rms:.2f} dBFS")
    
    # Export
    loud.export(output_path, format='wav')
    print(f"   ✅ Saved: {output_path}")
    
    return loud, new_rms

def main():
    print("=" * 70)
    print("Generating Synthetic Pilot Samples for Volume Band Testing")
    print("=" * 70)
    
    # Source files
    sad_normal_source = "data/sad/normal/sad_normal_pilot_01.wav"
    happy_normal_source = "data/happy/normal/happy_normal_pilot_01.wav"
    
    # Output paths
    sad_whisper_output = "data/sad/whisper/sad_whisper_pilot_01.wav"
    angry_loud_output = "data/angry/loud/angry_loud_pilot_01.wav"
    
    # Ensure output directories exist
    os.makedirs("data/sad/whisper", exist_ok=True)
    os.makedirs("data/angry/loud", exist_ok=True)
    
    # Generate whisper sample from sad recording
    if os.path.exists(sad_normal_source):
        whisper_audio, whisper_rms = create_whisper_sample(
            sad_normal_source, 
            sad_whisper_output,
            volume_reduction_db=-18  # Significant reduction for whisper
        )
        whisper_duration = len(whisper_audio) / 1000
    else:
        print(f"\n❌ Source not found: {sad_normal_source}")
        whisper_duration = 0
        whisper_rms = 0
    
    # Generate loud/angry sample from happy recording
    if os.path.exists(happy_normal_source):
        loud_audio, loud_rms = create_loud_sample(
            happy_normal_source,
            angry_loud_output,
            volume_increase_db=12,  # Significant increase for loud
            pitch_shift_semitones=-2  # Lower pitch for angry effect
        )
        loud_duration = len(loud_audio) / 1000
    else:
        print(f"\n❌ Source not found: {happy_normal_source}")
        loud_duration = 0
        loud_rms = 0
    
    print("\n" + "=" * 70)
    print("Generation Complete - Synthetic Pilot Samples Created")
    print("=" * 70)
    
    if whisper_duration > 0:
        print(f"\n✅ WHISPER sample:")
        print(f"   Path: {sad_whisper_output}")
        print(f"   Duration: {whisper_duration:.2f}s")
        print(f"   RMS: {whisper_rms:.2f} dBFS")
        print(f"   Expected band: very_low or low")
    
    if loud_duration > 0:
        print(f"\n✅ LOUD sample:")
        print(f"   Path: {angry_loud_output}")
        print(f"   Duration: {loud_duration:.2f}s")
        print(f"   RMS: {loud_rms:.2f} dBFS")
        print(f"   Expected band: high")
    
    print("\n" + "=" * 70)
    print("⏭️  Next: Run validation pipeline")
    print("   python emotion_assisted_prelabeling.py --project-root . --data-dir data --min-confidence 0.65")
    print("   python emotion_real_mic_validation.py")
    print("=" * 70)

if __name__ == "__main__":
    main()
