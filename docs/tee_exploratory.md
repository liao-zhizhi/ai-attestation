# TEE 探索性原型说明

见代码模块 `backend/app/tee_stub.py`。

本文档与 stub 同步：TEE **不做产品化集成**。设置环境变量 `ATA_TEE_MODE=exploratory` 后，合规验证包可附带 stub attestation 字段，仅用于演示文档形状。

完整背景、退出标准与假设架构见该模块顶部 docstring，以及本目录 `zkp_feasibility.md` 中关于「防篡改深化」的优先级讨论（时间戳/锚定优先于 TEE/ZKP）。
