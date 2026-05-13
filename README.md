# karakeep-opds

Standalone bridge that exposes [Karakeep](https://github.com/karakeep-app/karakeep)
bookmarks as OPDS feeds for OPDS-capable readers.

## Features

- OPDS 1.2 Atom feeds at `/opds`
- OPDS 2 JSON feeds at `/opds2`
- Recent bookmarks and search feeds
- Supports Karakeep `link` and `text` bookmarks
- Generates minimal EPUB files for OPDS acquisition links
- Keeps Karakeep API token server-side

Asset bookmarks such as images and PDFs are skipped in this first version.

## Configuration

Copy `.env.example` to `.env` and set:

| Variable | Required | Description |
| --- | --- | --- |
| `KARAKEEP_BASE_URL` | yes | Karakeep origin, for example `https://karakeep.example.com` |
| `KARAKEEP_API_TOKEN` | yes | API key from Karakeep Settings > API Keys |
| `KARAKEEP_API_PATH` | no | API prefix, default `/api/v1`; set empty only if your reverse proxy already routes API root |
| `OPDS_USERNAME` | yes | Username entered in your OPDS reader |
| `OPDS_PASSWORD` | yes | Password entered in your OPDS reader; any non-empty value |
| `OPDS_PAGE_SIZE` | no | Page size sent to Karakeep, default `50` |
| `SERVICE_BASE_URL` | no | Public origin for generated links behind reverse proxies |

## Quick Setup

Create your `.env` file, then create a `docker-compose.yml`:

```yaml
services:
  karakeep-opds:
    image: ghcr.io/yazdipour/karakeep-opds:latest
    ports:
      - "8000:8000"
    env_file: .env
```
Run `docker compose up -d`.

## Run locally

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
uvicorn karakeep_opds.app:app --reload
```

## Run with Docker

You can run the application using the pre-built Docker image from GHCR using `docker-compose`. Create a `.env` file first as shown above.

Using the pre-built image (GHCR):
```bash
docker run -d \
  --name karakeep-opds \
  --env-file .env \
  -p 8000:8000 \
  ghcr.io/karakeep-app/karakeep-opds:latest
```

Using Docker Compose:
```bash
docker compose up -d
```

If you prefer to build the image locally from source, run:

```bash
docker compose up --build
```

## OPDS URLs

Use these URLs in your OPDS reader:

- OPDS 1.2 catalog: `https://opds.example.com/opds`
- OPDS 1.2 recent: `https://opds.example.com/opds/recent`
- OPDS 1.2 search: `https://opds.example.com/opds/search?q=query`
- OPDS 2 catalog: `https://opds.example.com/opds2`

When prompted by the reader, enter `OPDS_USERNAME` and `OPDS_PASSWORD`.
Put this service behind HTTPS or Tailscale because HTTP Basic credentials are only
encoded, not encrypted, on plain HTTP.

## Development

```bash
pytest
ruff check .
```

## AI Acknowledgment

This project was built with the assistance of AI tools for code generation and refactoring.

## License

This project is licensed under the [GNU General Public License v3.0 (GPLv3)](LICENSE).
