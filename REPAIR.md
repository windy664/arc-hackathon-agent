# ARC 模型代理故障修复（2026-09-29）

本包恢复 `arc_main.py` 的真实 ARC 编译入口为 `main.py`，替换原来的固定页面生成器。
修复对应日志：`REQ-2-1-1` 的 TestGenerator 请求模型时遇到 HTTP 400 / proxy_error /
connection reset by peer，流回退后再次失败并退出。

- 在模型请求层重试，不重新运行已经执行过工具的整个阶段。
- 仅重试传输异常、408/429、常见暂时性 5xx，以及明确包含连接故障的 proxy_error 400。
- 默认每次模型调用最多尝试 2 次（包括首次）；指数退避加少量随机延迟。
- 默认请求超时 300 秒；异步请求还具有整体时间限制。同步调用使用客户端网络超时。
- 默认单个 DESIGN/IMPLEMENT 阶段最多 1800 秒。
- 重试耗尽仍报告失败，保存队列与产物；中断任务保留 RUNNING，供已有恢复逻辑处理。
- 不修改测试判分，不伪造通过，不自动改用其他网关或模型。

可通过 `ARC_MODEL_MAX_ATTEMPTS`、`ARC_MODEL_REQUEST_TIMEOUT`、`ARC_PHASE_TIMEOUT`
配置尝试次数、请求超时秒数、阶段超时秒数。

上传 ZIP 时选择 Python，包根目录包含 main.py 和 requirements.txt。
模型、Base URL、比赛额度仍在平台提交表单配置，包内不包含密钥。

只有原工作区仍然存在时，才能恢复：

```sh
python3 main.py /path/to/requirements --output-dir /path/to/existing-workspace --resume
```

新的平台运行如果创建全新容器/工作区，不会自动找回旧运行的产物。
本地故障注入测试不调用真实模型；仍需平台验证实际网关与完整生成/评测流程。
