import os
import json
import uuid
import requests
from datetime import datetime

class LLMManager:
    def __init__(self):
        ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
        self.OLLAMA_URL = f"{ollama_host}/api/chat"
        self.MODEL = os.getenv("OLLAMA_MODEL", "llama3:latest")
        self.history_file = os.path.join(os.path.expanduser("~"), "duzzi_history.json")
        self.profile_file = os.path.join(os.path.expanduser("~"), "duzzi_profile.json")
        self.profile = self.load_profile()
        self.sessions = self.load_sessions()
        self.active_session_id = None
        
        # Cria a primeira sessão se não houver nenhuma
        if not self.sessions:
            self.create_session()
        else:
            # Pega a ultima sessão como ativa
            self.active_session_id = list(self.sessions.keys())[-1]

    def load_profile(self):
        if os.path.exists(self.profile_file):
            try:
                with open(self.profile_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return {"nome": "Nenhum", "cidade": "Desconhecida", "estilo": "amigável"}

    def save_profile(self, profile_data):
        self.profile.update(profile_data)
        with open(self.profile_file, "w", encoding="utf-8") as f:
            json.dump(self.profile, f, indent=4, ensure_ascii=False)

    def load_sessions(self):
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Verifica se é formato antigo (lista)
                    if isinstance(data, list):
                        sid = str(uuid.uuid4())
                        return {sid: {"title": "Conversa Antiga", "messages": data}}
                    return data
            except:
                pass
        return {}

    def save_sessions(self):
        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(self.sessions, f, indent=4, ensure_ascii=False)

    def create_session(self):
        sid = str(uuid.uuid4())
        self.sessions[sid] = {"title": "Nova sessao", "messages": []}
        self.active_session_id = sid
        self.save_sessions()
        return sid

    def get_sessions_list(self):
        return [{"id": k, "title": v["title"]} for k, v in self.sessions.items()]

    def switch_session(self, sid):
        if sid in self.sessions:
            self.active_session_id = sid
            return self.sessions[sid]["messages"]
        return []

    def get_active_messages(self):
        if not self.active_session_id or self.active_session_id not in self.sessions:
            self.create_session()
        return self.sessions[self.active_session_id]["messages"]

    def add_message(self, role, content):
        msgs = self.get_active_messages()
        msgs.append({"role": role, "content": content})
        
        # Atualiza titulo se for a primeira msg do user
        if role == "user" and len(msgs) <= 2 and self.sessions[self.active_session_id]["title"] == "Nova sessao":
            self.sessions[self.active_session_id]["title"] = content[:30] + ("..." if len(content) > 30 else "")
            
        if len(msgs) > 30: # Mantem até 30 na memoria ativa por sessao
            self.sessions[self.active_session_id]["messages"] = msgs[-30:]
            
        self.save_sessions()

    def generate_system_prompt(self):
        profile_str = ", ".join([f"{k}: {v}" for k, v in self.profile.items()])
        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        
        prompt = (
            f"Você é Duzzi, um assistente AI focado em código e produtividade.\n"
            f"Data/Hora atual: {now}\n"
            f"Perfil do usuário: {profile_str}\n\n"
            "REGRA ABSOLUTA: Responda SOMENTE com JSON puro. Sem markdown, sem ```json, sem texto extra. Apenas o objeto JSON.\n"
            "Estrutura:\n"
            '{"action": "TIPO", "params": {...}}\n\n'
            "AÇÕES DISPONÍVEIS:\n"
            "1. speak - Responder, conversar, gerar código. Params: {\"text\": \"sua resposta\"}\n"
            "2. play_spotify - Tocar música. Params: {\"query\": \"NOME_MUSICA NOME_ARTISTA\"}\n"
            "   REGRA SPOTIFY: Extraia APENAS o nome da música e do artista. Remova TODAS as preposições (de, do, da, dos, das, no, na).\n"
            "   EXEMPLOS:\n"
            '   - Usuário: "toque nino do millo j" -> {"action":"play_spotify","params":{"query":"niño milo j"}}\n'
            '   - Usuário: "toque let down do radiohead" -> {"action":"play_spotify","params":{"query":"let down radiohead"}}\n'
            '   - Usuário: "toque black do pearl jam" -> {"action":"play_spotify","params":{"query":"black pearl jam"}}\n'
            '   - Usuário: "toque piano man do billy joel" -> {"action":"play_spotify","params":{"query":"piano man billy joel"}}\n'
            '   - Usuário: "toque creep do radiohead" -> {"action":"play_spotify","params":{"query":"creep radiohead"}}\n'
            '   - Usuário: "toque as it was do harry styles" -> {"action":"play_spotify","params":{"query":"as it was harry styles"}}\n'
            "3. pause_spotify - Pausar música. Sem params.\n"
            "4. next_spotify - Próxima faixa. Sem params.\n"
            "5. prev_spotify - Faixa anterior. Sem params.\n"
            "6. volume_spotify - Ajustar volume. Params: {\"vol\": 50}\n"
            "7. web_search - Pesquisar na internet. Params: {\"query\": \"termos\"}\n"
            "8. open_site - Abrir site. Params: {\"url\": \"https://...\"}\n"
            "9. search_google - Busca Google. Params: {\"query\": \"termos\"}\n\n"
            "Para conversar e enviar códigos, use SEMPRE a ação 'speak'."
        )
        return prompt

    def get_intent(self, user_text):
        self.add_message("user", user_text)
        
        system_msg = {"role": "system", "content": self.generate_system_prompt()}
        messages = [system_msg] + self.get_active_messages()

        payload = {
            "model": self.MODEL,
            "messages": messages,
            "stream": False,
            "format": "json"
        }

        try:
            print(f"Enviando requisição ao Ollama ({self.MODEL})...")
            response = requests.post(self.OLLAMA_URL, json=payload, timeout=40)
            response.raise_for_status()
            
            ai_data = response.json()
            raw_content = ai_data["message"]["content"]
            
            result_json = json.loads(raw_content)
            
            if result_json.get("action") == "speak":
                self.add_message("assistant", result_json.get("params", {}).get("text", ""))
            else:
                 self.add_message("assistant", f"*(Ação interna acionada: {result_json.get('action')})*")
                 
            return result_json

        except Exception as e:
            print(f"Erro ao contatar LLM: {e}")
            return {"action": "speak", "params": {"text": "Tive um problema de conexão com a minha rede neural, Duzzi está fora do ar."}}
