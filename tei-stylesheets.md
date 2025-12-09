# TEI to HTML Docker Container

This Docker container provides the `teitohtml` conversion tool from the TEI Stylesheets project. The container automatically clones the latest version of the TEI Stylesheets repository from GitHub during the build process.

## Building the Container

From any directory:

```bash
docker build --load -t tei-stylesheets https://github.com/TEIC/Stylesheets.git
```

Or if you have the repository locally:

```bash
docker build --load -t tei-stylesheets .
```

Note: The `--load` flag ensures the image is loaded into your local Docker daemon for immediate use.

## Usage

### Basic Usage

Convert a TEI XML file to HTML:

```bash
docker run -v $(pwd):/data tei-stylesheets teitohtml input.xml output.html
```

### Advanced Usage

Use specific profile and options:

```bash
docker run -v $(pwd):/data tei-stylesheets teitohtml \
  --profile=default \
  --lang=en \
  --verbose \
  input.xml output.html
```

### Available Options

- `--profile=PROFILE`: Transformation profile to use
- `--lang=LANG`: Language for the output
- `--verbose`: Be verbose during conversion
- `--debug`: Enable debug mode
- `--splitLevel=N`: Set splitting level for multi-file output
- `--odd`: Process ODD files

### Volume Mounting

The container expects input and output files to be available through the `/data` volume. Mount your local directory containing TEI files:

```bash
# Mount current directory
docker run -v $(pwd):/data tei-stylesheets teitohtml my-document.xml my-document.html

# Mount specific directory
docker run -v /path/to/tei/files:/data tei-stylesheets teitohtml document.xml document.html
```

### Interactive Usage

For multiple conversions or exploring the container:

```bash
docker run -it -v $(pwd):/data tei-stylesheets /bin/bash
# Then inside the container:
teitohtml --help
teitohtml document1.xml document1.html
teitohtml document2.xml document2.html
```

### Examples

1. Basic TEI to HTML conversion:
```bash
docker run -v $(pwd):/data tei-stylesheets teitohtml letter.xml letter.html
```

2. Using a specific profile:
```bash
docker run -v $(pwd):/data tei-stylesheets teitohtml --profile=enrich manuscript.xml manuscript.html
```

3. Verbose output with debugging:
```bash
docker run -v $(pwd):/data tei-stylesheets teitohtml --verbose --debug text.xml text.html
```

## Available Profiles

The container includes several transformation profiles in `/app/stylesheets/profiles/`:
- `default`: Standard TEI to HTML conversion
- `enrich`: Enhanced conversion with additional features
- Custom profiles can be added by mounting them into the container

## Supported Input Formats

The container primarily supports TEI XML files, but the underlying stylesheets also support:
- TEI P4 and P5
- TEI Lite
- Various TEI dialects

## Environment Variables

- `APPHOME`: Application home directory (set to `/app/stylesheets`)
- `SAXONJAR`: Path to Saxon JAR file
- `TRANGJAR`: Path to Trang JAR file
- `PATH`: Includes `/app/stylesheets/bin` for easy access to tools