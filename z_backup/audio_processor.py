import io
from pydub import AudioSegment
from pydub.effects import normalize
import httpx

class AudioProcessor:
    def __init__(self):
        self.default_format = "mp3"
        self.sample_rate = 44100
    
    async def combine_voice_music(self, voice_data: bytes, music_url: str) -> bytes:
        """Combine voice recording with background music"""
        try:
            # Load voice audio
            voice_audio = AudioSegment.from_file(io.BytesIO(voice_data))
            
            # Download and load music
            async with httpx.AsyncClient() as client:
                music_response = await client.get(music_url)
                music_audio = AudioSegment.from_file(io.BytesIO(music_response.content))
            
            # Normalize audio levels
            voice_audio = normalize(voice_audio)
            music_audio = normalize(music_audio)
            
            # Adjust music volume (background level)
            music_audio = music_audio - 15  # Reduce by 15dB
            
            # Match durations - loop music if needed
            voice_duration = len(voice_audio)
            if len(music_audio) < voice_duration:
                # Loop music to match voice duration
                loops_needed = (voice_duration // len(music_audio)) + 1
                music_audio = music_audio * loops_needed
            
            # Trim music to match voice duration
            music_audio = music_audio[:voice_duration]
            
            # Overlay voice on music
            combined = music_audio.overlay(voice_audio)
            
            # Normalize final output
            combined = normalize(combined)
            
            # Export to bytes
            output_buffer = io.BytesIO()
            combined.export(output_buffer, format=self.default_format)
            return output_buffer.getvalue()
            
        except Exception as e:
            raise Exception(f"Audio processing error: {str(e)}")
    
    def process_voice_recording(self, voice_data: bytes) -> bytes:
        """Process and optimize voice recording"""
        try:
            audio = AudioSegment.from_file(io.BytesIO(voice_data))
            
            # Normalize volume
            audio = normalize(audio)
            
            # Remove silence from beginning and end
            audio = self._trim_silence(audio)
            
            # Apply gentle compression
            audio = self._apply_compression(audio)
            
            # Export processed audio
            output_buffer = io.BytesIO()
            audio.export(output_buffer, format="wav")
            return output_buffer.getvalue()
            
        except Exception as e:
            raise Exception(f"Voice processing error: {str(e)}")
    
    def _trim_silence(self, audio: AudioSegment, silence_thresh: int = -40) -> AudioSegment:
        """Remove silence from start and end"""
        # Find first non-silent chunk
        start_trim = 0
        for i in range(0, len(audio), 100):  # Check every 100ms
            chunk = audio[i:i+100]
            if chunk.dBFS > silence_thresh:
                start_trim = max(0, i - 100)  # Keep 100ms before speech
                break
        
        # Find last non-silent chunk
        end_trim = len(audio)
        for i in range(len(audio), 0, -100):
            chunk = audio[i-100:i]
            if chunk.dBFS > silence_thresh:
                end_trim = min(len(audio), i + 100)  # Keep 100ms after speech
                break
        
        return audio[start_trim:end_trim]
    
    def _apply_compression(self, audio: AudioSegment, threshold: float = -20.0, 
                         ratio: float = 4.0) -> AudioSegment:
        """Apply gentle compression to even out volume levels"""
        # Simple compression implementation
        # In production, you might want to use more sophisticated audio processing
        compressed = audio.compress_dynamic_range(
            threshold=threshold,
            ratio=ratio,
            attack=5.0,
            release=50.0
        )
        return compressed