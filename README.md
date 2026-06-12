# SpecForge

SpecForge 是一個 evidence-first 的 codebase-to-spec 掃描工具。

它會把一個既有專案掃描成一份 spec bundle，讓人和 LLM 都能看懂專案目前的骨架、入口、前後端 surface、API、資料層、測試、設定與缺口。SpecForge 本身不使用 LLM，也不強制依賴 tree-sitter、Babel 或其他 parser；目前以 Python 零依賴規則抽取為主。

## 安裝

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

解除安裝只會移除 `specforge` 指令，不會刪除專案裡已產生的 `.specforge` 或 `specforge-output`。

## 使用方式

第一次掃描專案：

```bash
cd your-project
specforge init
```

更新既有 spec：

```bash
specforge update
```

如果已經存在 `.specforge` 或 `specforge-output`，再次執行 `init` 會要求你改用 `update`。需要覆寫初始化時可以使用：

```bash
specforge init --force
```

## 產生位置

SpecForge 預設會在被掃描專案底下產生：

```text
your-project/.specforge/          facts.json, traceability.json, gaps.json
your-project/specforge-output/    Markdown spec bundle
```

`.specforge` 是機器可讀的掃描資料；`specforge-output` 是人和 LLM 可讀的 Markdown 規格文件。

## 目前可以掃描什麼

- Python / JavaScript / TypeScript / Java 的基礎 symbols、imports、commands
- CLI entrypoints 與 command rebuild targets
- Express、Next API、FastAPI、Flask、Spring MVC、Servlet routes
- React、Vue、Next、HTML、JSP、forms、CSS、assets、state usage
- Spring / Maven、Servlet / JSP、JPA entity、repository、service
- SQL、Prisma、Drizzle、MyBatis、SQLAlchemy、Django model 基礎訊號
- `.env.example`、Dockerfile、docker-compose、GitHub Actions、Spring / Vite / Next config
- frontend API call 到 backend route 的保守連結
- test map、runtime config、contract gaps、evidence trace

## 主要輸出文件

總覽與架構：

```text
overview.md
architecture.md
quality-report.md
```

骨架與 surface：

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

重建與 LLM handoff：

```text
feature-map.md
rebuild-spec.md
module-boundaries.md
contract-gaps.md
refactor-plan.md
spec-diff.md
implementation-guide.md
llm-handoff.md
```

## 重要原則

- 只有有 evidence 的內容才會被當成事實。
- 掃不到的 request、response、auth、DB side effects、user flow 會留在 gaps 或 unknown。
- 目前第一階段重點是「專案骨架與關聯」，不是完整業務邏輯理解。
- API、測試、command implementation 的關聯都是保守推斷，會附上 confidence 或 match reason。
- Secret value 不會被輸出；runtime config 只列 key name 或設定訊號。

## License

MIT
