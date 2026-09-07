# 4Diagnosis Speech Recorder

Aplikacja wspierająca lekarzy patomorfologów w nagrywaniu głosowych notatek i generowaniu strukturalnych opisów makroskopowych. Umożliwia zarządzanie pacjentami, badaniami i nagraniami audio z przeszukiwalną historią.

## Architektura

Projekt składa się z trzech głównych komponentów:

- **Frontend**: React SPA z nowoczesnym UI (TypeScript + Tailwind CSS)
- **Backend STT**: Django + Channels dla strumieniowej transkrypcji głosu (Whisper)
- **REST API**: Django REST Framework dla zarządzania danymi

### Wymagania wstępne

- **Node.js** (wersja 18+)
- **Bun** (runtime JavaScript)
- **Python** (wersja 3.8+)
- **pip** (menedżer pakietów Python)
- **Redis** (dla WebSocket)
- **ffmpeg** (dla przetwarzania audio)

### Instalacja i uruchomienie

#### 1. Klonowanie repozytorium

```bash
git clone <repository-url>
cd 4Diagnosis_SpeechRecorder
```

#### 2. Stworzenie pliku z kluczami środowiskowymi
Utwórz plik `.env` w katalogu `backend` z następującą zawartością:

```bash
OPENROUTER_API_KEY='twoj_klucz_openrouter'
```

lub:

```bash
OPENAI_API_KEY='twoj_klucz_openai'
```

#### 3. Frontend (React + Bun)

```bash
# Przejdź do katalogu frontendu
cd app

# Zainstaluj zależności
bun install

# Uruchom serwer deweloperski
bun dev
```

Frontend będzie dostępny na `http://localhost:3010`

#### 4. Backend (Django)

```bash
# Przejdź do katalogu backendu
cd backend

# Utwórz virtual environment
python3 -m venv venv

# Aktywuj virtual environment (Linux)
source venv/bin/activate
# Albo na Windowsie .\venv\Scripts\Activate.ps1 

# Zainstaluj zależności
pip install -r requirements.txt

# Jeśli masz problemy z PyTorch (torch._C), przeinstaluj:
pip uninstall torch torchvision torchaudio
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# Uruchom kontener Qdrant (z głównego katalogu repozytorium)
docker-compose up qdrant -d

# Przeprowadź migrację bazy Qdranta (z src/)
python manage.py index_qdrant

# Przeprowadź migracje bazy danych
python src/manage.py migrate

# Uruchom serwer Django (ASGI dla WebSocket)
# Aktywuj virtual environment
source venv/bin/activate
# albo na Windowsie .\venv\Scripts\Activate.ps1 

# Opcja 1: Uruchom z katalogu src/
cd src && daphne -p 8000 stt.asgi:application

# Opcja 2: Uruchom z katalogu backend/ z PYTHONPATH
PYTHONPATH=src daphne -p 8000 stt.asgi:application
```

Backend będzie dostępny na `http://localhost:8000`

**Uwaga:** Przy pierwszym uruchomieniu backend automatycznie pobierze i załaduje model Whisper (może zająć kilka minut). W logach zobaczysz komunikaty:
- "🔄 Ładowanie processora Whisper..."
- "🔄 Ładowanie modelu Whisper..."

### ✅ Weryfikacja działania

Po uruchomieniu obu części sprawdź czy wszystko działa:

```bash
# Sprawdź frontend
curl -I http://localhost:3010

# Sprawdź backend (powinien odpowiadać)
curl http://localhost:8000
```

### 🔧 Konfiguracja

#### Frontend
Konfiguracja WebSocket i Audio znajduje się w:
- `app/src/config.ts`

Dodatkowa konfiguracja dotycząca resamplingu jest w:
- `app/src/audio-worklets/BaseProcessor.ts`

Aplikacja jest domyślnie skonfigurowana do używania portu 8000 dla backendu.
W przypadku wysyłania audio, frontend normalizuje sample rate do 16000 Hz.

#### Backend
Główne ustawienia w `backend/src/stt/settings.py`:
- Baza danych: SQLite (domyślnie)
- Redis: dla Channels/WebSocket
- Debug mode: włączony dla developmentu

## 📁 Struktura projektu

```
4Diagnosis_SpeechRecorder/
├── app/                    # Frontend (React + Bun)
│   ├── src/
|   |   ├── audio-worklets # Worklety do grafu przetwarzania dźwięku
│   │   ├── components/    # Komponenty React
│   │   ├── pages/         # Strony aplikacji
│   │   ├── lib/           # Logika biznesowa
│   │   ├── contexts/      # React contexts
|   |   ├── utils/         # Funkcjonalności pomocnicze
|   |   ├── types/         # Typy TypeScript
|   |   └── hooks/         # Custom hooki Reacta
│   ├── package.json
│   └── tsconfig.json
├── backend/               # Backend (Django)
│   ├── src/
│   │   ├── app_stt/       # Główna aplikacja Django
│   │   ├── stt/           # Ustawienia projektu
│   │   └── utils/         # Narzędzia audio
│   ├── requirements.txt
│   └── pytest.ini
├── README.md
└── PROJECT_SCOPE.md       # Szczegółowy zakres projektu
```

## 🔄 Kluczowe funkcjonalności

### Nagrywanie i transkrypcja
- Strumieniowe nagrywanie audio przez WebSocket
- Ekstrakcja Named-Entity Recognition elementów badania
- Korygowanie tekstu przez LLM
- Generowanie strukturalnych opisów makroskopowych

### Zarządzanie danymi
- CRUD dla pacjentów, badań i nagrań
- Przeszukiwalna historia nagrań
- Zarządzanie metadanymi i plikami audio

## 🧪 Testowanie

### Frontend
```bash
cd app
bun run build  # Sprawdź czy build przechodzi
```

### Backend
```bash
cd backend
source venv/bin/activate # windows .\venv\Scripts\Activate.ps1 
python src/manage.py test
```

## 🤝 Przyczynianie się

1. Fork repozytorium
2. Utwórz branch dla nowej funkcjonalności
3. Zrób commit zmian
4. Wyślij pull request

