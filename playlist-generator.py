from flask import Flask, request, Response
import requests
import json
import urllib.parse

app = Flask(__name__)

def rewrite_m3u_links(m3u_content, base_url, api_password):
    """
    Riscrive i link nel contenuto M3U secondo le regole specificate,
    includendo gli headers da #EXTVLCOPT e #EXTHTTP.
    """
    lines = m3u_content.split('\n')
    rewritten_lines = []
    current_ext_headers = {} # Dizionario per conservare gli headers dalle direttive
    
    for line in lines:
        line = line.strip()
        
        is_header_tag = False
        if line.startswith('#EXTVLCOPT:'):
            is_header_tag = True
            try:
                option_str = line.split(':', 1)[1]
                if '=' in option_str:
                    key_vlc, value_vlc = option_str.split('=', 1)
                    key_vlc = key_vlc.strip()
                    value_vlc = value_vlc.strip()
 
                    # Gestione speciale per http-header che contiene "Key: Value"
                    if key_vlc == 'http-header' and ':' in value_vlc:
                        header_key, header_value = value_vlc.split(':', 1)
                        header_key = header_key.strip()
                        header_value = header_value.strip()
                        current_ext_headers[header_key] = header_value
                        print(f"ℹ️ Trovato header da #EXTVLCOPT (http-header): {{'{header_key}': '{header_value}'}}")
                    elif key_vlc.startswith('http-'):
                        # Gestisce http-user-agent, http-referer etc.
                        header_key = '-'.join(word.capitalize() for word in key_vlc[len('http-'):].split('-'))

                        current_ext_headers[header_key] = value_vlc
                        print(f"ℹ️ Trovato header da #EXTVLCOPT: {{'{header_key}': '{value_vlc}'}}")
            except Exception as e:
                print(f"⚠️ Errore nel parsing di #EXTVLCOPT '{line}': {e}")
        
        elif line.startswith('#EXTHTTP:'):
            is_header_tag = True
            try:
                json_str = line.split(':', 1)[1]
                # Sostituisce tutti gli header correnti con quelli del JSON
                current_ext_headers = json.loads(json_str)
                print(f"ℹ️ Trovati headers da #EXTHTTP: {current_ext_headers}")
            except Exception as e:
                print(f"⚠️ Errore nel parsing di #EXTHTTP '{line}': {e}")
                current_ext_headers = {} # Resetta in caso di errore

        if is_header_tag:
            rewritten_lines.append(line)
            continue
        
        # Se la linea contiene un URL (non inizia con # e non è vuota)
        if line and not line.startswith('#') and ('http://' in line or 'https://' in line):
            print(f"Processando link: {line[:100]}...")
            
            processed_url = line # Inizializza con il link originale, verrà modificato se le regole corrispondono
            
            # Controlla PRIMA se il link contiene 'vixsrc.to' (priorità alta)
            if 'vixsrc.to' in line:
                # Riscrive come extractor video per VixCloud
                processed_url = f"{base_url}/extractor/video?host=VixCloud&redirect_stream=true&api_password={api_password}&d={line}"
                print(f"✅ Riscritto VixCloud: {line[:50]}... -> {processed_url[:50]}...")
            
            # Controlla se è un link .m3u8 (anche con parametri)
            elif '.m3u8' in line:
                # Riscrive come proxy HLS
                processed_url = f"{base_url}/proxy/hls/manifest.m3u8?api_password={api_password}&d={line}"
                print(f"✅ Riscritto M3U8: {line[:50]}... -> {processed_url[:50]}...")
            
            # Controlla se è un link .mpd (anche con parametri)
            elif '.mpd' in line:
                # Riscrive come proxy MPD
                processed_url = f"{base_url}/proxy/mpd/manifest.m3u8?api_password={api_password}&d={line}"
                print(f"✅ Riscritto MPD: {line[:50]}... -> {processed_url[:50]}...")
            
            # Controlla se è un link .php (anche con parametri)
            elif '.php' in line:
                # Riscrive come extractor video
                processed_url = f"{base_url}/extractor/video?host=DLHD&redirect_stream=true&api_password={api_password}&d={line}"
                print(f"✅ Riscritto PHP: {line[:50]}... -> {processed_url[:50]}...")
            
            else:
                # Link non modificato dalle regole di riscrittura specifiche
                # 'processed_url' rimane il 'line' originale
                print(f"⚠️ Link non modificato (pattern): {line[:50]}...")

            # Applica gli headers da current_ext_headers, se presenti, a processed_url
            if current_ext_headers:
                header_params_str = ""
                for key, value in current_ext_headers.items():
                    # Formato richiesto: &h_NOMEHEADER=VALOREHEADER. Applica URL encoding a chiave e valore.
                    header_params_str += f"&h_{urllib.parse.quote(key)}={urllib.parse.quote(urllib.parse.quote(value))}" 
                
                if header_params_str: # Se sono stati formattati parametri header
                    processed_url += header_params_str
                    print(f"➕ Aggiunti headers a URL: {header_params_str} -> {processed_url[:150]}...")
                
                current_ext_headers = {} # Resetta gli headers dopo averli applicati a questa URL

            rewritten_lines.append(processed_url)
        else:
            # Mantiene le linee di metadati (#EXTM3U, #EXTINF, etc.)
            rewritten_lines.append(line)
            # Non resettare current_exthttp_headers qui; devono persistere per la prossima URL se non ancora usati.
    
    return '\n'.join(rewritten_lines)

def rewrite_m3u_links_streaming(m3u_lines_iterator, base_url, api_password):
    """
    Riscrive i link da un iteratore di linee M3U secondo le regole specificate,
    includendo gli headers da #EXTVLCOPT e #EXTHTTP. Yields rewritten lines.
    """
    current_ext_headers = {} # Dizionario per conservare gli headers dalle direttive
    
    for line_with_newline in m3u_lines_iterator:
        line_content = line_with_newline.rstrip('\n')
        logical_line = line_content.strip()
        
        is_header_tag = False
        if logical_line.startswith('#EXTVLCOPT:'):
            is_header_tag = True
            try:
                option_str = logical_line.split(':', 1)[1]
                if '=' in option_str:
                    key_vlc, value_vlc = option_str.split('=', 1)
                    key_vlc = key_vlc.strip()
                    value_vlc = value_vlc.strip()
 
                    # Gestione speciale per http-header che contiene "Key: Value"
                    if key_vlc == 'http-header' and ':' in value_vlc:
                        header_key, header_value = value_vlc.split(':', 1)
                        header_key = header_key.strip()
                        header_value = header_value.strip()
                        current_ext_headers[header_key] = header_value
                        print(f"ℹ️ Trovato header da #EXTVLCOPT (http-header): {{'{header_key}': '{header_value}'}}")
                    elif key_vlc.startswith('http-'):
                        # Gestisce http-user-agent, http-referer etc.
                        header_key = '-'.join(word.capitalize() for word in key_vlc[len('http-'):].split('-'))
                    
                        current_ext_headers[header_key] = value_vlc
                        print(f"ℹ️ Trovato header da #EXTVLCOPT: {{'{header_key}': '{value_vlc}'}}")
            except Exception as e:
                print(f"⚠️ Errore nel parsing di #EXTVLCOPT '{logical_line}': {e}")
        
        elif logical_line.startswith('#EXTHTTP:'):
            is_header_tag = True
            try:
                json_str = logical_line.split(':', 1)[1]
                # Sostituisce tutti gli header correnti con quelli del JSON
                current_ext_headers = json.loads(json_str)
                print(f"ℹ️ Trovati headers da #EXTHTTP: {current_ext_headers}")
            except Exception as e:
                print(f"⚠️ Errore nel parsing di #EXTHTTP '{logical_line}': {e}")
                current_ext_headers = {} # Resetta in caso di errore

        if is_header_tag:
            yield line_with_newline
            continue
        
        if logical_line and not logical_line.startswith('#') and \
           ('http://' in logical_line or 'https://' in logical_line):
            print(f"Processando link: {logical_line[:100]}...")
            
            # Decide la logica di riscrittura in base alla presenza della password
            if api_password is not None:
                # --- LOGICA CON PASSWORD (ESISTENTE) ---
                processed_url_content = logical_line
                
                if 'vixsrc.to' in logical_line:
                    processed_url_content = f"{base_url}/extractor/video?host=VixCloud&redirect_stream=true&api_password={api_password}&d={logical_line}"
                    print(f"✅ Riscritto VixCloud: {logical_line[:50]}... -> {processed_url_content[:50]}...")
                elif '.m3u8' in logical_line:
                    processed_url_content = f"{base_url}/proxy/hls/manifest.m3u8?api_password={api_password}&d={logical_line}"
                    print(f"✅ Riscritto M3U8: {logical_line[:50]}... -> {processed_url_content[:50]}...")
                elif '.mpd' in logical_line:
                    processed_url_content = f"{base_url}/proxy/mpd/manifest.m3u8?api_password={api_password}&d={logical_line}"
                    print(f"✅ Riscritto MPD: {logical_line[:50]}... -> {processed_url_content[:50]}...")
                elif '.php' in logical_line:
                    processed_url_content = f"{base_url}/extractor/video?host=DLHD&redirect_stream=true&api_password={api_password}&d={logical_line}"
                    print(f"✅ Riscritto PHP: {logical_line[:50]}... -> {processed_url_content[:50]}...")
                else:
                    # Link non modificato dalle regole, ma gli header potrebbero essere aggiunti
                    print(f"⚠️ Link non modificato (pattern): {logical_line[:50]}...")
            else:
                # --- NUOVA LOGICA SENZA PASSWORD ---
                processed_url_content = f"{base_url}/proxy/m3u?url={logical_line}"
                print(f"✅ Riscritto (senza password): {logical_line[:50]}... -> {processed_url_content[:50]}...")
            # Applica gli header raccolti, indipendentemente dalla modalità
            if current_ext_headers:
                header_params_str = "".join([f"&h_{urllib.parse.quote(key)}={urllib.parse.quote(urllib.parse.quote(value))}" for key, value in current_ext_headers.items()])
                processed_url_content += header_params_str
                print(f"➕ Aggiunti headers a URL: {header_params_str} -> {processed_url_content[:150]}...")
                current_ext_headers = {}
            
            yield processed_url_content + '\n'
        else:
            yield line_with_newline
            
def download_m3u_playlist_streaming(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive'
        }
        
        print(f"Scaricamento (streaming) da: {url}")
        # verify=False is generally not recommended for production
        with requests.get(url, headers=headers, timeout=30, verify=False, stream=True) as response:
            print(f"Status code: {response.status_code}")
            print(f"Headers risposta (prime parti): {{k: v[:100] for k, v in dict(response.headers).items()}}") # Log snippet of headers
            response.raise_for_status()
            for line_bytes in response.iter_lines():
                decoded_line = line_bytes.decode('utf-8', errors='replace')
                # Explicitly check for and skip empty lines after decoding
                yield decoded_line + '\n' if decoded_line else ''
        
    except requests.RequestException as e:
        print(f"Errore download (streaming): {str(e)}")
        raise Exception(f"Errore nel download (streaming) della playlist: {str(e)}")
    except Exception as e:
        print(f"Errore generico durante lo streaming del download da {url}: {str(e)}")
        raise

@app.route('/proxy')
def proxy_handler():
    try:
        query_string = request.query_string.decode('utf-8')
        print(f"=== DEBUG PROXY ===")
        print(f"Query string: {query_string}")

        if not query_string:
            return "Query string mancante", 400

        playlist_definitions = query_string.split(';')

        def generate_combined_playlist():
            first_playlist_header_handled = False # Tracks if the main #EXTM3U header context is done
            total_bytes_yielded = 0
            log_interval_bytes = 10 * 1024 * 1024 # Log every 10MB
            last_log_bytes_milestone = 0

            for definition_idx, definition in enumerate(playlist_definitions):
                if '&' not in definition:
                    print(f"[{definition_idx}] Skipping invalid playlist definition (manca '&'): {definition}")
                    yield f"# SKIPPED Invalid Definition: {definition}\n"
                    continue

                parts = definition.split('&', 1)
                creds_part, playlist_url_str = parts
                
                api_password = None
                base_url_part = creds_part

                # Heuristics to distinguish domain:port or scheme:// from domain:password
                if ':' in creds_part:
                    possible_base, possible_pass = creds_part.rsplit(':', 1)
                    
                    # A password is assumed if the part after the last colon is not a port (all digits)
                    # and does not start with '//' (which would mean we split a URL scheme like http://)
                    if not possible_pass.startswith('//') and not possible_pass.isdigit():
                        base_url_part = possible_base
                        api_password = possible_pass
                
                if api_password is not None:
                    print(f"  [{definition_idx}] Base URL: {base_url_part}, Password: {'*' * len(api_password)}")
                else:
                    # Nessuna password fornita (o la parte dopo ':' era una porta/scheme)
                    print(f"  [{definition_idx}] Base URL: {base_url_part}, Modalità senza password.")

                base_url_part = base_url_part.rstrip('/')
                print(f"[{definition_idx}] Processing Playlist (streaming): {playlist_url_str}")

                current_playlist_had_lines = False
                first_line_of_this_segment = True
                lines_processed_for_current_playlist = 0
                try:
                    downloaded_lines_iter = download_m3u_playlist_streaming(playlist_url_str)
                    print(f"  [{definition_idx}] Download stream initiated for {playlist_url_str}")
                    rewritten_lines_iter = rewrite_m3u_links_streaming(
                        downloaded_lines_iter, base_url_part, api_password
                    )
                    
                    for line in rewritten_lines_iter:
                        current_playlist_had_lines = True
                        is_extm3u_line = line.strip().startswith('#EXTM3U')
                        lines_processed_for_current_playlist += 1

                        if not first_playlist_header_handled: # Still in the context of the first playlist's header
                            yield line
                            if is_extm3u_line:
                                first_playlist_header_handled = True  # Main header yielded
                            
                            line_bytes = len(line.encode('utf-8', 'replace')) # Use 'replace' for safety
                            total_bytes_yielded += line_bytes
                            
                            if total_bytes_yielded // log_interval_bytes > last_log_bytes_milestone:
                                last_log_bytes_milestone = total_bytes_yielded // log_interval_bytes
                                print(f"ℹ️ [{definition_idx}] Total data yielded: {total_bytes_yielded / (1024*1024):.2f} MB. Current playlist lines: {lines_processed_for_current_playlist}")

                            if len(line) > 10000: 
                                print(f"⚠️ [{definition_idx}] VERY LONG LINE encountered (length={len(line)}, lines in current playlist={lines_processed_for_current_playlist}): {line[:100]}...")


                        else: # Main header already handled (or first playlist didn't have one)
                            if first_line_of_this_segment and is_extm3u_line:
                                # Skip #EXTM3U if it's the first line of a subsequent segment
                                pass
                            else:
                                yield line
                        first_line_of_this_segment = False

                        # This block for logging and length check was duplicated, ensure it's correctly placed for all yielded lines
                        if first_playlist_header_handled: # If not the first header part, calculate bytes and log here too
                            line_bytes = len(line.encode('utf-8', 'replace'))
                            total_bytes_yielded += line_bytes
                            if total_bytes_yielded // log_interval_bytes > last_log_bytes_milestone:
                                last_log_bytes_milestone = total_bytes_yielded // log_interval_bytes
                                print(f"ℹ️ [{definition_idx}] Total data yielded: {total_bytes_yielded / (1024*1024):.2f} MB. Current playlist lines: {lines_processed_for_current_playlist}")
                            if len(line) > 10000:
                                print(f"⚠️ [{definition_idx}] VERY LONG LINE encountered (length={len(line)}, lines in current playlist={lines_processed_for_current_playlist}): {line[:100]}...")

                except Exception as e:
                    print(f"💥 [{definition_idx}] Error processing playlist {playlist_url_str} (after ~{lines_processed_for_current_playlist} lines yielded for it): {str(e)}")
                    yield f"# ERROR processing playlist {playlist_url_str}: {str(e)}\n"
                
                print(f"✅ [{definition_idx}] Finished processing playlist {playlist_url_str}. Lines processed in this segment: {lines_processed_for_current_playlist}")
                if current_playlist_had_lines and not first_playlist_header_handled:
                    # This playlist (which was effectively the first with content) finished,
                    # and no #EXTM3U was found to mark as the main header.
                    # Mark header as handled so subsequent playlists skip their #EXTM3U.
                    first_playlist_header_handled = True
        
        print(f"🏁 Avvio streaming del contenuto combinato... (Total definitions: {len(playlist_definitions)})")
        # The final total_bytes_yielded will be known only if the generator completes fully.
        return Response(
            generate_combined_playlist(),
            mimetype='application/vnd.apple.mpegurl',
            headers={
                'Content-Disposition': 'attachment; filename="playlist.m3u"',
                'Access-Control-Allow-Origin': '*'
            }
        )
        
    except Exception as e:
        print(f"ERRORE GENERALE: {str(e)}")
        import traceback
        traceback.print_exc()
        return f"Errore: {str(e)}", 500

@app.route('/') # Imposta /builder come pagina iniziale
@app.route('/builder')
def url_builder():
    """
    Pagina con un'interfaccia per generare l'URL del proxy.
    """
    html_content = """
    <!DOCTYPE html>
    <html lang="it">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>URL Builder - Server Proxy M3U</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; background-color: #f5f5f5; }
            .container { background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            h1 { color: #333; text-align: center; margin-bottom: 30px; }
            h2 { color: #2c5aa0; border-bottom: 2px solid #2c5aa0; padding-bottom: 5px; text-align: left; margin-top: 30px; }
            .form-group { margin-bottom: 15px; }
            label { display: block; margin-bottom: 5px; font-weight: bold; color: #555; }
            input[type="text"], input[type="url"] { width: 100%; padding: 10px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }
            .btn { display: inline-block; padding: 10px 20px; background: #2c5aa0; color: white; text-decoration: none; border-radius: 5px; margin: 5px; cursor: pointer; border: none; font-size: 16px; }
            .btn:hover { background: #1e3d6f; }
            .btn-add { background-color: #28a745; }
            .btn-remove { background-color: #dc3545; padding: 5px 10px; font-size: 12px; }
            .playlist-entry { background: #f8f9fa; padding: 20px; border-radius: 5px; margin-bottom: 15px; border-left: 4px solid #17a2b8; position: relative; }
            .output-area { margin-top: 20px; }
            #generated-url { background: #e9ecef; padding: 10px; border: 1px solid #ced4da; border-radius: 4px; font-family: 'Courier New', monospace; word-break: break-all; min-height: 50px; white-space: pre-wrap; }
            .home-link { text-align: center; margin-top: 20px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔗 URL Builder per Proxy M3U</h1>
            
            <div class="form-group">
                <label for="server-address">Indirizzo del tuo Server Proxy</label>
                <input type="text" id="server-address" placeholder="Indirizzo del server corrente" value="" readonly style="background-color: #e9ecef;">
            </div>

            <h2>Playlist da Unire</h2>
            <div id="playlist-container">
                <!-- Le playlist verranno aggiunte qui dinamicamente -->
            </div>

            <button type="button" class="btn btn-add" onclick="addPlaylistEntry()">Aggiungi Playlist</button>
            <hr style="margin: 20px 0;">

            <button type="button" class="btn" onclick="generateUrl()">Genera URL</button>

            <div class="output-area">
                <label for="generated-url">URL Generato</label>
                <div id="generated-url">L'URL apparirà qui...</div>
                <button type="button" class="btn" onclick="copyUrl()">Copia URL</button>
            </div>

            <div class="home-link" style="display: none;"> <!-- Nascondi il pulsante "Torna alla Home" -->
                <a href="/" class="btn">Torna alla Home</a>
            </div>
        </div>

        <!-- Template per una singola playlist -->
        <template id="playlist-template">
            <div class="playlist-entry">
                <button type="button" class="btn btn-remove" style="position: absolute; top: 10px; right: 10px;" onclick="this.parentElement.remove()">Rimuovi</button>
                <div class="form-group">
                    <label>Dominio (MFP o TvProxy, con porta se necessario)</label>
                    <input type="text" class="dominio" placeholder="Es: https://mfp.com oppure https://tvproxy.com">
                </div>
                <div class="form-group">
                    <label>Password API</label>
                    <input type="text" class="password" placeholder="Obbligatoria per MFP, lasciare vuoto per TvProxy">
                    <small style="color: #6c757d; display: block; margin-top: 4px;">
                        <b>MFP:</b> Inserire la password. <br><b>TvProxy:</b> Lasciare vuoto.</small>
                </div>
                <div class="form-group">
                    <label>URL della Playlist M3U</label>
                    <input type="url" class="playlist-url" placeholder="Es: http://provider.com/playlist.m3u">
                </div>
            </div>
        </template>

        <script>
            document.addEventListener('DOMContentLoaded', function() {
                // Imposta l'indirizzo del server di default
                document.getElementById('server-address').value = window.location.origin;
                // Aggiunge una playlist di default all'avvio
                addPlaylistEntry();
            });

            function addPlaylistEntry() {
                const template = document.getElementById('playlist-template').content.cloneNode(true);
                document.getElementById('playlist-container').appendChild(template);
            }

            function generateUrl() {
                const serverAddress = document.getElementById('server-address').value.trim().replace(/\\/$/, '');
                if (!serverAddress) {
                    alert('Indirizzo del server non disponibile. Ricarica la pagina.');
                    return;
                }

                const entries = document.querySelectorAll('.playlist-entry');
                const definitions = [];

                entries.forEach(entry => {
                    const dominio = entry.querySelector('.dominio').value.trim();
                    const password = entry.querySelector('.password').value.trim();
                    const playlistUrl = entry.querySelector('.playlist-url').value.trim();

                    if (dominio && playlistUrl) {
                        let credsPart = dominio;
                        if (password) {
                            credsPart += ':' + password;
                        }
                        definitions.push(credsPart + '&' + playlistUrl);
                    }
                });

                if (definitions.length === 0) {
                    document.getElementById('generated-url').textContent = 'Nessuna playlist valida inserita.';
                    return;
                }

                const finalUrl = serverAddress + '/proxy?' + definitions.join(';');
                document.getElementById('generated-url').textContent = finalUrl;
            }

            function copyUrl() {
                const urlText = document.getElementById('generated-url').textContent;
                if (urlText && !urlText.startsWith('L\\'URL') && !urlText.startsWith('Nessuna')) {
                    navigator.clipboard.writeText(urlText).then(() => {
                        alert('URL copiato negli appunti!');
                    }).catch(err => {
                        alert('Errore durante la copia: ' + err);
                    });
                } else {
                    alert('Nessun URL da copiare.');
                }
            }
        </script>
    </body>
    </html>
    """
    return html_content

if __name__ == '__main__':
    print("Avvio del server proxy M3U...")
    print("Formato URL per singola playlist (esempio): http://localhost:7860/proxy?https://mfp.com:pass123&http://provider.com/playlist.m3u")
    print("Formato URL per multiple playlist (esempio misto): http://localhost:7860/proxy?https://dom1.com:pass1&url1.m3u;https://dom2.com&url2.m3u")
    # Rimosso print per /test
    
    # Avvia il server
    app.run(host='0.0.0.0', port=7860, debug=False)