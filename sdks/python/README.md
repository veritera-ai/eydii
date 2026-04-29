# EYDII Python SDK

The trustless verification layer for autonomous systems. Content-blind. Mathematical.

## Install

```bash
pip install veritera
```

## Usage

```python
import os
from veritera import EydiiClient

eydii = EydiiClient(api_key=os.environ["EYDII_API_KEY"])

result = eydii.verify(
    agent_id="analyst",
    action_type="file_write",
    context={"path": "/reports/q1.md"},
)

if result.allowed:
    # proceed
    pass
```

## Requirements

- Python 3.9+

## Get Your API Key

Sign up at [id.veritera.ai](https://id.veritera.ai).

## Documentation

Full documentation at [veritera.ai](https://veritera.ai).

## License

Proprietary — see [LICENSE](../../LICENSE). All rights reserved by Veritera Corporation.
