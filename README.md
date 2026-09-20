# 群报数「每日签到打卡」自动提交

针对小程序「群报数」的打卡任务（表单 ID `1889970208846901248`，每日 20:00–22:30 窗口，
每人每天限一次）的接口重放自动化，运行在 GitHub Actions，北京时间每天 20:10 / 20:40
各触发一次（已打卡自动跳过，双保险防定时延迟）。

## 提交逻辑（checkin.py）

1. `GET /v1/{FORM_ID}/form_data/last` —— `currNormalSize >= 1` 说明今天已打卡，直接成功退出
2. `GET /v1/form/{FORM_ID}/profile` —— **现拉最新 `formVersion`**（老师每次编辑表单版本号会涨，
   用旧版本号提交会被 13396「表单内容被修改」拒绝——这是本方案踩过的最大的坑）
3. `POST /v1/{FORM_ID}/form_data`，请求体：
   - 姓名（名单题）：`{"cid", "type":"WORD", "value":"张江楠202330142156 5"}`（格式为 `名字 组号`）
   - 是否请假：`{"cid", "type":"CHOICE", "value":[{"cid":"否选项cid","customValue":""}]}`
   - 定位：`{"cid", "type":"LOCATION", "value":{固定坐标对象}}`
   - 顶层：`{"fid":"", "subscribe":{}, "showQuestions":[三个cid], "examUsedTime":null, "formVersion":N}`
4. 回查 `currNormalSize` 确认生效；失败重试 3 次（间隔 30s），仍失败则 PushPlus 推送微信

接口域名 `form.qun100.com`，鉴权为请求头 `Authorization: <token>`（小程序抓包获得）。

## Secrets（GitHub 仓库 Settings → Secrets → Actions）

| 名称 | 内容 |
|---|---|
| `QBS_TOKEN` | 小程序请求头 Authorization 的值（过期后按下面步骤刷新） |
| `SMTP_USER` | QQ 邮箱地址（发件人=收件人，失败提醒发到这里） |
| `SMTP_PASS` | QQ 邮箱 SMTP 授权码（设置 → 账户 → 开启 SMTP 服务时生成，不是 QQ 密码） |

## token 过期后怎么刷新（实测有效期约 48~72 小时，隔两天刷一次）

**双击桌面「打卡token一键刷新.bat」** → 打开电脑微信进「群报数」任意页面（打卡页即可，
原本开着就先关掉重开）→ 看到窗口显示 `[OK] token 已验证并同步到 GitHub Secrets` 即完成。
脚本会自动：抓 token → 调接口验证 → 更新 GitHub Secret 和本地 secrets.local.json → 恢复原代理。

手动兜底（bat 失败时）：跑 `python refresh_token.py`；再不行用老办法（打卡抓包-开始/结束.bat + extract.py）。

## 提醒邮件规则

- **打卡成功**（脚本实际提交的日子）：收到「打卡成功（自动提交）」邮件
- **连续失败 3 次**：收到「打卡失败，请手动补卡」邮件，当天 22:30 前手动打卡
- 手动打过卡的日子：不发邮件（脚本检测到已打卡直接跳过）

## 表单被老师改了怎么办

脚本每次现拉 formVersion，普通修改无感。但如果老师**删改了题目**（cid 变化）或
**重组了名单分组**（姓名里的组号变了），需要更新 `checkin.py` 顶部的常量并重新推送。

## 本地测试

```bash
python checkin.py   # 读取 secrets.local.json 里的 token；已打卡时输出 skip
```

## 历史包袱（本地文件，不入库）

- `capture.flows` / `extracted.json` —— mitmproxy 抓包原始数据与分析结果
- `wxapkg-dec/` / `decrypt_wxapkg.py` —— PC 微信小程序包解密产物（逆向提交接口用）
