import io
import tempfile
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeVideoClip
import httpx

class VideoProcessor:
    def __init__(self):
        self.default_format = "mp4"
        self.default_fps = 30
        self.default_resolution = (1920, 1080)
    
    async def combine_audio_video(self, audio_data: bytes, video_url: str) -> bytes:
        """Combine audio with video"""
        try:
            # Download video
            async with httpx.AsyncClient() as client:
                video_response = await client.get(video_url)
                video_data = video_response.content
            
            # Create temporary files
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as video_temp:
                video_temp.write(video_data)
                video_temp_path = video_temp.name
            
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as audio_temp:
                audio_temp.write(audio_data)
                audio_temp_path = audio_temp.name
            
            # Load video and audio
            video_clip = VideoFileClip(video_temp_path)
            audio_clip = AudioFileClip(audio_temp_path)
            
            # Match durations
            audio_duration = audio_clip.duration
            if video_clip.duration < audio_duration:
                # Loop video to match audio duration
                loops_needed = int(audio_duration / video_clip.duration) + 1
                video_clip = video_clip.loop(loops_needed)
            
            # Trim video to match audio duration
            video_clip = video_clip.subclip(0, audio_duration)
            
            # Set audio to video
            final_clip = video_clip.set_audio(audio_clip)
            
            # Export to bytes
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as output_temp:
                final_clip.write_videofile(
                    output_temp.name,
                    fps=self.default_fps,
                    codec='libx264',
                    audio_codec='aac',
                    temp_audiofile='temp-audio.m4a',
                    remove_temp=True,
                    verbose=False,
                    logger=None
                )
                
                # Read the output file
                with open(output_temp.name, 'rb') as f:
                    result = f.read()
            
            # Cleanup
            video_clip.close()
            audio_clip.close()
            final_clip.close()
            
            return result
            
        except Exception as e:
            raise Exception(f"Video processing error: {str(e)}")
    
    def create_simple_video(self, duration: int, background_color: tuple = (0, 0, 0)) -> bytes:
        """Create a simple colored background video"""
        try:
            from moviepy.editor import ColorClip
            
            # Create a solid color clip
            clip = ColorClip(
                size=self.default_resolution,
                color=background_color,
                duration=duration
            )
            
            # Export to bytes
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
                clip.write_videofile(
                    temp_file.name,
                    fps=self.default_fps,
                    codec='libx264',
                    verbose=False,
                    logger=None
                )
                
                with open(temp_file.name, 'rb') as f:
                    result = f.read()
            
            clip.close()
            return result
            
        except Exception as e:
            raise Exception(f"Simple video creation error: {str(e)}")
    
    def add_text_overlay(self, video_data: bytes, text: str, 
                        position: tuple = ('center', 'center')) -> bytes:
        """Add text overlay to video"""
        try:
            from moviepy.editor import TextClip, CompositeVideoClip
            
            # Create temporary file for input video
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_input:
                temp_input.write(video_data)
                temp_input_path = temp_input.name
            
            # Load video
            video_clip = VideoFileClip(temp_input_path)
            
            # Create text clip
            text_clip = TextClip(
                text,
                fontsize=50,
                color='white',
                font='Arial-Bold'
            ).set_position(position).set_duration(video_clip.duration)
            
            # Composite video with text
            final_clip = CompositeVideoClip([video_clip, text_clip])
            
            # Export
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_output:
                final_clip.write_videofile(
                    temp_output.name,
                    fps=self.default_fps,
                    codec='libx264',
                    verbose=False,
                    logger=None
                )
                
                with open(temp_output.name, 'rb') as f:
                    result = f.read()
            
            # Cleanup
            video_clip.close()
            text_clip.close()
            final_clip.close()
            
            return result
            
        except Exception as e:
            raise Exception(f"Text overlay error: {str(e)}")