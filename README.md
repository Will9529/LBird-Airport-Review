# LBird机场测评 (LBird-Airport-Review)

> [!CAUTION]
> **纯技术学习研究声明 · 不构成任何建议**  
> 本仓库的所有代码、采集脚本、统计指标与自动化输出数据**仅用于网络探测、协议解析、异步爬虫工程与自动化可观测性技术学习**，**不构成任何购买、使用、推荐或投资建议**。  
> 本仓库**不提供、不托管、不销售、不分发任何 VPN 或代理节点服务**；公开输出文件**绝不包含**任何服务器地址、端口、密码、UUID 或私有订阅链接。  
> 完整条款及 48 小时侵权/下架处理通道请阅读 [DISCLAIMER.md](./DISCLAIMER.md)。

---

## 实时自动化探测看板 (Live Snapshot)

<!-- AUTO_DASHBOARD_START -->
> 最近一次自动探测时间：`2026-11-24 03:32 UTC+8`（共收录 `108` 个观测目标：🟢 正常 `77` · 🟡 观察 `0` · 🔴 风险 `31`；纯技术学习用途，不构成任何建议）

### 观测榜单节选（Top 30，完整全量见 [`data/airports.json`](./data/airports.json)）

| 目标 | 状态 | 综合分 | 节点数 | 延迟 (ms) | 可用率 | 采集模式 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| [V2RayAggregator 开源样本](https://github.com/mahdibland/V2RayAggregator) | 🟢 normal | **94.70** | 4095 | 1.58 | 100.0% | `tcp_passive` |
| [Barry-V2ray 开源样本](https://github.com/barry-far/V2ray-Config) | 🟢 normal | **94.30** | 207 | 2.09 | 100.0% | `tcp_passive` |
| 快狸 | 🟢 normal | **93.70** | 38 | 37.5 | 100.0% | `directory_bench` |
| [Pawdroid 开源样本](https://github.com/Pawdroid/Free-servers) | 🟢 normal | **93.30** | 9 | 1.32 | 100.0% | `tcp_passive` |
| 二猫云 | 🟢 normal | **93.20** | 40 | 36.0 | 100.0% | `directory_bench` |
| 一翻云 | 🟢 normal | **93.00** | 85 | 41.0 | 98.82% | `directory_bench` |
| 宇宙云 | 🟢 normal | **92.80** | 60 | 42.5 | 100.0% | `directory_bench` |
| 可信云 | 🟢 normal | **92.70** | 50 | 38.0 | 100.0% | `directory_bench` |
| 速界 | 🟢 normal | **92.70** | 52 | 37.0 | 100.0% | `directory_bench` |
| edgenova | 🟢 normal | **92.50** | 42 | 39.0 | 100.0% | `directory_bench` |
| 光速云 | 🟢 normal | **92.40** | 48 | 36.5 | 100.0% | `directory_bench` |
| 光年梯 | 🟢 normal | **92.05** | 62 | 41.5 | 100.0% | `directory_bench` |
| 极连云 | 🟢 normal | **92.05** | 55 | 40.5 | 100.0% | `directory_bench` |
| U1S1 | 🟢 normal | **91.40** | 58 | 11.0 | 100.0% | `directory_bench` |
| 唯兔云 | 🟢 normal | **91.35** | 30 | 50.0 | 96.67% | `directory_bench` |
| 全球云 | 🟢 normal | **90.55** | 33 | 41.0 | 96.97% | `directory_bench` |
| 飞猫云 | 🟢 normal | **89.90** | 88 | 37.0 | 97.73% | `directory_bench` |
| 星岛梦 | 🟢 normal | **88.65** | 88 | 51.0 | 98.86% | `directory_bench` |
| [NoMoreWalls 开源样本](https://github.com/peasoft/NoMoreWalls) | 🟢 normal | **88.30** | 117 | 4.94 | 87.5% | `tcp_passive` |
| [Au1rxx 开源聚合样本](https://github.com/Au1rxx/free-vpn-subscriptions) | 🟢 normal | **87.90** | 560 | 145.97 | 100.0% | `tcp_passive` |
| ANDY CLOUD | 🟢 normal | **84.55** | 0 | 85.0 | 92.0% | `directory_index` |
| 动力港 | 🟢 normal | **81.80** | 70 | 85.0 | 92.0% | `directory_index` |
| 跨界云 | 🟢 normal | **80.55** | 0 | 85.0 | 92.0% | `directory_index` |
| 灵猫网络 | 🟢 normal | **79.95** | 0 | 85.0 | 92.0% | `directory_index` |
| 环球梯 | 🟢 normal | **79.00** | 60 | 85.0 | 92.0% | `directory_index` |
| 闪跃 | 🟢 normal | **78.45** | 0 | 85.0 | 92.0% | `directory_index` |
| v2free机场 | 🟢 normal | **78.40** | 100 | 85.0 | 92.0% | `directory_index` |
| 拼好连 | 🟢 normal | **77.85** | 0 | 85.0 | 92.0% | `directory_index` |
| 闪电鼠 | 🟢 normal | **77.55** | 0 | 85.0 | 92.0% | `directory_index` |
| 瞬云 | 🟢 normal | **77.10** | 0 | 85.0 | 92.0% | `directory_index` |

### 风险与跑路预警节选（共 `31` 条，完整见 [`data/risk.json`](./data/risk.json)）

| 目标 | 状态 | 综合分 | 说明 |
| :--- | :---: | :---: | :--- |
| SKYLUMO | 🔴 risk | **30.80** | 公开目录记录已下架/停止收录（2026-11-18），仅供参考避坑。 |
| Sogo云 | 🔴 risk | **30.80** | 公开目录与实测数据汇总：参考月付 ¥25.0，节点 45 个，实测速率 822.6 Mbps，延迟 37 ms，公开参考评分 4.1/5。 |
| OneStep | 🔴 risk | **30.80** | 公开目录记录已下架/停止收录（2026-05-06），仅供参考避坑。 |
| 快帆云 | 🔴 risk | **30.80** | 社区公开风险清单记录：跑路（2025）。 |
| FCCloud | 🔴 risk | **30.80** | 社区公开风险清单记录：跑路（2025）。 |
| spcloud | 🔴 risk | **30.80** | 社区公开风险清单记录：跑路（2025）。 |
| efcloud | 🔴 risk | **30.80** | 社区公开风险清单记录：机场转让/用户套餐时长减半（2025）。 |
| ACA | 🔴 risk | **30.80** | 社区公开风险清单记录：跑路（2025）。 |
| 十元一年 | 🔴 risk | **30.80** | 社区公开风险清单记录：客服态度及其恶劣（2025）。 |
| DuangCloud | 🔴 risk | **30.80** | 社区公开风险清单记录：跑路（2024）。 |
| leensa | 🔴 risk | **30.80** | 社区公开风险清单记录：跑路预警（2024）。 |
| 六尺巷 | 🔴 risk | **30.80** | 社区公开风险清单记录：跑路（2024）。 |
| BHcloud/蜂巢 | 🔴 risk | **30.80** | 社区公开风险清单记录：跑路预警（2024）。 |
| 流量光 | 🔴 risk | **30.80** | 社区公开风险清单记录：跑路（2024）。 |
| v2Club/蓝岸 | 🔴 risk | **30.80** | 社区公开风险清单记录：跑路（2024）。 |
<!-- AUTO_DASHBOARD_END -->

---

## 架构设计

```mermaid
flowchart LR
    A["config/airports.yaml + sources.yaml + denylist.yaml"] --> B["多源采集层 (Catalog / Web / TG / RSS / Sub)"]
    S["GitHub Secrets (可选私有测试源)"] --> B
    B --> C["协议解析与脱敏聚合 (Clash YAML / Base64 / URI)"]
    C --> D["合规探测引擎 (DNS / TLS / HTTP / TCP 握手)"]
    D --> E["S-P-N-C-R 评分与 30 天滚动状态机"]
    E --> F["data/*.json + snapshot.json + README 看板"]
    F --> G["下游站点同步 (raw.githubusercontent.com / jsDelivr)"]
```

### 核心特性

1. **合规与安全边界**：内置 `robots.txt` 尊重、单域名速率限制、SSRF 防护（拒绝内网/回环/元数据 IP），绝不绕过验证码、人机校验或登录鉴权；公开输出在导出前执行正则防泄密校验。
2. **多格式节点解析与脱敏**：原生支持 Clash/Mihomo YAML、Base64 订阅与纯文本多协议 URI（`ss/vmess/vless/trojan/hysteria2/tuic`），按 `(protocol, host, port)` 去重，并在内存中完成地区、线路与并发 TCP 握手探测后立即销毁节点明文。
3. **S-P-N-C-R 五维客观评分**：
   - `S` (Stability 30%)：网站存活 + 抽样节点 TCP 握手可用率
   - `P` (Performance 25%)：吞吐速率（可选 CLI 测速）或被动响应效率（被动模式下严格封顶 88 分）
   - `N` (Network 20%)：中位 RTT 延迟、失败率与覆盖地区广度
   - `C` (Cost 15%)：月付成本、试用与退款支持度
   - `R` (Risk 10%)：DNS/TLS 证书健康度、连续异常次数、频道活跃度与外部风险源交叉比对

---

## 快速扩展与接入指南

### 1. 添加自定义监测目标

直接在 GitHub 网页端编辑 [`config/airports.yaml`](./config/airports.yaml)，参照文件底部的注释模板添加条目并提交至 `main` 分支，GitHub Actions 会自动触发新一轮采集。

### 2. 安全注入私有测试订阅（绝不入库）

在仓库 `Settings -> Secrets and variables -> Actions` 中新增 Secret `LBIRD_SUBSCRIPTIONS_JSON`，内容为 JSON 映射：

```json
{
  "my-target-slug": "https://example.com/sub?token=your-private-token"
}
```

工作流运行时仅在内存中读取该环境变量，绝不会将其写入 `data/*.json` 或日志。

### 3. 下游站点拉取标准 JSON

- **Raw 直连**：`https://raw.githubusercontent.com/Will9529/LBird-Airport-Review/main/data/snapshot.json`
- **jsDelivr CDN**：`https://cdn.jsdelivr.net/gh/Will9529/LBird-Airport-Review@main/data/snapshot.json`

也支持按表独立拉取 `data/airports.json`、`data/deals.json`、`data/news.json`、`data/risk.json`、`data/reports.json`、`data/stats.json`。

---

## 本地运行与测试

```bash
pip install -r requirements.txt
PYTHONPATH=src python -m lbird.cli run --config-dir config --data-dir data --readme README.md
PYTHONPATH=src python -m lbird.cli validate --data-dir data
pytest -v
```
