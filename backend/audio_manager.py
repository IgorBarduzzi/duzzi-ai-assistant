import os
import time
import queue
import asyncio
import numpy as np
import sounddevice as sd
import soundfile as sf
import edge_tts
import subprocess

# Ignora warnings em C e ALSA caso haja, util para console mais limpo
os.environ["PYTHONWARNINGS"] = "ignore"

class AudioManager:
    def __init__(self, callback_wakeword, callback_transcript):
        self.callback_wakeword = callback_wakeword
        self.callback_transcript = callback_transcript
        
        self.SILENCE_RMS_THRESHOLD = 0.01
        self.SAMPLE_RATE = 16000
        self.CHANNELS = 1
        self.BLOCK_SIZE = int(self.SAMPLE_RATE * 0.5) # 0.5 seconds per block
        
        self.is_listening = True
        self.audio_queue = queue.Queue()
        self.wake_word_model = None
        self.stt_model = None
        self.state = "idle" # "idle", "listening_command"
        self.vad_timeout = 2.0 # Segundos de silêncio para assumir que comando terminou
        
        self.init_models()
        self.start_microphone_stream()

    def init_models(self):
        try:
            from faster_whisper import WhisperModel
            print("Iniciando carregamento do modelo Faster-Whisper (Small, pt)...")
            self.stt_model = WhisperModel("small", device="cpu", compute_type="int8")
        except Exception as e:
            print(f"Aviso: Faster-Whisper ausente ou incompatível com seu Python atual. Funcionalidade de voz desativada. Use apenas texto. Erro: {e}")
            self.stt_model = None
        
        print("Tentando carregar o OpenWakeWord...")
        try:
            import openwakeword
            from openwakeword.model import Model
            openwakeword.utils.download_models() # baixe os pretreinados se n houver
            self.wake_word_model = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
            print("OpenWakeWord carregado com Hey Jarvis!")
        except Exception as e:
            print(f"Aviso: OpenWakeWord falhou. Fallback ativado (sem wakeword estrito). Erro: {e}")

    def audio_callback(self, indata, frames, time, status):
        # Callback assíncrono do pyaudio/sounddevice -> Thread
        if status:
            pass # print(status)
        if self.is_listening:
            audio_data = indata.copy().flatten()
            self.audio_queue.put(audio_data)

    def start_microphone_stream(self):
        print("Iniciando thread de stream do Microfone...")
        self.stream = sd.InputStream(samplerate=self.SAMPLE_RATE,
                                     channels=self.CHANNELS,
                                     blocksize=self.BLOCK_SIZE,
                                     callback=self.audio_callback)
        self.stream.start()
        
    def loop_process_audio(self):
        """ Laço que processa a queue de áudio num worker thread separado """
        buffer_audio = []
        silence_start_time = None
        
        while True:
            audio_chunk = self.audio_queue.get()
            
            if self.state == "idle":
                if self.wake_word_model:
                    prediction = self.wake_word_model.predict(audio_chunk)
                    if "hey_jarvis" in prediction and prediction["hey_jarvis"] > 0.5:
                        self.callback_wakeword()
                        self.state = "listening_command"
                        buffer_audio = []
                        silence_start_time = None
                else:
                    # Ativação por limiar de energia (RMS) caso wake word esteja desabilitada.
                    rms = np.sqrt(np.mean(audio_chunk**2))
                    if rms > self.SILENCE_RMS_THRESHOLD:
                        self.callback_wakeword()
                        self.state = "listening_command"
                        buffer_audio = [audio_chunk]
                        silence_start_time = None
                        
            elif self.state == "listening_command":
                rms = np.sqrt(np.mean(audio_chunk**2))
                buffer_audio.append(audio_chunk)
                
                if rms < self.SILENCE_RMS_THRESHOLD:
                    if silence_start_time is None:
                        silence_start_time = time.time()
                    elif (time.time() - silence_start_time) > self.vad_timeout:
                        self.state = "idle"
                        self.process_command(buffer_audio)
                        buffer_audio = []
                else:
                    silence_start_time = None

    def process_command(self, buffer_audio):
        combined = np.concatenate(buffer_audio)
        # Salva o array em um disco temporario para jogar no whisper
        temp_wav = "temp_command.wav"
        sf.write(temp_wav, combined, self.SAMPLE_RATE)
        
        if not self.stt_model:
            print("STT Model off, ignoring audio chunk.")
            return

        print("Transcrevendo com Whisper...")
        segments, _ = self.stt_model.transcribe(temp_wav, language="pt", vad_filter=True)
        text = " ".join([segment.text for segment in segments]).strip()
        
        if os.path.exists(temp_wav):
            os.remove(temp_wav)
            
        if text:
            print(f"Você disse: {text}")
            self.callback_transcript(text)
        else:
            print("Whisper: (audio inaudível)")

    async def speak(self, text):
        """ Executa text to speech assincrono via Edge-TTS pausando a captura de áudio """
        if not text: return
        self.is_listening = False
        self.audio_queue.queue.clear()
        
        communicate = edge_tts.Communicate(text, "pt-BR-AntonioNeural")
        temp_audio = "tts_response.mp3"
        await communicate.save(temp_audio)
        
        try:
            # Toca o áudio de forma nativa e secreta (invisível) usando a API C do Windows (winmm)
            # Isso impede que o seu Media Player abra, e também não trava o arquivo.
            import ctypes
            mciSendString = ctypes.windll.winmm.mciSendStringW
            
            # Resolve o caminho absoluto pois API Windows as vezes sofre do cwd do script python
            abs_path = os.path.abspath(temp_audio)
            
            mciSendString(f'open "{abs_path}" type mpegvideo alias duzzi_tts', None, 0, None)
            mciSendString(f'play duzzi_tts wait', None, 0, None)
            mciSendString(f'close duzzi_tts', None, 0, None)
        except Exception as e:
            print(f"Tentativa falha de usar MCI: {e}")
            
        # O arquivo agora já não está bloqueado por reprodutores como o Groove, podemos deletar limpo.
        if os.path.exists(temp_audio):
           try:
               os.remove(temp_audio)
           except: pass
           
        self.is_listening = True
