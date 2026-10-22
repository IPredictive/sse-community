# 狮城胖叔·上证分析台

这是一个公开托管在 GitHub 的上证指数 AI 分析与预测社区项目。

每天工作日自动运行 5 位分析师：
- Technical：MA / MACD / RSI
- Flow：成交量与动量
- Macro：宏观与政策新闻
- Sentiment：财经新闻与市场情绪
- Overseas：标普500、纳斯达克、恒生、美元人民币
- Chief Analyst：综合五位分析师，给出最终上涨概率、信心与理由

## 每日网页

当前网站由 **GitHub Pages** 发布：https://ipredictive.github.io/sse-community/

- `site/index.html` 是当前静态网页。
- `.github/workflows/pages.yml` 负责发布网页改动。
- `.github/workflows/daily.yml` 工作日运行 AI 分析、更新数据库并重新生成网页。
- 每日工作流遇到并发推送时会同步最新 `main` 并重试发布。

## AI 分析

默认使用项目内的规则模型与技术指标，不需要配置 OpenAI API Key。若将来启用外部大模型，API Key 应放在 GitHub Actions Secrets 中，不能写进代码、README 或网页。

## GitHub Actions

工作日每天运行一次。当前 cron 为 \`35 7 * * 1-5\`（UTC），对应新加坡/上海时间约 15:35。

也可以在：
\`Actions → Daily SSE Agents → Run workflow\`
手动运行。

## 本地测试

\`\`\`bash
pip install -r requirements.txt
python run_daily.py --demo --backfill 60 --no-news
python generate_site.py
\`\`\`

## 重要

这是研究和回测框架，不是可靠的股票预测器。“上涨概率”是模型输出，不代表保证性的真实概率，不应据此自动交易。


## Community backend (Google Apps Script, no Supabase)

The initial Apps Script backend source is in `google-apps-script/Code.gs`, with setup instructions in `google-apps-script/README.md`.

Important: adding the source to GitHub does not deploy it into your Google account. The frontend `site/community.js` already calls the configured Apps Script `/exec` URL. The Apps Script project must be deployed as a Web app and have `SPREADSHEET_ID` and private `ADMIN_KEY` Script Properties configured. After changing `google-apps-script/Code.gs`, publish a new Apps Script deployment version manually; GitHub commits do not update the live Apps Script deployment.


## Optional AGNES AI review layer

The daily pipeline can call an external AGNES-compatible chat-completions endpoint to review analyst disagreements, counterarguments, evidence gaps, and risks. This first integration is advisory only: **AGNES does not change the numeric CHIEF_ANALYST probability**. If the endpoint is not configured, times out, or returns invalid output, the existing ensemble and publication workflow continue.

Configure these in **GitHub → Settings → Secrets and variables → Actions**:

- Secret `AGNES_API_KEY`: your existing AGNES API key. Add it to this repository’s Actions secrets; a key stored only in Vercel is not automatically available to GitHub Actions.
- Optional variable `AGNES_API_URL`: defaults to `https://apihub.agnes-ai.com/v1/chat/completions`.
- Optional variable `AGNES_MODEL`: defaults to `agnes-3.0-flash`.

Do not commit API keys to the repository or paste them into chat. The defaults use AGNES’s documented OpenAI-compatible chat endpoint and `agnes-3.0-flash`; verify the model is enabled for your key in the AGNES console. The endpoint must accept an OpenAI-compatible `POST` request with `messages` and return a JSON response containing `choices[0].message.content` (Responses-style `output_text` is also accepted). Review output is saved as a short note in the CHIEF_ANALYST explanation; forecast probability and confidence remain those of the deterministic ensemble. Do not configure the endpoint until its URL, model name, access rights, and pricing are confirmed.
