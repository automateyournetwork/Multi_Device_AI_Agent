FROM ollama/ollama

# Install curl for health checks
RUN apt-get update && apt-get install -y curl

# Copy the init.sh script
COPY scripts/init.sh /init.sh
RUN chmod +x /init.sh

# Override the entrypoint to run the init script
ENTRYPOINT ["/init.sh"]