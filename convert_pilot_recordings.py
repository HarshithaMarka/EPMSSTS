"""
Convert pilot recording MP3 files to WAV format (16kHz mono)
"""
import os
from pydub import AudioSegment
from pydub.silence import detect_leading_silence

def trim_silence(audio, silence_thresh=-50):
    """Remove leading and trailing silence from audio"""
    trim_leading = detect_leading_silence(audio, silence_threshold=silence_thresh)
    trim_trailing = detect_leading_silence(audio.reverse(), silence_threshold=silence_thresh)
    return audio[trim_leading:len(audio)-trim_trailing]

def convert_mp3_to_wav(mp3_path, output_dir="pilot_converted"):
    """Convert MP3 to WAV 16kHz mono with silence trimming"""
    os.makedirs(output_dir, exist_ok=True)
    
    # Load MP3
    audio = AudioSegment.from_mp3(mp3_path)
    print(f"\n📁 {os.path.basename(mp3_path)}")
    print(f"   Original: {audio.frame_rate}Hz, {audio.channels}ch, {len(audio)/1000:.2f}s")
    
    # Convert to mono
    if audio.channels > 1:
        audio = audio.set_channels(1)
    
    # Resample to 16kHz
    audio = audio.set_frame_rate(16000)
    
    # Trim silence
    audio_trimmed = trim_silence(audio)
    duration = len(audio_trimmed) / 1000
    
    print(f"   Converted: 16000Hz, 1ch, {duration:.2f}s (after trimming)")
    
    # Check duration requirement (3-6 seconds)
    if duration < 3:
        print(f"   ⚠️  WARNING: Duration {duration:.2f}s < 3s minimum")
    elif duration > 6:
        print(f"   ⚠️  WARNING: Duration {duration:.2f}s > 6s maximum")
    else:
        print(f"   ✅ Duration valid (3-6s)")
    
    # Export as WAV
    output_filename = os.path.basename(mp3_path).replace('.mp3', '.wav')
    output_path = os.path.join(output_dir, output_filename)
    audio_trimmed.export(output_path, format='wav')
    
    print(f"   💾 Saved: {output_path}")
    return output_path, duration

if __name__ == "__main__":
    mp3_files = [
        "data/angry/normal/test_happy.mp3",
        "data/angry/normal/test_sad.mp3",
        "data/angry/normal/test_tts_output.mp3"
    ]
    
    print("=" * 60)
    print("Converting Pilot Recordings: MP3 → WAV (16kHz mono)")
    print("=" * 60)
    
    results = []
    for mp3_file in mp3_files:
        if os.path.exists(mp3_file):
            wav_path, duration = convert_mp3_to_wav(mp3_file)
            results.append((mp3_file, wav_path, duration))
        else:
            print(f"\n❌ File not found: {mp3_file}")
    
    print("\n" + "=" * 60)
    print("Conversion Summary")
    print("=" * 60)
    for mp3, wav, dur in results:
        print(f"✅ {os.path.basename(mp3)} → {wav} ({dur:.2f}s)")
    
    print(f"\n📂 Converted files saved to: pilot_converted/")
    print("\n⏭️  Next step: Map each file to emotion/volume and rename accordingly")
