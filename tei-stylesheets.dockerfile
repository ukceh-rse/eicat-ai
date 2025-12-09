# Use a lightweight Linux base image with Java
FROM eclipse-temurin:11-jre-jammy

# Set maintainer information
LABEL maintainer="TEI Stylesheets Docker Container"
LABEL description="Docker container for TEI Stylesheets teitohtml conversion tool"

# Install required system packages
RUN apt-get update && apt-get install -y \
    ant \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create application directory
WORKDIR /app

# Clone the Stylesheets repository
RUN git clone https://github.com/TEIC/Stylesheets.git stylesheets

# Set working directory to stylesheets
WORKDIR /app/stylesheets

# Ensure the bin scripts are executable
RUN chmod +x bin/*

# Set environment variables
ENV APPHOME=/app/stylesheets
ENV SAXONJAR=/app/stylesheets/lib/saxon10he.jar
ENV TRANGJAR=/app/stylesheets/lib/trang.jar
ENV PATH="/app/stylesheets/bin:${PATH}"

# Verify the required JAR files exist
RUN test -f "$SAXONJAR" || (echo "ERROR: Saxon JAR not found at $SAXONJAR" && exit 1)
RUN test -f "$TRANGJAR" || (echo "ERROR: Trang JAR not found at $TRANGJAR" && exit 1)

# Create a directory for input and output files
RUN mkdir -p /data/input /data/output
WORKDIR /data

# Set the default command to show usage
CMD ["teitohtml", "--help"]

# Expose volume for input/output files
VOLUME ["/data"]