import os
import asyncio
import io
import wave
from google import genai
from google.genai import types

class LyriaMusic:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise Exception("GEMINI_API_KEY not found in environment")
        
        self.client = genai.Client(
            api_key=self.api_key,
            http_options={'api_version': 'v1alpha'}
        )
    
    def build_music_config(self, tag: str):
        """Build smart config based on tag"""
        if tag == "meditation":
            return types.LiveMusicGenerationConfig(
                bpm=70,
                guidance=3.5,
                density=0.3,
                brightness=0.3,
                temperature=0.9,
                music_generation_mode=types.MusicGenerationMode.QUALITY
            )
        elif tag == "focus":
            return types.LiveMusicGenerationConfig(
                bpm=90,
                guidance=4.0,
                density=0.5,
                brightness=0.4,
                temperature=1.0,
                music_generation_mode=types.MusicGenerationMode.QUALITY
            )
        elif tag == "sleep":
            return types.LiveMusicGenerationConfig(
                bpm=60,
                guidance=3.0,
                density=0.2,
                brightness=0.2,
                temperature=0.8,
                music_generation_mode=types.MusicGenerationMode.QUALITY
            )
        elif tag == "energy":
            return types.LiveMusicGenerationConfig(
                bpm=120,
                guidance=4.2,
                density=0.7,
                brightness=0.7,
                temperature=1.2,
                music_generation_mode=types.MusicGenerationMode.DIVERSITY
            )
        else:
            # fallback
            return types.LiveMusicGenerationConfig(
                bpm=80,
                guidance=4.0,
                density=0.5,
                brightness=0.5,
                temperature=1.0,
                music_generation_mode=types.MusicGenerationMode.QUALITY
            )
    
    async def generate_music_with_config(self, prompt: str, tag: str, duration: int = 30) -> bytes:
        """Generate music with tag-based config"""
        try:
            audio_chunks = []
            
            async def receive_audio(session):
                """Collect audio chunks"""
                async for message in session.receive():
                    if hasattr(message, 'server_content') and message.server_content.audio_chunks:
                        audio_data = message.server_content.audio_chunks[0].data
                        audio_chunks.append(audio_data)
            
            async with self.client.aio.live.music.connect(model='models/lyria-realtime-exp') as session:
                # Set up task to receive audio
                receive_task = asyncio.create_task(receive_audio(session))
                
                # Configure music generation with WeightedPrompt
                await session.set_weighted_prompts(
                    prompts=[
                        types.WeightedPrompt(text=prompt, weight=1.0),
                    ]
                )
                
                # Use smart config based on tag
                config = self.build_music_config(tag)
                await session.set_music_generation_config(config=config)
                
                # Start generation
                await session.play()
                
                # Record for specified duration
                await asyncio.sleep(duration)
                
                # Stop generation
                await session.stop()
                
                # Allow receiver to flush remaining chunks
                await asyncio.sleep(0.1)
                
                # Cancel the receive task
                receive_task.cancel()
                try:
                    await receive_task
                except asyncio.CancelledError:
                    pass
            
            # Convert collected audio chunks to WAV
            if audio_chunks:
                return self._create_wav_from_chunks(audio_chunks)
            else:
                raise Exception("No audio generated")
                
        except Exception as e:
            raise Exception(f"Lyria API error: {str(e)}")
    
    async def generate_music(self, prompt: str, duration: int = 30) -> bytes:
        """Generate music using Lyria RealTime"""
        try:
            audio_chunks = []
            
            async def receive_audio(session):
                """Collect audio chunks"""
                async for message in session.receive():
                    if hasattr(message, 'server_content') and message.server_content.audio_chunks:
                        audio_data = message.server_content.audio_chunks[0].data
                        audio_chunks.append(audio_data)
            
            async with self.client.aio.live.music.connect(model='models/lyria-realtime-exp') as session:
                # Set up task to receive audio
                receive_task = asyncio.create_task(receive_audio(session))
                
                # Configure music generation
                await session.set_weighted_prompts(
                    prompts=[
                        types.WeightedPrompt(text=prompt, weight=1.0),
                    ]
                )
                
                await session.set_music_generation_config(
                    config=types.LiveMusicGenerationConfig(
                        bpm=120,
                        temperature=1.0,
                        guidance=4.0,
                        density=0.7,
                        brightness=0.5
                    )
                )
                
                # Start generation
                await session.play()
                
                # Record for specified duration
                await asyncio.sleep(duration)
                
                # Stop generation
                await session.stop()
                
                # Allow receiver to flush remaining chunks
                await asyncio.sleep(0.1)
                
                # Cancel the receive task
                receive_task.cancel()
                try:
                    await receive_task
                except asyncio.CancelledError:
                    pass
            
            # Convert collected audio chunks to WAV
            if audio_chunks:
                return self._create_wav_from_chunks(audio_chunks)
            else:
                raise Exception("No audio generated")
                
        except Exception as e:
            raise Exception(f"Lyria API error: {str(e)}")
    
    def _create_wav_from_chunks(self, audio_chunks: list) -> bytes:
        """Convert raw PCM chunks to WAV format"""
        # Lyria outputs 16-bit PCM at 48kHz stereo
        sample_rate = 48000
        channels = 2
        sample_width = 2  # 16-bit
        
        # Combine all chunks
        combined_audio = b''.join(audio_chunks)
        
        # Create WAV file in memory
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(sample_width)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(combined_audio)
        
        return wav_buffer.getvalue()