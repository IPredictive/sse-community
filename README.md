# 狮城胖叔·上证预测打擂台（独立版）

这是独立于 `sse-agents` 的新网站，面向 Namecheap cPanel + Python 3.11 + MySQL 8。

## 当前基础功能
- MySQL 数据库初始化
- 用户注册 / 登录，使用安全的密码哈希
- 新用户注册时发放 3000 P币
- 下一交易日看多 / 看空投票（每用户每目标日期一次）
- P币排行榜
- 五个量化分析师与 Chief Analyst 结果展示（当预测结果写入 MySQL 后显示）
- 不调用 OpenAI API

## cPanel 环境变量
在 Setup Python App 中设置：
- `DB_HOST`：通常为 `localhost`
- `DB_NAME`：cPanel 显示的完整数据库名称，包含自动添加的前缀
- `DB_USER`：cPanel 显示的完整数据库用户名，包含自动添加的前缀
- `DB_PASSWORD`：数据库用户密码
- `SECRET_KEY`：自行生成的长随机字符串

不要将密码写入代码或提交到 GitHub。

## 部署
1. 将本仓库文件放进 cPanel Python 应用根目录。
2. 在 Setup Python App 的虚拟环境中安装 `requirements.txt` 中依赖。
3. 设置上面的环境变量。
4. 点击 Restart。
5. 访问网站的 `/health`，预期返回 `{"status":"ok","database":"connected"}`。

## 注意
- 原仓库 `IPredictive/sse-agents` 不会被修改。
- 投票目标日期当前跳过周末，尚未接入中国法定交易日历；上线前应加入节假日交易日历。
- P币准确预测结算和奖励规则需在正式启用前确认。
- 本项目只展示研究用途的量化预测，不构成投资建议。
