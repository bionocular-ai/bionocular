import { registerOTel } from '@vercel/otel';

/**
 * Registers the OpenTelemetry tracer the AI SDK's `experimental_telemetry`
 * writes to. Spans go wherever the standard `OTEL_EXPORTER_OTLP_*` variables
 * point; with none set they are created and dropped, which costs nothing. The
 * agent's run records and tool log lines do not depend on this.
 */
export function register() {
  registerOTel({ serviceName: 'bionocular-web' });
}
