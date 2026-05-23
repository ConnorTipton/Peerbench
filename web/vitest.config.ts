import { defineConfig } from "vitest/config";
import path from "node:path";

export default defineConfig({
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
      // Stub Next.js's `import "server-only"` guard for unit tests — the
      // package throws on import outside a server context, but the tests
      // exercise pure logic in plain Node.
      "server-only": path.resolve(__dirname, "lib/__mocks__/server-only.ts"),
    },
  },
  test: {
    environment: "node",
    include: ["lib/**/*.test.ts"],
  },
});
