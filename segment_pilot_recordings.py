"""
Segment long pilot recordings into 3-6 second chunks using silence detection
"""
import os
from pydub import AudioSegment
from pydub.silence import split_on_silence

def segment_audio(wav_path, min_duration_ms=3000, max_duration_ms=6000, 
                  silence_thresh=-40, min_silence_len=500):
    """
    Split audio file on silence and extract segments of appropriate duration
    
    Args:
        wav_path: Path to WAV file
        min_duration_ms: Minimum segment duration (default 3000ms = 3s)
        max_duration_ms: Maximum segment duration (default 6000ms = 6s)
        silence_thresh: Silence threshold in dBFS (default -40)
        min_silence_len: Minimum silence length in ms (default 500)
    
    Returns:
        List of (segment_audio, duration_s) tuples
    """
    print(f"\n📁 Processing: {os.path.basename(wav_path)}")
    
    # Load audio
    audio = AudioSegment.from_wav(wav_path)
    print(f"   Original duration: {len(audio)/1000:.2f}s")
    
    # Split on silence
    chunks = split_on_silence(
        audio,
        min_silence_len=min_silence_len,
        silence_thresh=silence_thresh,
        keep_silence=100  # Keep 100ms of silence at edges
    )
    
    print(f"   Found {len(chunks)} chunks after silence splitting")
    
    # Filter chunks by duration
    valid_segments = []
    for i, chunk in enumerate(chunks):
        duration_ms = len(chunk)
        duration_s = duration_ms / 1000
        
        if min_duration_ms <= duration_ms <= max_duration_ms:
            valid_segments.append((chunk, duration_s))
            print(f"   ✅ Chunk {i+1}: {duration_s:.2f}s (valid)")
        elif duration_ms < min_duration_ms:
            print(f"   ⏭️  Chunk {i+1}: {duration_s:.2f}s (too short, skipping)")
        else:
            # If chunk too long, try to extract first valid portion
            if duration_ms > max_duration_ms:
                truncated = chunk[:max_duration_ms]
                valid_segments.append((truncated, max_duration_ms/1000))
                print(f"   ✂️  Chunk {i+1}: {duration_s:.2f}s → truncated to {max_duration_ms/1000:.2f}s")
    
    print(f"   📊 Valid segments extracted: {len(valid_segments)}")
    return valid_segments

def process_all_recordings(input_dir="pilot_converted", output_dir="pilot_segmented"):
    """Process all WAV files and segment them"""
    os.makedirs(output_dir, exist_ok=True)
    
    wav_files = {
        "test_happy.wav": "happy",
        "test_sad.wav": "sad",
        "test_tts_output.wav": "unknown"  # Will need user to identify
    }
    
    all_segments = {}
    
    print("=" * 70)
    print("Segmenting Pilot Recordings (3-6 second chunks)")
    print("=" * 70)
    
    for filename, emotion_hint in wav_files.items():
        wav_path = os.path.join(input_dir, filename)
        if not os.path.exists(wav_path):
            print(f"\n❌ File not found: {wav_path}")
            continue
        
        segments = segment_audio(wav_path)
        
        # Save segments
        saved_files = []
        for i, (segment, duration) in enumerate(segments, 1):
            base_name = filename.replace('.wav', '')
            output_filename = f"{base_name}_segment_{i:02d}.wav"
            output_path = os.path.join(output_dir, output_filename)
            
            segment.export(output_path, format='wav')
            saved_files.append((output_filename, duration))
            print(f"   💾 {output_filename}: {duration:.2f}s")
        
        all_segments[emotion_hint] = saved_files
    
    print("\n" + "=" * 70)
    print("Segmentation Complete")
    print("=" * 70)
    
    for emotion, files in all_segments.items():
        print(f"\n{emotion.upper()} ({len(files)} segments):")
        for fname, dur in files:
            print(f"  • {fname} ({dur:.2f}s)")
    
    total_segments = sum(len(files) for files in all_segments.values())
    print(f"\n📊 Total valid segments: {total_segments}")
    print(f"📂 Segmented files saved to: {output_dir}/")
    
    return all_segments

if __name__ == "__main__":
    segments = process_all_recordings()
    
    print("\n" + "=" * 70)
    print("Next Steps:")
    print("=" * 70)
    print("1. Review segmented files and identify emotion/volume for each")
    print("2. Select best 8 segments for pilot validation:")
    print("   - 2 happy/normal")
    print("   - 2 sad/normal")
    print("   - 1 sad/whisper")
    print("   - 2 angry/normal")
    print("   - 1 angry/loud")
    print("3. Rename and move to correct data/{emotion}/{volume}/ folders")
    print("=" * 70)
