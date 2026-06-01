# KESSLER ZERO-TRUST DOCKERFILE

# Stage 1: The Forge (Build)
FROM alpine:edge AS builder
RUN apk add --no-cache zig=0.13.0-r0 # (Alpine edge will update to 0.16.0)
WORKDIR /kessler
COPY . .
# Compile the static release binary
RUN zig build -Doptimize=ReleaseFast -Dtarget=x86_64-linux-musl

# Stage 2: The Enclave (Run)
FROM alpine:latest
WORKDIR /opt/kessler
# Only bring over the compiled binary and the config templates
COPY --from=builder /kessler/zig-out/bin/kessler /usr/local/bin/kessler
COPY --from=builder /kessler/config/ ./config/

# Non-root user for security compliance
RUN addgroup -S quant && adduser -S quant -G quant
USER quant

# Mount points for custom scenarios and telemetry output
VOLUME ["/opt/kessler/config/scenarios", "/opt/kessler/output"]

ENTRYPOINT ["kessler"]
CMD ["--config", "config/default.yaml"]
