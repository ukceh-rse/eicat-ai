# TEI to HTML API

FastAPI service that converts TEI XML files to HTML using TEI Stylesheets.

## Building

```bash
docker build -t tei-api .
```

## Running

```bash
docker run -p 8000:8000 tei-api
```

## Usage

Upload a TEI XML file to convert it to HTML:

```bash
curl -X POST "http://localhost:8000/tei2html" \
     -F "file=@document.xml"
```

Returns the converted HTML content directly.