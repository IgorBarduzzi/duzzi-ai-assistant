import os
import json
import asyncio
import subprocess
import webbrowser
import requests
import string
import secrets
from datetime import datetime

class SkillsManager:
    def __init__(self):
        self.notes_file = os.path.join(os.path.expanduser("~"), "duzzi_notes.json")
        self.timers = {}
        
        # Dicionario simples de apps frequentes do windows
        self.APPS = {
            "bloco de notas": "notepad.exe",
            "calculadora": "calc.exe",
            "navegador": "msedge.exe", # ou chrome.exe
            "paint": "mspaint.exe",
            "explorador de arquivos": "explorer.exe",
            "terminal": "cmd.exe",
            "configurações": "ms-settings:"
        }

    def get_weather(self, city):
        """Consulta clima via wttr.in (sem chave)"""
        if not city:
            return "Nenhuma cidade informada."
        try:
            url = f"https://wttr.in/{city}?format=%C+%t"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                texto_clima = response.text.strip()
                # Tradução basica do wttr caso ingles
                traducoes = {
                    "Clear": "Céu limpo", "Sunny": "Ensolarado", "Partly cloudy": "Parcialmente nublado",
                    "Cloudy": "Nublado", "Overcast": "Encoberto", "Rain": "Chuva", "Snow": "Neve"
                }
                for en, pt in traducoes.items():
                    texto_clima = texto_clima.replace(en, pt)
                return f"O clima atual em {city} é: {texto_clima}."
            return "Não consegui obter o clima dessa base de dados."
        except Exception as e:
            return f"Erro de conexão ao checar o clima: {e}"

    def open_app(self, app_name):
        app_lower = app_name.lower().strip()
        
        # Busca parcial simples
        comando = None
        for key, exe in self.APPS.items():
            if key in app_lower or app_lower in key:
                comando = exe
                break
                
        if comando:
            try:
                # Se for ms-settings: o padrao de url do windows
                if comando.startswith("ms-"):
                    os.system(f"start {comando}")
                else:
                    subprocess.Popen(comando)
                return f"Abrindo {app_name}..."
            except Exception as e:
                return f"Tentei abrir, mas falhei: {e}"
        else:
            return f"Não tenho um atalho mapeado para o app '{app_name}'."

    def save_note(self, text):
        notes = []
        if os.path.exists(self.notes_file):
            try:
                 with open(self.notes_file, "r", encoding="utf-8") as f:
                     notes = json.load(f)
            except: pass
            
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        notes.append({"date": timestamp, "text": text})
        
        with open(self.notes_file, "w", encoding="utf-8") as f:
            json.dump(notes, f, indent=4, ensure_ascii=False)
            
        return "Anotado com sucesso na sua base de memórias temporárias."

    def get_notes(self):
        if os.path.exists(self.notes_file):
            try:
                 with open(self.notes_file, "r", encoding="utf-8") as f:
                     notes = json.load(f)
                 if notes:
                     # Retornar as ultimas 3 notas formatadas
                     recentes = notes[-3:]
                     return "Tudo bem, aqui vão suas anotações recentes. " + " ".join([f"Na data {n['date']} você anotou: {n['text']}." for n in recentes])
            except: pass
        return "O seu bloco de notas está vazio."

    def get_all_notes(self):
        if os.path.exists(self.notes_file):
            try:
                with open(self.notes_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except: pass
        return []

    def delete_note(self, idx):
        if os.path.exists(self.notes_file):
            try:
                with open(self.notes_file, "r", encoding="utf-8") as f:
                    notes = json.load(f)
                if 0 <= idx < len(notes):
                    notes.pop(idx)
                    with open(self.notes_file, "w", encoding="utf-8") as f:
                        json.dump(notes, f, indent=4, ensure_ascii=False)
                    return True
            except: pass
        return False

    def open_site(self, url):
        # limpa para garantir https
        url = url.lower().strip()
        if not url.startswith("http"):
            url = f"https://{url}"
            
        try:
            webbrowser.open(url)
            return f"Navegando para o site solicitado."
        except:
             return "Falha ao abrir o site."

    def search_google(self, query):
        url = f"https://www.google.com/search?q={query}"
        try:
            webbrowser.open(url)
            return f"Pesquisando {query} no Google."
        except:
             return "Falha ao abrir o Google."

    def web_search_duckduckgo(self, query):
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=3))
                if not results:
                    return "Não encontrei resultados na internet para essa busca."
                
                # Formata os resultados em um texto limpo
                contexto = "Resultados da pesquisa:\n"
                for i, r in enumerate(results):
                    contexto += f"{i+1}. Título: {r['title']}\nTrecho: {r['body']}\n\n"
                return contexto
        except Exception as e:
            return f"Erro ao acessar a internet: {e}"

    def generate_password(self, length=14):
        alfabeto = string.ascii_letters + string.digits + "!@#$%&*"
        senha = ''.join(secrets.choice(alfabeto) for _ in range(int(length)))
        return f"A senha gerada é {senha} (com {length} caracteres). Ela foi enviada para cá, recomendo copiá-la ao invés de ouví-la."

    async def _timer_task(self, seconds, name, callback):
        await asyncio.sleep(seconds)
        if callback:
             await callback(f"Atenção Duzzi: Lembre o usuário do timer de nome: {name}")

    def create_timer(self, seconds, name, callback):
        try:
            segundos = int(seconds)
            task = asyncio.create_task(self._timer_task(segundos, name, callback))
            self.timers[name] = task
            return f"Timer criado para {segundos} segundos. Título: {name}."
        except:
            return "Falha ao parsear os segundos para criação do timer."
