import asyncio
import websockets
import json
import threading
import sys

# Importa os módulos auxiliares
from spotify_manager import SpotifyManager
from audio_manager import AudioManager
from llm_manager import LLMManager
from skills_manager import SkillsManager

class DuzziAssistant:
    def __init__(self):
        # Carrega credenciais do Spotify via variáveis de ambiente
        self.SPOTIPY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID", "")
        self.SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET", "")
        
        self.state = "idle" # idle, listening, processing, speaking
        self.clients = set()
        
        # Inicializa modulos
        self.llm = LLMManager()
        self.skills = SkillsManager()
        self.spotify = SpotifyManager(self.SPOTIPY_CLIENT_ID, self.SPOTIPY_CLIENT_SECRET)
        
        # Audio Manager e suas callbacks. audio_manager roda e escuta.
        print("Iniciando AudioManager (isso pode levar uns segundos para baixar os modelos Whisper se aplicavel)...")
        # rodamos o audio processor em uma thread separada para nao travar o loop do asyncio
        self.audio = AudioManager(
            callback_wakeword=self.on_wakeword_detected,
            callback_transcript=self.on_voice_command_received
        )
        self.audio_thread = threading.Thread(target=self.audio.loop_process_audio, daemon=True)
        self.audio_thread.start()

    async def broadcast(self, message):
         if not self.clients:
              return
         data = json.dumps(message)
         aws = [asyncio.create_task(client.send(data)) for client in self.clients]
         await asyncio.wait(aws)

    def on_wakeword_detected(self):
        self.state = "listening"
        print("-> WAKE WORD DETECTADA!")
        # Como as webSockets funcoes async estao no main loop thread,
        # Nós criamos tasks no asyncio event loop para os broadcasts não bloqueantes
        try:
             loop = asyncio.get_running_loop()
             loop.create_task(self.broadcast({"type": "state", "value": "listening"}))
             loop.create_task(self.broadcast({"type": "wakeword", "value": "Jarvis invocado"}))
        except:
             pass

    def on_voice_command_received(self, text):
        self.state = "processing"
        print(f"-> COMANDO DE VOZ RECONHECIDO: {text}")
        try:
             loop = asyncio.get_running_loop()
             loop.create_task(self.broadcast({"type": "transcript", "value": text}))
             loop.create_task(self.broadcast({"type": "state", "value": "processing"}))
             # Dispara processador LLM pro texto que chegou do command local de audio.
             loop.create_task(self.process_intent(text))
        except:
             pass

    async def process_intent(self, user_text):
         # O processo do LLM bloquearia muito se fosse sincrono longamente, mas requests aqui ta block limiting,
         # O ideal num PROD absoluto e usar httpx assincrono no llm manager, mas para o local app server.
         # Faremos em thread executor pra ñ engasgar WS connections e o poller socket.
         loop = asyncio.get_running_loop()
         intent_json = await loop.run_in_executor(None, self.llm.get_intent, user_text)
         await self.execute_action(intent_json)

    async def execute_action(self, intent_json):
        action = intent_json.get("action", "speak")
        params = intent_json.get("params", {})
        resposta_falada = ""
        
        print(f"-> ACAO MAPEDA ESTRITA OLLAMA: {action}")
        
        if action == "speak":
            resposta_falada = params.get("text", "")
            
        elif action == "web_search":
             q = params.get("query", "")
             await self.broadcast({"type": "say", "value": f"*(Buscando na internet por: {q})*"})
             await self.broadcast({"type": "state", "value": "processing"})
             
             # Roda a busca de forma assincrona pra não travar o loop
             loop = asyncio.get_running_loop()
             search_results = await loop.run_in_executor(None, self.skills.web_search_duckduckgo, q)
             
             # Injeta o resultado no histórico como se fosse o sistema
             self.llm.add_message("system", search_results)
             
             # Pede pro LLM formular a resposta final baseada no histórico atualizado
             new_intent = await loop.run_in_executor(None, self.llm.get_intent, "Por favor, formule a resposta final baseada nos resultados da pesquisa acima.")
             
             # Executa a nova intenção recursivamente (provavelmente será um 'speak')
             return await self.execute_action(new_intent)
            
        elif action == "play_spotify":
             resposta_falada = self.spotify.play_track(params.get("query", ""))
        elif action == "pause_spotify":
             resposta_falada = self.spotify.pause()
        elif action == "next_spotify":
             resposta_falada = self.spotify.next_track()
        elif action == "prev_spotify":
             resposta_falada = self.spotify.prev_track()
        elif action == "volume_spotify":
             resposta_falada = self.spotify.set_volume(params.get("vol", 50))
        elif action == "queue_spotify":
             resposta_falada = self.spotify.add_to_queue(params.get("query", ""))
        elif action == "playlist_spotify":
             resposta_falada = self.spotify.play_playlist(params.get("query", ""))
        elif action == "liked_spotify":
             resposta_falada = self.spotify.play_liked_songs()

        elif action == "weather":
             city = params.get("city")
             if not city: city = self.llm.profile.get("cidade", "São Paulo")
             resposta_falada = self.skills.get_weather(city)

        elif action == "open_app":
             app_name = params.get("app_name", "")
             resposta_falada = self.skills.open_app(app_name)

        elif action == "open_site":
             url = params.get("url", "")
             resposta_falada = self.skills.open_site(url)
             
        elif action == "search_google":
             q = params.get("query", "")
             resposta_falada = self.skills.search_google(q)
             
        elif action == "note":
             t = params.get("text", "")
             resposta_falada = self.skills.save_note(t)
             await self.broadcast({"type": "notes_data", "value": self.skills.get_all_notes()})
             
        elif action == "timer":
             secs = params.get("seconds", 10)
             name = params.get("name", "Timer genérico")
             def cb(txt):
                  # Cria task assincrona para quando estourar o timer emitir alerta na interface e voz
                  t = asyncio.create_task(self.say_internal(txt))
                  return t
             resposta_falada = self.skills.create_timer(secs, name, cb)
             
        elif action == "generate_password":
             size = params.get("length", 14)
             resposta_falada = self.skills.generate_password(size)

        else:
             resposta_falada = "Não tenho certeza sobre como processar a ação mapeada internamente."
        
        await self.say_internal(resposta_falada)
        
    async def say_internal(self, text):
        if not text:
             self.state = "idle"
             await self.broadcast({"type": "state", "value": "idle"})
             return
             
        print(f"Duzzi diz: {text}")
        self.state = "speaking"
        await self.broadcast({"type": "say", "value": text})
        await self.broadcast({"type": "state", "value": "speaking"})
        
        # TTS foi desativado a pedido do usuario ("EU QUERO SO O TEXTO")
        # await self.audio.speak(text)
        
        # Simulando um pequeno delay para a UI processar (já que o TTS demorava)
        await asyncio.sleep(1)
        
        # Pos fala, transicao state back
        self.state = "idle"
        await self.broadcast({"type": "state", "value": "idle"})

    # ---------- WS CONNECTION HANDLER -----------
    async def websocket_handler(self, websocket, path=None):
         self.clients.add(websocket)
         print(f"Cliente UI conectado. Total clientes: {len(self.clients)}")
         try:
             # Envia profile inicianlmente e estado
             await websocket.send(json.dumps({"type": "profile_data", "value": self.llm.profile}))
             await websocket.send(json.dumps({"type": "state", "value": self.state}))
             # Adiciona sincronia inicial das notas da tela Mural
             await websocket.send(json.dumps({"type": "notes_data", "value": self.skills.get_all_notes()}))
             
             # Envia lista de sessoes e carrega a atual
             await websocket.send(json.dumps({"type": "sessions_list", "value": self.llm.get_sessions_list(), "active_id": self.llm.active_session_id}))
             await websocket.send(json.dumps({"type": "session_loaded", "value": self.llm.get_active_messages()}))
             
             async for message in websocket:
                 data = json.loads(message)
                 m_type = data.get("type")
                 
                 if m_type == "command": # command direto da UI de texto
                      user_cmd = data.get("value", "")
                      await self.broadcast({"type": "transcript", "value": user_cmd})
                      self.state = "processing"
                      await self.broadcast({"type": "state", "value": "processing"})
                      await self.process_intent(user_cmd)
                      # Sempre após um comando do usuário, o título da sessão pode ter mudado
                      await self.broadcast({"type": "sessions_list", "value": self.llm.get_sessions_list(), "active_id": self.llm.active_session_id})
                      
                 elif m_type == "new_session":
                      self.llm.create_session()
                      await websocket.send(json.dumps({"type": "sessions_list", "value": self.llm.get_sessions_list(), "active_id": self.llm.active_session_id}))
                      await websocket.send(json.dumps({"type": "session_loaded", "value": self.llm.get_active_messages()}))
                      
                 elif m_type == "load_session":
                      sid = data.get("value")
                      self.llm.switch_session(sid)
                      await websocket.send(json.dumps({"type": "sessions_list", "value": self.llm.get_sessions_list(), "active_id": self.llm.active_session_id}))
                      await websocket.send(json.dumps({"type": "session_loaded", "value": self.llm.get_active_messages()}))

                 elif m_type == "spotify_cmd":
                      cmd = data.get("value")
                      if cmd == "play": self.spotify.resume()
                      elif cmd == "pause": self.spotify.pause()
                      elif cmd == "next": self.spotify.next_track()
                      elif cmd == "prev": self.spotify.prev_track()
                      elif cmd == "volume": self.spotify.set_volume(data.get("vol", 50))
                      
                 elif m_type == "profile_get":
                      await websocket.send(json.dumps({"type": "profile_data", "value": self.llm.profile}))
                      
                 elif m_type == "profile_set":
                      new_prof = data.get("value", {})
                      self.llm.save_profile(new_prof)
                      await self.broadcast({"type": "profile_data", "value": self.llm.profile})

                 elif m_type == "get_notes_list":
                      await websocket.send(json.dumps({"type": "notes_data", "value": self.skills.get_all_notes()}))
                      
                 elif m_type == "delete_note":
                      idx = data.get("value", -1)
                      self.skills.delete_note(idx)
                      await self.broadcast({"type": "notes_data", "value": self.skills.get_all_notes()})

         except websockets.exceptions.ConnectionClosed:
             pass
         except Exception as e:
             import traceback
             print(f"Erro no websocket handler: {e}")
             traceback.print_exc()
         finally:
             self.clients.remove(websocket)
             print(f"Cliente desconectado. Restantes: {len(self.clients)}")
             
    # ---------- BACKGROUND TASKS -----------
    async def poller_spotify_now_playing(self):
         while True:
             if self.clients and self.spotify.sp:
                 loop = asyncio.get_running_loop()
                 # Evitar travamento do loop se lib do spotipy network sync demorar
                 current = await loop.run_in_executor(None, self.spotify.get_current_playing)
                 if current:
                     await self.broadcast({"type": "now_playing", "value": current})
             await asyncio.sleep(5)

async def main():
    duzzi = DuzziAssistant()
    
    server = await websockets.serve(duzzi.websocket_handler, "127.0.0.1", 9876)
    print("Duzzi WS Server inicializado na porta ws://127.0.0.1:9876")
    
    # Inicia poller do spotify rodando concorrente
    asyncio.create_task(duzzi.poller_spotify_now_playing())
    
    await server.wait_closed()

if __name__ == "__main__":
    # Workaround pra possivel erro em alguns prompters windows de event policy
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
