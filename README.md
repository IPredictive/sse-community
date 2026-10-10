# 狮城胖叔·上证分析台

这是一个保持 **Private** 的上证指数多智能体研究项目。

每天工作日自动运行 5 位分析师：
- Technical：MA / MACD / RSI
- Flow：成交量与动量
- Macro：宏观与政策新闻
- Sentiment：财经新闻与市场情绪
- Overseas：标普500、纳斯达克、恒生、美元人民币
- Chief Analyst：综合五位分析师，给出最终上涨概率、信心与理由

## 每日网页

网页文件由 GitHub Actions 自动生成到 \`site/index.html\`。

由于当前 GitHub 账户的 Private repository 不支持直接启用 GitHub Pages，本项目改用 **Vercel** 发布网页。仓库保持 Private，不需要公开源代码。

第一次部署：
1. 在 Vercel 登录并连接 GitHub。
2. Import \`IPredictive/sse-agents\`。
3. Framework Preset 选择 \`Other\` / Static。
4. Root Directory 保持 \`/\`。
5. Deploy。
6. 之后 GitHub Actions 每天更新 \`site/index.html\`，Vercel 会自动重新部署。

仓库已经提供 \`vercel.json\`，用于把 \`site/\` 作为网站输出目录。

## AI API

GitHub Actions 使用：
- \`OPENAI_API_KEY\`：Repository secret
- \`OPENAI_MODEL\`：Repository variable

不要把 API Key 写进代码、README 或网页。

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

Important: adding the source to GitHub does not deploy it into your Google account. You must create/deploy the Apps Script web app and configure its `SPREADSHEET_ID` and private `ADMIN_KEY` Script Properties. The frontend still needs to be switched from its old Supabase calls to the Apps Script API and tested against the deployed URL before registration, voting, P coins, or leaderboard will work without Supabase.
