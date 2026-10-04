# Qunbao Check-in

> **每天都要做一次的事情，不应该每天都由你亲自做。**

今天，正式发布 **Qunbao Check-in**。

一个面向「群报数」固定签到场景的自动化方案。

它不会在晚上提醒你：

> “该打卡了。”

它会直接完成这件事。

---

## 为什么要做它？

每天打开微信。

找到小程序。

进入表单。

填写姓名。

选择选项。

提交定位。

确认结果。

第二天，再来一次。

当一件事情每天都以几乎相同的方式重复时，我们开始思考一个很简单的问题：

> **为什么它还需要人来做？**

于是，有了 Qunbao Check-in。

---

# 从“记得签到”，到“自动完成”

Qunbao Check-in 会在签到任务执行时自动完成一套完整流程：

```text
检查今天是否已经签到
        ↓
获取最新表单版本
        ↓
构造并提交签到数据
        ↓
再次回查提交结果
        ↓
成功结束 / 失败重试并通知
```

如果今天已经完成签到，它不会重复提交。

如果还没有，它才真正开始工作。

**自动化的第一步，不是提交，而是先确认有没有必要提交。**

---

# 不是简单地“重放一次 POST”

最开始，看起来只需要保存一次请求，然后每天重新发送。

真正做起来以后，最大的坑来自一个字段：

```text
formVersion
```

群报数的表单存在版本机制。

当表单发布者重新编辑表单后，版本号可能发生变化。如果继续携带旧版本号提交，服务端可能返回：

```text
13396 - 表单内容被修改
```

所以 Qunbao Check-in **不会把 `formVersion` 写死**。

每一次准备签到时，都会先读取：

```text
GET /v1/form/{FORM_ID}/profile
```

获取当前最新版本。

这意味着，即使表单发布者调整了普通表单内容，脚本也不需要依赖某一个长期不变的版本号，而是会在提交前同步当前 `formVersion`。

**真正可靠的自动化，不应该建立在“希望表单永远别变”之上。**

> 需要注意：如果发布者进行了结构级修改，例如删除或重新创建题目、导致 `cid` 变化，或者重新调整名单分组，则仍需同步更新脚本配置。

---

# 一次完整签到，会发生什么？

## 01 / CHECK

首先查询当天的提交状态：

```text
GET /v1/{FORM_ID}/form_data/last
```

当：

```text
currNormalSize >= 1
```

说明今天已经完成签到。

任务直接结束。

不重复提交。

---

## 02 / SYNC

如果今天还没有签到，脚本会读取最新表单信息：

```text
GET /v1/form/{FORM_ID}/profile
```

并取得当前：

```text
formVersion
```

旧版本不猜。

版本号不写死。

每一次提交，都以当前表单状态为准。

---

## 03 / CHECK IN

随后构造签到数据，并发送：

```text
POST /v1/{FORM_ID}/form_data
```

当前提交内容包括：

- 姓名 / 名单信息
- “是否请假”的选项
- 签到位置
- 当前表单对应的 `formVersion`

鉴权通过请求头：

```text
Authorization: <token>
```

接口域名：

```text
form.qun100.com
```

---

## 04 / VERIFY

请求成功，并不代表整个流程结束。

提交完成后，Qunbao Check-in 会再次查询当天状态。

只有当：

```text
currNormalSize >= 1
```

才认为本次签到真正完成。

因为我们需要确认的不是：

> “HTTP 请求发出去了。”

而是：

> **“签到记录确实已经写进去了。”**

---

# 失败，也必须被看见

网络可能波动。

接口可能异常。

Token 可能过期。

表单结构也可能变化。

所以 Qunbao Check-in 不假设所有事情永远正常。

一次执行最多尝试 3 次：

```text
Attempt #1
    ↓
失败
    ↓ 30s
Attempt #2
    ↓
失败
    ↓ 30s
Attempt #3
```

连续失败后，脚本会通过 QQ 邮箱 SMTP（Simple Mail Transfer Protocol，简单邮件传输协议）发送：

```text
打卡失败，请手动补卡
```

把异常重新交还给人处理。

---

# 成功的时候，也会告诉你

当脚本实际完成自动提交并回查确认后，会收到：

```text
打卡成功（自动提交）
```

如果今天已经人工完成签到：

**不会发送多余邮件。**

脚本检测到状态后直接退出。

它只在真正需要出现的时候出现。

---

# 现在，它怎么运行？

项目支持本地和 GitHub Actions 两种运行方式。

当前日常任务主要由 **Windows Task Scheduler（Windows 任务计划程序）** 执行，在本机定时启动脚本。

GitHub Actions（GitHub 自动化工作流）的定时调度目前已经移除，仅保留：

```text
workflow_dispatch
```

也就是 **手动应急触发**。

这样可以避免低活跃仓库的 GitHub Schedule（GitHub 定时调度）出现明显延迟后，在已经错过签到窗口时补跑任务并产生无意义的失败提醒。

当前工作流文件：

```text
.github/workflows/checkin.yml
```

需要时，可以直接在 GitHub Actions 页面手动运行。

---

# Secrets

GitHub Actions 中使用的敏感信息通过：

```text
Settings
→ Secrets and variables
→ Actions
```

保存。

| Secret | 用途 |
|---|---|
| `QBS_TOKEN` | 群报数接口请求使用的 Authorization Token |
| `SMTP_USER` | QQ 邮箱地址 |
| `SMTP_PASS` | QQ 邮箱 SMTP 授权码 |

Token 不写进仓库。

邮箱授权码也不写进仓库。

**代码可以公开，凭据不应该公开。**

---

# Token 过期了？

Token 不是永久有效的。

推荐刷新方式：

1. 打开群报数网页版：

   ```text
   https://h5.qun100.com/#/pages/record/main
   ```

2. 使用微信扫码登录。

3. 登录成功后，从浏览器 `localStorage` 中读取：

   ```text
   productionwxLoginAccessToken
   ```

4. 更新 `QBS_TOKEN`。

仓库中同时保留了 Token 获取与刷新相关辅助脚本，方便在需要时重新获取认证信息。

---

# 本地运行

安装依赖：

```bash
pip install requests
```

然后：

```bash
python checkin.py
```

本地运行时，脚本会优先读取环境变量：

```text
QBS_TOKEN
```

如果没有，则尝试读取：

```text
secrets.local.json
```

如果当天已经完成签到，会直接跳过，不会重复提交。

---

# 项目结构

```text
qunbaoshu-checkin/
│
├── .github/
│   └── workflows/
│       └── checkin.yml       # GitHub Actions 应急手动执行
│
├── checkin.py                # 自动签到核心逻辑
├── extract.py                # 请求信息提取辅助
├── mitm_token_grab.py        # Token 获取辅助
├── refresh_token.py          # Token 刷新辅助
├── .gitignore
└── README.md
```

---

# 如果表单发生变化

对于普通编辑：

```text
发布者修改表单
        ↓
formVersion 更新
        ↓
脚本运行时重新获取
        ↓
继续使用最新版本提交
```

通常不需要手动维护版本号。

但如果发布者进行了结构级调整，例如：

- 删除或重新创建题目；
- 题目对应的 `cid` 发生变化；
- 名单重新分组；
- 姓名对应的组号发生变化；

则需要同步修改 `checkin.py` 中对应配置。

自动化可以适应**版本变化**。

但它不会猜测一个全新的表单结构。

---

# 最后

Qunbao Check-in 没有试图解决一个复杂的问题。

它解决的是一种更常见的问题：

> **一件很简单，但每天都要重复一次的事情。**

以前：

```text
到时间
  ↓
想起来
  ↓
打开微信
  ↓
找到小程序
  ↓
找到表单
  ↓
填写
  ↓
提交
  ↓
确认
```

现在：

```text
到时间
  ↓
自动检查
  ↓
自动同步
  ↓
自动提交
  ↓
自动确认
  ↓
Done.
```

没有新的 App。

没有每天需要打开的控制台。

没有“我今天是不是忘记签了”的反复确认。

它在需要的时候执行。

成功之后安静退出。

异常的时候告诉你。

而你，

**不再需要把注意力浪费在重复的事情上。**

---

## Qunbao Check-in

### **让重复的事情，停止重复占用你的注意力。**
