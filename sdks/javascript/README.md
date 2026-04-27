# EYDII JavaScript SDK

The trustless verification layer for autonomous systems. Content-blind. Mathematical.

## Install

```bash
npm install @veritera.ai/eydii
```

## Usage

```typescript
import { Veritera } from "@veritera.ai/eydii";

const eydii = new Veritera({ apiKey: process.env.EYDII_API_KEY });

const result = await eydii.verify({
  agentId: "analyst",
  actionType: "file_write",
  context: { path: "/reports/q1.md" },
});

if (result.allowed) {
  // proceed
}
```

## Requirements

- Node.js 18+
- TypeScript 5+ (optional)

## Get Your API Key

Sign up at [id.veritera.ai](https://id.veritera.ai).

## Documentation

Full documentation at [veritera.ai](https://veritera.ai).

## License

MIT -- see [LICENSE](../../LICENSE).
