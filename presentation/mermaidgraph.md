---
marp: true
---

<div class ="mermaid">
graph LR
    B[(SNOW CMDB)]
    A((Start)) -.-> E
    E(Pull Device Serials) --> C{Clean Data}
    B --> E
    C --> |Send API Request| D[OEM API]
    D --> |Update Records based on API resposes| B
</div>
