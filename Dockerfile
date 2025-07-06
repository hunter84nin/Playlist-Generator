# Dockerfile

# --- Fase 1: Base Image ---
# Utilizziamo un'immagine Python ufficiale e leggera (slim) come base.
FROM python:3.10-slim

# --- Fase 2: Impostazione dell'ambiente ---
# Impostiamo la directory di lavoro all'interno del container.
WORKDIR /app

# --- Fase 3: Installazione delle dipendenze ---
# Copiamo *solo* il file delle dipendenze per sfruttare la cache di Docker.
# Questo strato verrà ricreato solo se il file requirements.txt cambia.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Fase 4: Copia dell'applicazione ---
# Copiamo il codice dell'applicazione nella directory di lavoro.
COPY app.py .

# --- Fase 5: Esposizione della porta ---
# Esponiamo la porta su cui Gunicorn ascolterà.
# L'applicazione è configurata per la porta 7860.
EXPOSE 7860

# --- Fase 6: Comando di avvio ---
# Avviamo l'applicazione usando Gunicorn, un server WSGI robusto per la produzione.
# --bind 0.0.0.0:7860: Ascolta su tutte le interfacce sulla porta 7860.
# --workers 3: Numero di processi worker per gestire le richieste (un buon punto di partenza).
# --timeout 120: Aumentiamo il timeout a 120s per gestire playlist lunghe o lente da scaricare.
# app:app: Indica a Gunicorn di cercare l'oggetto 'app' nel file 'app.py'.
CMD ["gunicorn", "--bind", "0.0.0.0:7860", "--workers", "4", "--timeout", "120", "app:app"]
