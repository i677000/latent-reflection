# Black (Latent Reflection)

Local-network art installation that renders short reflective phrases on a phone as a passive display object.

## What it is
- A local LLM generates short phrases
- A FastAPI backend sanitizes, times, and styles them
- A PWA frontend renders the text fullscreen with subtle effects
- Designed for LAN only, no public exposure by default

## Status
Prototype / art object. Intended for local network use only.

## Run (LAN only)
```bash
cd ~/black/latent-reflection
docker compose up -d --build
# pull model once
docker compose exec ollama ollama pull llama3.2:3b
```

Open on phone: `http://<host-lan-ip>:3000`

## Prompt control
Edit `backend/prompt.txt`. Changes are applied on the next API request (no rebuild required).

## Notes on safety
This project is **not** safe for public internet exposure in its current form. If you want to publish it online, add authentication, rate limiting, and TLS.

## License
- Code: MIT (or replace with your preferred license)
- Font: Ruslan Display (see `frontend/fonts/Ruslan_Display/OFL.txt`)

## Structure
```
latent-reflection/
  docker-compose.yml
  backend/
    app.py
    prompt.txt
    fallback.txt
  frontend/
    index.html
    styles.css
    app.js
```
