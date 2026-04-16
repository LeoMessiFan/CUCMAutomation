# schema/

This directory must contain the Cisco AXL WSDL schema files.

These files are **not included in the repository** — they come with the Cisco AXL SDK (axlsqltoolkit), available from Cisco DevNet.

## Required Files

- `AXLAPI.wsdl`
- `AXLEnums.xsd`
- `AXLSoap.xsd`

## How to Add

Copy from your local axlsqltoolkit installation:

```bash
cp /path/to/axlsqltoolkit/schema/current/AXLAPI.wsdl  schema/
cp /path/to/axlsqltoolkit/schema/current/AXLEnums.xsd  schema/
cp /path/to/axlsqltoolkit/schema/current/AXLSoap.xsd   schema/
```
