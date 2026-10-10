# roLabelImg Windows 客户端发布与手动升级方案

发布仓库：<https://github.com/YG817/rolabelImg-master>。
本方案以 Windows 10/11 x64、Python 3.11、公开 GitHub Releases 为目标。
当前新客户端版本起点为 **2.0.0**；发布前可以在 `app_version.py` 调整。

## 1. 发布流程

```text
修改代码与 APP_VERSION
    ↓
提交到 GitHub main 分支，推送 v2.0.0 标签
    ↓
GitHub Actions：源码测试 → PyInstaller onedir → exe 内自检
    ↓
Inno Setup：生成 Setup.exe → ZIP / SHA256 / 构建信息
    ↓
创建带安装包的草稿 Release
    ↓
你在干净 Windows 电脑验收，填写说明，再手动 Publish release
    ↓
已安装的客户端后台查询正式版 → 提示用户 → 浏览器下载
    ↓
用户保存标注、退出程序、运行新 Setup.exe，覆盖升级
```

每位用户安装后无需 Python、Conda 或项目虚拟环境。
客户端查询的是 Release，不会执行 git pull，也不下载源码替代安装包。
普通代码提交不会通知用户；仅正式发布 Release 才会被客户端识别。
草稿、预发布版和缺少匹配安装包的 Release 不会提示正常可安装更新。

## 2. 项目结构与职责

```text
roLabelImg-master/
├── roLabelImg.py                     # 现有标注应用，新增版本与更新入口
├── client_entry.py                   # exe 入口、异常日志、安装运行互斥量
├── app_version.py                    # 唯一运行版本号、GitHub 仓库、安装包命名
├── requirements.txt                  # 现有开发环境依赖范围
├── USER_GUIDE.md
├── THIRD_PARTY_NOTICES.md
├── resources.py                     # 现有已编译 Qt 图标资源
├── data/predefined_classes.txt
├── libs/
│   ├── update_checker.py             # 后台查询 Release、比较版本、提示下载
│   └── release_smoke.py              # exe 内检查 Qt / TIFF / PROJ / COCO / VOC
├── packaging/
│   ├── requirements-windows.txt      # Windows 构建的核心依赖固定版本
│   ├── roLabelImg.spec               # PyInstaller onedir 配置
│   ├── rth_gdal.py                   # 打包后 GDAL / PROJ 数据目录
│   ├── installer.iss                # Inno Setup 安装、快捷方式、升级与卸载
│   └── RELEASE_NOTES.md              # 本次发布说明模板，每版修改
├── tools/build_windows.py            # 构建、exe 自检、安装包、压缩、校验和
├── .github/workflows/windows-release.yml
└── docs/WINDOWS_RELEASE.md            # 本说明
```

构建生成的 `build/`、`dist/`、`release/`、`.build-venv/` 已加入忽略规则，
不要把它们提交到源码仓库。

## 3. 版本号与仓库配置

所有运行时、exe 文件版本和安装包版本均读取 `app_version.py`：

```python
APP_VERSION = '2.0.0'
GITHUB_OWNER = 'YG817'
GITHUB_REPO = 'rolabelImg-master'
```

对应 Git 标签 `v2.0.0`，安装包必须叫：

```text
roLabelImg-Setup-2.0.0-win-x64.exe
```

版本按三段整数比较，`2.10.0` 大于 `2.9.0`，不会按字符串比较。
正式客户端目前只接收 `X.Y.Z` 或 `vX.Y.Z` 格式。
兼容修复增加最后一段，例如 `2.0.1`；新功能增加中间一段，例如 `2.1.0`。
更新发布时只需手动修改 APP_VERSION；`setup.cfg` 的 bumpversion 配置仅为旧工具兼容，
如继续使用该工具也应同步它的 current_version。

不把 GitHub Token 放进客户端。公开仓库的正式 Release 信息允许匿名查询。
如果未来源码改为私有，请另建公开的发布仓库，并调整上述 OWNER / REPO 与安装器网页地址；
当前工作流默认在源码所在仓库上传 Release，不会自动跨仓库发布。

## 4. 本地先构建一遍

### 4.1 安装构建工具

安装 **64 位 Python 3.11** 和 **Inno Setup 6**。本地可以使用官方较新的 Inno Setup 6；
工作流在需要安装编译器时使用 6.4.3，已有编译器则复用。

当前检测到的本地 Conda Python 是 **3.10.0**，PyInstaller 官方明确不支持它。
开发标注功能可以继续使用当前环境，构建发行版请使用单独的 Python 3.11 环境。

在项目根目录执行（PowerShell）：

```powershell
py -3.11 -m venv .build-venv
.\.build-venv\Scripts\python.exe -m pip install -r packaging\requirements-windows.txt
.\.build-venv\Scripts\python.exe -m pytest -q
.\.build-venv\Scripts\python.exe tools\build_windows.py
```

如果你使用本地 Conda 的 Python 3.11，可把 `.build-venv\Scripts\python.exe` 换成该环境的
`python.exe` 完整路径。推荐使用只有本项目依赖的构建环境，避免把开发工具和额外 GUI 框架打进去。
这里的虚拟环境只用于发布构建，最终用户不需要它，也没有新增用户启动脚本。

如果 Inno Setup 安装路径不同：

```powershell
.\.build-venv\Scripts\python.exe tools\build_windows.py --iscc "D:\Tools\Inno Setup 6\ISCC.exe"
```

成功后产生：

```text
dist/roLabelImg/roLabelImg.exe
dist/roLabelImg/_internal/...          # 必须完整保留的运行库和资源
release/roLabelImg-Setup-2.0.0-win-x64.exe
release/roLabelImg-2.0.0-win-x64-portable.zip
release/SHA256SUMS.txt
release/build-info.json
```

用户下载 Setup.exe 即可安装。绿色版用户需要完整解压 ZIP，不能单独拷贝 exe。
构建脚本会运行 exe 的 `--smoke-test`，失败则停止，不继续生成安装包。
报告在 `build/frozen-smoke.json`；这是轻量运行库检查，仍需人工验收大影像、网络盘及实际编辑。

### 4.2 打包方式与资源

采用 PyInstaller **onedir + windowed**：主程序不弹出控制台，运行库位于 `_internal`。
Qt、NumPy、lxml 使用 PyInstaller 的 hooks；Rasterio 额外收集全部子模块、数据、二进制以及
Windows wheel 的 `.libs` 目录。GDAL / PROJ 的数据路径由 runtime hook 指向包内文件。
不要依赖开发电脑的 Conda、GDAL 或 PROJ 环境变量。

资源仍以 `roLabelImg.py` 的 `__file__` 为基准，PyInstaller 会为它提供包内位置；
`data/` 和 `USER_GUIDE.md` 明确包含在 spec 中。
图标来自现有 `resources.py`，无须在用户电脑运行 pyrcc5。
如以后更新图标，先重新生成 resources.py，再重新构建。

当前未配置自定义 exe 文件图标；可准备 `.ico` 后给 spec 中 EXE 增加 icon 路径，
并在 installer.iss 增加 SetupIconFile。应用窗口已有原项目图标。

## 5. 安装与升级配置

`packaging/installer.iss` 的关键设置：

```ini
AppId={{C5A4A2D8-A96A-450E-9B52-6E0D65BE1D37}
DefaultDirName={localappdata}\Programs\roLabelImg
PrivilegesRequired=lowest
UsePreviousAppDir=yes
AppMutex=Local\roLabelImg-running
```

**不要因版本变化重新生成 AppId。** 固定身份让新安装包识别旧安装，沿用目录和卸载记录。
默认按当前用户安装，不需要管理员权限；其他 Windows 用户需各自安装。
已经运行的软件通过命名互斥量告知安装器，安装器会提示先关闭它，避免强制结束未保存的标注。
快捷方式在开始菜单，桌面快捷方式可选。
当前安装器使用英文向导，应用界面保持中文。

升级会替换 exe，并先清理安装目录内的 `_internal`，避免遗留旧运行库。
`_internal` 是程序专用目录，不能存放用户影像或标注。
安装和卸载都不删除用户的标签库、配置或影像目录。

| 内容 | 位置 |
| --- | --- |
| 程序 | 默认 `%LOCALAPPDATA%\Programs\roLabelImg` |
| 本地类别名称、颜色和 ID | 原有 `%APPDATA%\roLabelImg\labels.json` |
| 窗口、路径和更新检查选项 | 原有 QSettings，Windows 使用当前用户设置 |
| 客户端异常日志 | `%APPDATA%\roLabelImg\logs\client.log`，轮转保留 |
| JSON / XML 标注 | 用户选择的保存目录，保持现有规则 |

未修改 QApplication 的组织名和软件名，确保既有类别库和设置路径兼容。
客户端版本、安装目录或构建目录不能作为用户类别库的保存位置。

## 6. 客户端更新核心逻辑

源码已接入顶部 **版本与更新**：显示当前版本，手动检查，以及启动检查开关。
已打包的客户端启动 5 秒后可检查一次，每天最多自动检查一次；源码运行不自动联网。
后台使用标准库 HTTPS 与 QThread，不依赖 Qt5 在开发机器上找到的外部 OpenSSL DLL。
连接和读取设置超时，元数据上限 1 MiB；关闭时请求取消，并使用现有线程生命周期管理。

请求地址：

```text
https://api.github.com/repos/YG817/rolabelImg-master/releases/latest
```

核心函数可独立使用与测试：

```python
from libs.update_checker import release_information

# release_json 是 GitHub API 的返回对象。
info = release_information(release_json, current='2.0.0')
if info:
    # info 包含 version、url、notes。
    # 在界面提示用户，点击后调用系统浏览器。
    print(info['version'], info['url'])
```

实际应用已经处理线程、界面及关闭事件，不要在 GUI 主线程直接调用网络函数。
仅接受配置仓库的 HTTPS 安装包地址、精确文件名及已上传的有效附件。
Release body 在窗口内以纯文本显示，避免把发布说明当作可执行 HTML。
网络失败、限流、仓库没有 Release 不影响标注；自动检查静默失败，手动检查在状态栏说明原因。
弹窗有“打开浏览器下载安装包”和“复制下载链接”，便于默认浏览器失败时继续操作。

**这里没有自动替换 exe 的代码。** 下载和安装由用户执行，符合当前更新方式。
收到提示后用户应：保存 → 下载 → 退出软件 → 安装新版本 → 重新打开。
SHA256SUMS.txt 用于手动核对下载文件，客户端不负责校验浏览器下载到本地的文件。

## 7. 首次上传 GitHub

仓库当前为空，本地目录当前也不是 Git 仓库。先把配置、源码和测试提交到主分支。
下面是给你执行的示例，当前没有代你执行提交或推送：

```powershell
git init
git branch -M main
git remote add origin https://github.com/YG817/rolabelImg-master.git
git add .
git commit -m "Prepare Windows client releases and manual updates"
git push -u origin main
```

提交前检查 `git status`，不要把真实影像、私人标注、账户密钥或构建产物提交到公开仓库。
大影像可保留在仓库之外；测试用的轻量样本按项目测试需求保留。
GitHub 仓库需公开，Actions 需要启用；工作流使用该仓库的 GITHUB_TOKEN，发布 job 配置
`contents: write`，不需要把个人访问令牌写进代码。

第一次可以先去 Actions → Windows release → Run workflow，验证构建并下载 workflow artifacts。
手动运行只生成构建附件，不创建 Release。
验收通过后，再推送正式标签：

```powershell
git tag v2.0.0
git push origin v2.0.0
```

工作流会校验标签和 APP_VERSION 一致，然后创建草稿 Release 并上传 4 类构建产物。
到仓库 Releases 中打开草稿，确认安装包、版本、说明，完成人工测试后点 Publish release，
并让它成为 latest 正式版。草稿发布前，客户端不会提示这个版本。
若构建中断后重试，允许覆盖同标签草稿的附件；不会覆盖已正式发布的 Release。
不要修改已经发布版本的安装包，应增加版本号另发新版。

## 8. 后续发版例子

以 2.0.1 为例：

1. 修复问题，修改 `app_version.py`：`APP_VERSION = '2.0.1'`。
2. 修改 `packaging/RELEASE_NOTES.md`，说明具体修改与已知限制。
3. 本地运行测试，提交代码并推到 main。
4. 推送 `v2.0.1` 标签，等待 Actions 创建草稿和附件。
5. 在干净 Windows 环境从 2.0.0 安装包升级到 2.0.1，确认原类别、颜色、标注目录不丢失。
6. Publish release；2.0.0 用户在下次检查时会收到提示。

不以推送源码到 main 代替发布 Release，也不在两个版本之间更换 AppId。
旧客户端的测试可通过“版本与更新 → 检查更新”触发，不必等自动检查周期。

## 9. 发布验收与排错

建议在一台没有 Python、Conda、GDAL 的 Windows 10/11 x64 电脑或虚拟机验收：

- 安装、开始菜单启动、卸载；中文用户名和含空格路径。
- 单图、目录、UNC 网络盘路径；普通图和实际 1–2 GB TIFF。
- 缩放后的细节读取、中心经纬度、旋转框、连续编辑、多选删除、撤销。
- COCO / VOC 保存并重开，原始像素坐标及现有标注保存规则。
- 自定义标签和颜色在覆盖升级后保留，卸载不删除用户目录。
- 断网启动正常；手动检查失败有状态提示；未发布草稿不提示升级。
- 从旧版本查到新版本，浏览器正确下载 Setup；软件未退出时安装器提示关闭。

若报缺少 GDAL / PROJ 文件，检查 `_internal/rasterio/gdal_data`、`proj_data` 和二进制目录；
若报 Qt platform plugin，检查 `_internal` 的 Qt plugins/platforms/qwindows.dll。
不要单独移动 exe。启动失败可查看 client.log，打包自检失败查看 frozen-smoke.json。

当前本地没有 PyInstaller 和 Inno Setup 编译器，也只有不适于构建的 Python 3.10.0。
因此这里提供的是已接入项目并完成源码验证的发布配置，尚未声称生成或验收了真实 Setup.exe。
首次 Actions 的 frozen smoke 和干净系统人工验收必须完成后再发布。

## 10. 发布材料与签名

当前工作目录缺少原始 LICENSE；公开发布前应从项目上游取得并保留许可证和版权声明，
结合 THIRD_PARTY_NOTICES.md 补齐实际打包依赖的授权材料。
PyQt5 使用 GPL v3 或商业许可，需要根据你的分发方式选择合适的授权安排。

目前构建产物未签名。需要 Windows Authenticode 签名时，流程应为：
PyInstaller → 签 exe → 编译安装器 → 签 Setup.exe → 生成最终 SHA256 → 发布。
证书和私钥由发布环境保存，不能放在源码或客户端内；签名后应重新计算 SHA256。
当前 build_windows.py 是未签名基线，签名流程需在相应步骤接入实际证书服务。

## 官方参考

- PyInstaller 使用与平台构建：https://pyinstaller.org/en/stable/usage.html
- 打包后的资源定位：https://pyinstaller.org/en/stable/runtime-information.html
- PyInstaller hooks：https://pyinstaller.org/en/stable/hooks.html
- Python 3.10.0 限制：https://pypi.org/project/pyinstaller/
- Inno Setup 下载：https://jrsoftware.org/isdl.php
- Inno Setup AppId：https://jrsoftware.org/ishelp/topic_setup_appid.htm
- 当前用户安装：https://jrsoftware.org/ishelp/topic_setup_privilegesrequired.htm
- 安装时运行状态检测：https://jrsoftware.org/ishelp/topic_setup_appmutex.htm
- GitHub Releases API：https://docs.github.com/en/rest/releases/releases
- PyQt 许可说明：https://www.riverbankcomputing.com/software/pyqt/intro
