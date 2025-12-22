# Deployment

This guide describes a live Next.js server + FastAPI deployment for `openfda-agent.snambiar.com`.

## Services

- Frontend (Next.js): `frontend/` on port `3002`
- API (FastAPI): `src/enhanced_fda_explorer` on port `8001`
- Nginx proxy: `/etc/nginx/sites-available/openfda-agent.snambiar.com`

## Frontend (Next.js)

```bash
cd /root/projects/analytics-projects/openfda-insights/frontend
npm install
npm run build
NODE_ENV=production npm run start -- -p 3002
```

`NEXT_PUBLIC_API_URL` is set to `/api` in production via `frontend/next.config.js`.

## API (FastAPI)

```bash
cd /root/projects/analytics-projects/openfda-insights
source venv/bin/activate
python3 -m src.enhanced_fda_explorer serve --port 8001
```

Ensure `.env` has the required provider keys and OpenFDA API key if needed.

## Nginx

Config: `/etc/nginx/sites-available/openfda-agent.snambiar.com`

Enable and reload:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## TLS Certificate

If the cert is not yet provisioned:

```bash
sudo certbot --nginx -d openfda-agent.snambiar.com
```

## Suggested systemd units (optional)

Create units if you want system boot persistence:

`/etc/systemd/system/openfda-agent-api.service`
```ini
[Unit]
Description=OpenFDA Insights API
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/projects/analytics-projects/openfda-insights
ExecStart=/root/projects/analytics-projects/openfda-insights/venv/bin/python -m src.enhanced_fda_explorer serve --port 8001
Restart=always
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

`/etc/systemd/system/openfda-agent-frontend.service`
```ini
[Unit]
Description=OpenFDA Insights Frontend
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/projects/analytics-projects/openfda-insights/frontend
ExecStart=/usr/bin/npm run start -- -p 3002
Restart=always
Environment=NODE_ENV=production

[Install]
WantedBy=multi-user.target
```
