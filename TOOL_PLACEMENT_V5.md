# Tool placement V5

| Placement | Execution | STRICT requirement |
| --- | --- | --- |
| `TEE_LOCAL` | inside attested confidential boundary | allowed |
| `CLOUD_LOCAL` | named ordinary cloud process | reject unless moved into TEE, confidential/common broker, or Gateway |
| `EXTERNAL` | downstream provider | CommonActionGateway with the STRICT outer profile |

The profile validator fails closed for unbrokered `CLOUD_LOCAL` activation in
STRICT. `ENTERPRISE_EFFICIENT` accepts it only with an explicit public Tool
category. Encrypted arguments do not hide a named endpoint. This audit does not
claim global destination privacy or confidential-GPU/resource privacy.
