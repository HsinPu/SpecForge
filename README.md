# SpecForge

SpecForge 是一個 evidence-first 的 codebase-to-spec 工具。

它會掃描一個專案，產生一份人和 LLM 都看得懂的 spec bundle。掃描過程不使用 LLM，所有結論都盡量附上來源檔案與行號；掃不到的地方會列成 gap。

## 目前定位

SpecForge v0.2 主要做兩件事：

```text
v0.1: 掃描全端專案骨架
v0.2: 把掃到的骨架串成可重構 / 可重建的關聯 spec
```

它會嘗試把這條鏈串起來：

```text
Page / Component / Form
-> API Call
-> Backend Route
-> API Contract
-> Service / Repository / Data Model
-> Test Evidence
```

## 一鍵安裝

Windows:

```powershell
powershell -ExecutionPolicy ByPass -NoProfile -Command "iex (irm https://raw.githubusercontent.com/HsinPu/SpecForge/main/scripts/install.ps1)"
```

Linux / macOS:

```bash
curl -fsSL https://raw.githubusercontent.com/HsinPu/SpecForge/main/scripts/install.sh | bash
```

安裝後重新開一個 terminal，確認：

```bash
specforge --version
```

## 解除安裝

Windows:

```powershell
powershell -ExecutionPolicy ByPass -NoProfile -Command "iex (irm https://raw.githubusercontent.com/HsinPu/SpecForge/main/scripts/uninstall.ps1)"
```

Linux / macOS:

```bash
curl -fsSL https://raw.githubusercontent.com/HsinPu/SpecForge/main/scripts/uninstall.sh | bash
```

解除安裝只移除 `specforge` 指令與安裝目錄，不會刪你的專案裡的 `.specforge` 或 `specforge-output`。

## 使用方式

第一次掃描專案：

```bash
cd your-project
specforge init
```

之後更新 spec：

```bash
specforge update
```

如果已經有 `.specforge` 或 `specforge-output`，`init` 會停止，避免覆蓋既有結果。要刷新請用：

```bash
specforge update
```

真的要重新初始化：

```bash
specforge init --force
```

## 輸出在哪

預設會產生在被掃描的專案底下：

```text
your-project/.specforge/          facts.json, traceability.json, gaps.json
your-project/specforge-output/    Markdown spec bundle
```

`.specforge` 偏向工具讀取，`specforge-output` 是給人和 LLM 看的。

## 建議閱讀順序

先看總覽：

```text
overview.md
architecture.md
```

看全端骨架：

```text
backend.md
frontend.md
api-routes.md
api-contracts.md
api-links.md
pages.md
components.md
data-models.md
runtime-config.md
test-map.md
```

看 v0.2 重構 / 重建文件：

```text
feature-map.md
rebuild-spec.md
module-boundaries.md
contract-gaps.md
refactor-plan.md
spec-diff.md
llm-handoff.md
```

## 目前可掃描的內容

- Python / JavaScript / TypeScript / Java 基礎 symbols、imports、commands
- Express、Next API、FastAPI、Flask、Spring MVC、Servlet routes
- React、Vue、Next、HTML、JSP、forms、CSS、assets、state usage
- Spring / Maven、Servlet / JSP、JPA entity、repository、service
- SQL、Prisma、Drizzle、MyBatis、SQLAlchemy、Django model
- `.env.example`、Dockerfile、docker-compose、GitHub Actions、Spring / Vite / Next config
- frontend API call 對 backend route 的初步關聯
- API contract skeleton、test map、runtime config、gaps、evidence trace

## v0.2 新增了什麼

- `feature-map.md`: 把前端 API call、後端 route、contract、data/test evidence 組成功能切片
- `rebuild-spec.md`: 給人或 LLM 的重建順序
- `refactor-plan.md`: 保守列出重構提醒
- `module-boundaries.md`: 粗分 frontend、backend API、data layer、runtime config、tests、shared source
- `contract-gaps.md`: 集中列出 unknown request、response、status、error、unmatched API
- `spec-diff.md`: `update` 時比較上一份 facts，列出新增或移除的 route、API call、component、page、model

## 限制

- 不會完整理解業務邏輯
- 不會保證完整 call graph
- 不會推論 auth/security、DB side effects、transaction、完整 user flow
- 不會讀取 secret value，只列 key name
- 沒有 evidence 的內容不能當事實，只能當 gap 或 unknown

## 版本紀錄

版本變更請看 [CHANGELOG.md](CHANGELOG.md)。

## License

MIT
