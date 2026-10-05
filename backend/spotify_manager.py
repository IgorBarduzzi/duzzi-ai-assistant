import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth

class SpotifyManager:
    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = "http://127.0.0.1:8888/callback"
        self.scopes = "user-modify-playback-state user-read-playback-state user-library-read playlist-read-private"
        self.cache_path = os.path.join(os.path.dirname(__file__), ".spotify_token")
        self.sp = None
        self.connect()

    def connect(self):
        try:
            auth_manager = SpotifyOAuth(client_id=self.client_id,
                                        client_secret=self.client_secret,
                                        redirect_uri=self.redirect_uri,
                                        scope=self.scopes,
                                        cache_path=self.cache_path)
            self.sp = spotipy.Spotify(auth_manager=auth_manager, requests_timeout=20)
            print("Spotify Assistant Connected.")
        except Exception as e:
            print(f"Erro ao conectar no Spotify: {e}")

    def get_current_playing(self):
        if not self.sp:
            return None
        try:
            current = self.sp.current_playback()
            if current and current.get('item'):
                track = current['item']
                return {
                    "title": track.get('name', 'Unknown'),
                    "artist": ", ".join([artist['name'] for artist in track.get('artists', [])]),
                    "album_cover": track['album']['images'][0]['url'] if track.get('album') and track['album'].get('images') else "",
                    "is_playing": current.get('is_playing', False),
                    "progress_ms": current.get('progress_ms', 0),
                    "duration_ms": track.get('duration_ms', 0)
                }
        except Exception as e:
            print(f"Erro em get_current_playing: {e}")
        return None

    def _clean_query(self, query):
        """Remove preposições portuguesas que confundem a busca do Spotify."""
        import re
        stop_words = {'de', 'do', 'da', 'dos', 'das', 'no', 'na', 'nos', 'nas', 'toque', 'toca', 'coloca', 'bota'}
        words = query.split()
        cleaned = [w for w in words if w.lower() not in stop_words]
        result = ' '.join(cleaned)
        
        # Correções de grafia comuns para melhorar a busca
        replacements = {
            r'\bmill?o\s*j\b': 'milo j',
            r'\bni[nñ]o\b': 'niño',
        }
        for pattern, repl in replacements.items():
            result = re.sub(pattern, repl, result, flags=re.IGNORECASE)
            
        print(f"[Spotify] Query original: '{query}' -> limpa: '{result}'")
        return result

    def play_track(self, query):
        if not self.sp: return ""
        try:
            clean_q = self._clean_query(query)
            if not clean_q:
                print("[Spotify] Query vazia após limpeza")
                return ""
            results = self.sp.search(q=clean_q, type='track', limit=5)
            tracks = results['tracks']['items']
            if tracks:
                track = tracks[0]
                track_uri = track['uri']
                album_uri = track['album']['uri']
                
                # Ao invés de uris=[track_uri] (que cria uma fila de 1 música), 
                # usamos o contexto do álbum e iniciamos a partir da música.
                # Assim o botão Next vai para a próxima faixa do álbum.
                try:
                     self.sp.start_playback(context_uri=album_uri, offset={"uri": track_uri})
                except Exception:
                     # Fallback para caso seja uma música sem context_uri válido (ex: local files)
                     self.sp.start_playback(uris=[track_uri])
                     
                return f"Tocando {track['name']} de {track['artists'][0]['name']}"
            return ""
        except Exception as e:
            print(f"[Spotify Error] {e}")
            return ""

    def play_playlist(self, query):
        if not self.sp: return
        try:
            results = self.sp.search(q=query, type='playlist', limit=5)
            playlists = results['playlists']['items']
            if playlists:
                playlist_uri = playlists[0]['uri']
                self.sp.start_playback(context_uri=playlist_uri)
                return f"Tocando a playlist {playlists[0]['name']}"
            return ""
        except Exception as e:
            print(f"[Spotify Error] {e}")
            return ""

    def play_liked_songs(self):
        if not self.sp: return
        try:
            # Como a library só permite buscar top_tracks ou liked (sem URIs para start_playback fácil, precisamos de workaround ou tocar recent)
            # Tocar musicas curtidas normalmente requer passar os URIs, o que quebra o limite se forem muitas.
            # O jeito the user requests is to find it, mas o Spotipy api não toca 'liked songs' diretamente via context_uri nativo pra biblioteca inteira.
            # Workaround: Pegar as ultimas 50 e mandar tocar
            results = self.sp.current_user_saved_tracks(limit=50)
            uris = [item['track']['uri'] for item in results['items']]
            if uris:
                self.sp.start_playback(uris=uris)
                return "Tocando suas músicas curtidas mais recentes."
            return ""
        except Exception as e:
            print(f"[Spotify Error] {e}")
            return ""

    def pause(self):
        if not self.sp: return
        try:
            self.sp.pause_playback()
            return "Música pausada."
        except Exception as e:
            print(f"[Spotify Error] {e}")
            return ""

    def resume(self):
        if not self.sp: return
        try:
            self.sp.start_playback()
            return "Retomando música."
        except Exception as e:
            print(f"[Spotify Error] {e}")
            return ""

    def next_track(self):
        if not self.sp: return
        try:
            self.sp.next_track()
            return "Próxima faixa."
        except Exception as e:
            print(f"[Spotify Error] {e}")
            return ""

    def prev_track(self):
        if not self.sp: return
        try:
            self.sp.previous_track()
            return "Voltando à faixa anterior."
        except Exception as e:
            print(f"[Spotify Error] {e}")
            return ""

    def set_volume(self, volume_percent):
        if not self.sp: return
        try:
            vol = max(0, min(100, int(volume_percent)))
            self.sp.volume(vol)
            return f"Volume ajustado para {vol}%."
        except Exception as e:
            print(f"[Spotify Error] {e}")
            return ""

    def add_to_queue(self, query):
        if not self.sp: return
        try:
            clean_q = self._clean_query(query)
            results = self.sp.search(q=clean_q, type='track', limit=5)
            tracks = results['tracks']['items']
            if tracks:
                track_uri = tracks[0]['uri']
                self.sp.add_to_queue(track_uri)
                return f"Adicionado à fila: {tracks[0]['name']} de {tracks[0]['artists'][0]['name']}"
            return ""
        except Exception as e:
            print(f"[Spotify Error] {e}")
            return ""
