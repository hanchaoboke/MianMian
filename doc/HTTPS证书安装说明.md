# 局域网 HTTPS 与语音输入

前端由 Caddy 提供构建产物，API 和 WebSocket 同源转发到 `127.0.0.1:8010`。无需启动 Vite。
证书自动续签，CA 与私钥保留在被 Git 忽略的 `.local/https`，不要删除这个目录或分发其中的私钥。

## 启动

先运行项目后端，再安装 [Caddy](https://caddyserver.com/docs/install)（macOS 使用 `brew install caddy`）。在项目根目录执行：

```bash
conda activate MianMian_py312
python deploy/https.py start --host 192.168.10.229
```

将 IP 换成服务器当前的局域网地址；省略 `--host` 时使用默认网络接口地址，多网卡可以重复传入。
默认端口为 8443，可通过 `--port` 修改。学生访问 `https://服务器IP:8443/`，教师访问 `https://服务器IP:8443/teacher/login`。
允许客户端连接 TCP 8443。脚本会构建前端并后台启动网关，关闭终端后网关仍运行；电脑重启后需重新启动后端及本脚本。

## 每台学生电脑首次安装证书

使用内网 IP 时，浏览器需要信任本项目 CA。把本目录中的 **[mianmian-local-ca.crt](mianmian-local-ca.crt)** 和本文档一起发给学生。启动或重新加载 HTTPS 网关时，会自动将当前公开证书同步到 `doc/mianmian-local-ca.crt`。
不要只点击浏览器的“继续访问不安全网站”，也不要通过关闭浏览器安全检查来使用麦克风。
证书文件由你通过可信渠道分发，学生安装前可核对你提供的 SHA-256 指纹：

```bash
openssl x509 -in doc/mianmian-local-ca.crt -noout -fingerprint -sha256
```

- **Windows / Chrome / Edge**：双击证书，选择“安装证书” → “当前用户” → “将所有的证书都放入下列存储” → “受信任的根证书颁发机构”。也可在证书所在目录执行 `certutil -user -addstore Root mianmian-local-ca.crt`。
- **macOS / Chrome / Safari**：双击证书导入“钥匙串访问”的“登录”钥匙串；双击该证书，展开“信任”，将使用此证书设为“始终信任”。
- **Firefox**：在“设置 → 隐私与安全 → 证书 → 查看证书 → 证书颁发机构”中导入，信任该 CA 标识网站。

重启浏览器后打开 HTTPS 学生端，确认地址栏没有证书错误；重新登录，点击“语音输入”并允许麦克风。
HTTP 与 HTTPS 的登录状态独立，需要重新登录。服务器 IP 改变后需重新运行 `reload --host 新IP`；CA 未更换时客户端无需重新安装证书。
证书安装完成后也可从 `https://服务器IP:8443/mianmian-local-ca.crt` 下载同一份公开 CA。

## 更新与停止

```bash
python deploy/https.py reload --host 192.168.10.229
python deploy/https.py status
python deploy/https.py stop
```

`reload` 会重建前端并更新网关；后端更新仍按后端的启动方式处理。日志在 `.local/https/gateway.log`。
若已有进程占用 8443，指定空闲 `--port`；2020 是仅本机可访问的 Caddy 管理端口，不应向局域网转发。

有正式域名时，可改用受浏览器默认信任的公有 CA 证书，省去逐台安装。内网域名通常需要 DNS 验证与内网 DNS 配置。
此网关仅负责 HTTPS 和静态页面，不会改变数据库及账号配置；正式运行仍需后端 `ENVIRONMENT=production`、PostgreSQL 和适当的进程托管。

浏览器要求说明见 [MDN getUserMedia](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia)，证书机制见 [Caddy Local HTTPS](https://caddyserver.com/docs/automatic-https#local-https)。
