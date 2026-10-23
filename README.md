# Duzzi AI — Assistente de Voz Local

Assistente virtual de voz executado localmente, focado em privacidade e baixa latência. O sistema combina detecção contínua de palavra de ativação (*wake word*), transcrição de áudio em tempo real com **Faster-Whisper**, raciocínio via **Ollama** e sintetização de fala neural (TTS), com interface web reativa conectada via WebSockets.

---

## ⚙️ Arquitetura

```
Microfone ➔ OpenWakeWord ➔ Faster-Whisper ➔ Ollama (Llama 3) ➔ Ações / Edge-TTS ➔ Áudio / UI
```

- **Wake Word:** Escuta contínua em segundo plano com modelo pré-treinado via `openwakeword`.
- **Speech-to-Text (STT):** Transcrição de voz utilizando `faster-whisper` (CTranslate2).
- **Raciocínio (LLM):** Inferência local com Ollama (`llama3:latest` ou modelo configurável).
- **Text-to-Speech (TTS):** Síntese de áudio neural via `edge-tts` com reprodução nativa em baixa latência.
- **Interface & Transporte:** Painel web conectado por WebSockets assíncronos (`asyncio`).
- **Integrações:** Módulo de controle para Spotify (OAuth), pesquisa web, timer e abertura de aplicativos.

---

## 🚀 Como Executar

### 1. Pré-requisitos
- Python 3.10+
- [Ollama](https://ollama.ai) instalado e rodando com o modelo baixado:
  ```bash
  ollama run llama3:latest
  ```

### 2. Instalação das dependências
```bash
git clone https://github.com/IgorBarduzzi/duzzi-ai-assistant.git
cd duzzi-ai-assistant

python -m venv .venv
# No Windows:
.venv\Scripts\activate
# No Linux/macOS:
source .venv/bin/activate

pip install -r backend/requirements.txt
```

### 3. Configuração do ambiente
Copie o arquivo de exemplo e ajuste as variáveis necessárias:
```bash
cp .env.example .env
```

| Variável | Padrão | Descrição |
| :--- | :--- | :--- |
| `OLLAMA_HOST` | `http://localhost:11434` | Endereço do servidor Ollama |
| `OLLAMA_MODEL` | `llama3:latest` | Modelo LLM utilizado |
| `SPOTIPY_CLIENT_ID` | *(Opcional)* | Client ID do Spotify Developer |
| `SPOTIPY_CLIENT_SECRET` | *(Opcional)* | Client Secret do Spotify Developer |

### 4. Iniciar o servidor
```bash
python backend/server.py
```
O servidor WebSocket iniciará na porta `8765`. Para interagir via interface, abra o arquivo `UI/index.html` no navegador.

---

## 🛠️ Comandos Suportados

- **Conversação Geral:** Dúvidas, explicações técnicas e assistência em código.
- **Controle de Mídia:** Tocar faixas, artistas ou playlists no Spotify, pausar e pular músicas.
- **Produtividade:** Definição de timers, anotações rápidas e consulta de clima.
- **Automação:** Abertura de aplicativos locais e pesquisas na web.

---

## 📄 Licença

Distribuído sob a licença [MIT](LICENSE).
