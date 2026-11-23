# 免责声明与合规边界 (Disclaimer & Compliance Notice)

## 中文声明

1. **纯技术学习与研究用途**  
   **LBird机场测评 (`LBird-Airport-Review`)** 是一个开源的网络可观测性、协议解析、定时探测与数据建模实验项目。本项目的所有代码、脚本、统计指标与自动化输出数据**仅用于计算机网络探测、异步编程与爬虫工程技术的学习与研究**。

2. **不构成任何建议或背书**  
   - 本仓库输出的所有数据、评分（S-P-N-C-R）、状态标签（`normal` / `watch` / `risk`）及自动生成报表**均不构成任何购买建议、使用建议、投资建议、质量担保或商业背书**。  
   - 自动化探针受探测节点网络环境（如 GitHub Actions 云机房出口 IP、跨境路由波动、目标站点临时策略等）影响极大，单次或短期观测结果**不代表任何服务商的真实或长期服务质量**。

3. **不提供任何代理或翻墙服务**  
   - 本仓库**不提供、不托管、不销售、不分发任何 VPN、代理服务器或可用节点订阅**。  
   - 公开输出文件（`data/*.json` 与 `README.md`）**严禁且不会包含**任何代理服务器 IP/域名、端口、密码、UUID 或原始订阅链接；所有节点级解析结果在内存中完成聚合统计后即被销毁。

4. **合规采集原则**  
   - 采集器严格遵守 `robots.txt` 协议、公开身份标识（`User-Agent`）、单域名请求速率限制与 SSRF 防护。  
   - **绝不绕过**任何网站的验证码（CAPTCHA）、人机校验（如 Cloudflare Turnstile）、登录鉴权或付费墙。  
   - 仅访问公开可获取的网页/公开开源仓库样本，或由仓库运行者自行通过私有 GitHub Secrets 注入的授权测试源。

5. **用户自负法律与合规责任**  
   任何个人或组织克隆、Fork、修改或运行本仓库代码时，必须严格遵守其所在国家及地区的相关法律法规。因不当使用、违规爬取或二次分发本仓库代码所产生的一切直接或间接法律责任，均由使用者自行承担，本项目作者与维护者不承担任何连带责任。

6. **侵权投诉与 48 小时下架通道 (Notice & Takedown)**  
   如任何第三方认为本仓库配置文件或历史输出中引用了您的公开链接、商标或信息并希望移除，请通过 [GitHub Issue (下架申请模板)](./.github/ISSUE_TEMPLATE/takedown.yml) 提交申请，我们将在确认后 **48 小时内** 将对应条目加入 `config/denylist.yaml` 并永久停止采集与清理历史数据。

---

## English Disclaimer

1. **Purely Educational & Technical Research Purpose**  
   **LBird-Airport-Review** is an open-source engineering project focused on network observability, protocol parsing, asynchronous probing, and scheduled data pipelines. All code, configurations, metrics, and outputs are provided **strictly for technical learning and research**.

2. **No Advice, No Endorsement, No Warranty**  
   Nothing in this repository constitutes a recommendation, endorsement, financial/consumer advice, or guarantee of service quality. Automated measurements from cloud runners (e.g., GitHub Actions) are inherently affected by datacenter IP policies and transient routing conditions.

3. **No Proxy Hosting or Credential Redistribution**  
   This repository **does not** provide, host, sell, or redistribute proxy/VPN services or raw subscription credentials. Public outputs (`data/*.json`, `README.md`) contain **only anonymized aggregate metrics** and never persist node hosts, ports, passwords, UUIDs, or private subscription URLs.

4. **Compliant Collection**  
   The collector respects `robots.txt`, applies per-domain rate limits, enforces SSRF protections, and **never** bypasses CAPTCHAs, anti-bot challenges, or authentication gates.

5. **Limitation of Liability & User Responsibility**  
   Provided "AS IS" under the MIT License without warranty of any kind. Users are solely responsible for ensuring their use complies with all applicable local laws and terms of service.

6. **Notice & Takedown (48-Hour SLA)**  
   Rights holders or operators may request immediate removal via the [Takedown Issue Template](./.github/ISSUE_TEMPLATE/takedown.yml). Verified targets are permanently excluded via `config/denylist.yaml` within 48 hours.
