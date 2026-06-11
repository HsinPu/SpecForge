# SpecForge

以 evidence 為核心的 codebase-to-spec 產生器。

SpecForge 會掃描既有專案，抽取可追溯的 deterministic facts，並產生一份人和 LLM 都能閱讀的 spec bundle。它不需要 LLM、不呼叫外部服務，重點是把「程式碼裡真的看得到的內容」整理成可交接的專案骨架。

## 目標

把一個專案整理成這樣的關聯式規格：

```text
Page / Component / Form
-> API Call
-> Backend Route
-> Request / Response Contract
-> Service / Repository / Data Model
-> Runtime Config
-> Test Evidence
```

這份 spec 可以給人看，也可以交給 LLM 作為重建、轉寫、migration 或理解專案的依據。

## 一鍵安裝

Windows：

```powershell
powershell -ExecutionPolicy ByPass -NoProfile -Command "iex (irm https://raw.githubusercontent.com/HsinPu/SpecForge/main/scripts/install.ps1)"
```

Linux / macOS：

```bash
curl -fsSL https://raw.githubusercontent.com/HsinPu/SpecForge/main/scripts/install.sh | bash
```

安裝完成後會提供 `specforge` 指令。若新開終端後仍找不到指令，請重開 terminal，或確認安裝腳本提示的 bin 目錄已加入 PATH。

## 使用方式

第一次在專案底下初始化：

```powershell
cd C:\path\to\project
specforge init
```

之後要重新掃描、更新 spec：

```powershell
cd C:\path\to\project
specforge update
```

如果已經有 `.specforge` 或 `specforge-output`，`specforge init` 會停止並提示改用 `update`。需要強制重建時可以用：

```powershell
specforge init --force
```

產物會建立在你執行指令的資料夾底下：

```text
C:\path\to\project\.specforge
C:\path\to\project\specforge-output
```

只有想指定輸出資料夾時才需要加參數：

```powershell
specforge init --out my-spec
specforge update --out my-spec
```

## 目前支援

- Python / JavaScript / TypeScript 基礎 symbols、imports、commands。
- Express、Next API、FastAPI、Flask、Spring MVC、Servlet route。
- React、Vue、Next、HTML、JSP、常見模板頁面與 CSS/assets。
- Spring/Maven、Servlet/JSP、JPA、repository、service 骨架。
- SQL、Prisma、Drizzle、MyBatis、SQLAlchemy、Django model 資料層訊號。
- env、Docker、Compose、GitHub Actions、Spring/Vite/Next config runtime 訊號。
- frontend API call 到 backend route 的保守關聯。
- API contract skeleton、test map、gaps、evidence trace。

## 產出內容

`forge` 會輸出兩個資料夾：

```text
.specforge/          raw facts, traceability, gaps
specforge-output/    Markdown spec bundle
```

主要文件會包含 overview、architecture、backend/frontend、API routes/contracts/links、data layer、runtime config、test map、implementation guide、LLM handoff、gaps 與 evidence。

## 原則

- 只把有 evidence 的內容當作 fact。
- 掃不到的 schema、auth、side effects、user flows 會列為 gaps。
- 不讀 secret value，只列出可公開的 key name 與來源。
- 第一版優先產生穩定骨架，不做完整 call graph 或完整業務邏輯推論。

## 授權

MIT。
