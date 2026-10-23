import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth

# Autenticação local OAuth para Spotify API

CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET", "")
REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI", "http://127.0.0.1:8888/callback")

# Escopos mapeados pelas exigências de funcionalidade
SCOPES = "user-modify-playback-state user-read-playback-state user-library-read playlist-read-private"

def auth():
    print("Iniciando a autenticação do Spotify...")
    # O arquivo `.spotify_token` armazenará o cache
    cache_path = os.path.join(os.path.dirname(__file__), ".spotify_token")

    sp_oauth = SpotifyOAuth(client_id=CLIENT_ID,
                            client_secret=CLIENT_SECRET,
                            redirect_uri=REDIRECT_URI,
                            scope=SCOPES,
                            cache_path=cache_path)
    
    # Abre o navegador para autorização do usuário e armazena o token em cache
    token_info = sp_oauth.get_access_token(as_dict=False)
    
    if token_info:
        print("Autenticação finalizada com sucesso!")
        print(f"O token foi salvo em {cache_path}")
        print("A API está pronta para ser consumida pelo Duzzi.")
    else:
        print("Houve um erro na autenticação. Feche tudo e confira suas credenciais e a Redirect URI.")

if __name__ == "__main__":
    auth()
