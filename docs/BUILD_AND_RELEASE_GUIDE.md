# roLabelImg：Windows 构建、安装包与 GitHub 发布操作手册

项目：<https://github.com/YG817/rolabelImg-master>。
工作目录：`D:\roLabelImg-master`。以下命令均在 PowerShell 中执行。

当前本地版本为 2.0.2，包含区域编辑、保存恢复与软件内下载更新，按用户要求暂不上传。2.0.1 已正式发布；本文保留当时的 2.0.1 示例，后续发布请将版本号、标签和文件名统一替换为 2.0.2。
说明中的 2.0.1 是本次版本示例，以后发布 2.0.2 时，版本、标签和文件名一起递增。
下面的上传及发布命令供你选择执行；创建本手册不等于已经上传或发布 2.0.1。

## 一、先区分三个动作

| 动作 | 工具 | 结果 |
|---|---|---|
| 把 Python 程序构建为可运行的软件 | PyInstaller | dist 下的 roLabelImg.exe 和 _internal 运行库 |
| 把完整软件做成安装包 | Inno Setup | release 下的带版本号 Setup.exe |
| 把版本提供给用户下载 | GitHub Releases | 下载附件、版本说明，以及客户端可检查的正式版本 |

git push 负责代码和标签。安装包放到 Releases，不能用强制添加忽略文件的方式放进 Git 历史。
程序采用 onedir，运行时必须带上整个目录；用户安装 Setup.exe 后不需要安装 Python。

## 二、环境准备：已有环境不用重复创建

本地已经有 `.build-venv`，Python 3.12.10 和所需依赖。本机 Inno Setup 7 编译器路径是：

```text
D:\Inno Setup 7\ISCC.exe
```

先确认：

```powershell
cd D:\roLabelImg-master
.\.build-venv\Scripts\python.exe --version
Test-Path "D:\Inno Setup 7\ISCC.exe"
```

换到一台新电脑时，安装 Windows x64 Python 3.12 和 Inno Setup 6 或 7，然后执行：

```powershell
cd D:\roLabelImg-master
py -3.12 -m venv .build-venv
.\.build-venv\Scripts\python.exe -m pip install -r packaging\requirements-windows.txt
```

使用其他环境时，用该环境的 python.exe 绝对路径替换 `.build-venv\Scripts\python.exe`。
不要混用其他 Python 的 pip；安装依赖始终使用同一个解释器的 `-m pip`。

## 三、每次构建前：确定版本并测试

1. 修改 `app_version.py` 的 APP_VERSION，例如 `2.0.1`。
2. 同步 `setup.cfg` 的 current_version，保持旧版本管理工具配置一致。
3. 编辑 `packaging/RELEASE_NOTES.md`，写明真实变化和验收情况。
4. 保存代码并运行测试：

```powershell
cd D:\roLabelImg-master
.\.build-venv\Scripts\python.exe -m pytest -q
```

本地已将 APP_VERSION 和 setup.cfg 同步设为 2.0.2；发布这一版时使用 v2.0.2 标签，不复用 v2.0.1。
2.0.0 已发布，不应重打同名安装包并替换正式版本；使用 2.0.1 发布更新。

## 四、本地构建：两种方式

### 方式 A：一个命令生成所有文件

```powershell
.\.build-venv\Scripts\python.exe tools\build_windows.py --iscc "D:\Inno Setup 7\ISCC.exe"
```

脚本依次执行：生成 EXE 文件版本 → PyInstaller 构建 → EXE 基础自检 →
Inno Setup 编译 → 生成便携 ZIP → SHA256 校验 → 构建信息。

成功后有：

```text
D:\roLabelImg-master\dist\roLabelImg\
├── roLabelImg.exe
└── _internal\...

D:\roLabelImg-master\release\
├── roLabelImg-Setup-2.0.1-win-x64.exe
├── roLabelImg-2.0.1-win-x64-portable.zip
├── SHA256SUMS.txt
├── build-info.json
└── update.json
```

控制台最终出现 `Release artifacts: D:\roLabelImg-master\release` 表示整套构建结束。
`Build complete!` 仅表示 PyInstaller 完成，后面还有安装包等步骤。

### 方式 B：分别构建 EXE 和 Setup

先生成主程序：

```powershell
.\.build-venv\Scripts\python.exe tools\build_windows.py --exe-only
```

输出 `Client executable: ...` 后，直接双击 `dist\roLabelImg\roLabelImg.exe` 试用。
这一步不需要 Inno Setup，不生成安装包和发布 ZIP。

确认主程序后，把已经生成的完整程序目录制作成安装包：

```powershell
.\.build-venv\Scripts\python.exe tools\build_windows.py --installer-only --iscc "D:\Inno Setup 7\ISCC.exe"
```

此步骤不重新运行 PyInstaller，会再次执行 EXE 基础自检，并核对 EXE 内部版本与
APP_VERSION 一致，再生成安装包、ZIP、校验和及构建信息。
更改程序代码或 EXE 图标后，应先重新执行 --exe-only；仅更改安装器设置时可以复用 EXE。
版本核对只能检查版本号，不能判断你是否在同一版本内又改过源码。

可单独调用 Inno 编译器，例如：

```powershell
& "D:\Inno Setup 7\ISCC.exe" /DAppVersion=2.0.1 /DSourceDir="D:\roLabelImg-master\dist\roLabelImg" /DOutputDir="D:\roLabelImg-master\release" "D:\roLabelImg-master\packaging\installer.iss"
```

这个原始命令只编译安装器，不验证 EXE 版本、不生成 ZIP 或更新 SHA256SUMS。
日常操作优先用构建脚本，保证五个发布文件来自同一轮构建。`update.json` 包含版本、日志、安装包地址、大小和 SHA-256；必须与安装包一起上传。
运行 spec 前还需要构建脚本生成 build/windows-version.txt，所以不建议绕过它直接运行 PyInstaller。

## 五、安装包 logo：文件图标与向导插图分开

旧安装包显示 Inno Setup 的图标，是因为未指定 SetupIconFile。
旧 EXE 的文件图标同样没有配置；Qt 窗口图标不能自动变成 Windows EXE 的图标。

现已接入：

```text
icons/expert2.png       现有窗口图标，黑色标签图案，48×48
icons/roLabelImg.ico    相同图案转换成 Windows 图标
```

`packaging/roLabelImg.spec`：

```python
exe = EXE(..., icon=str(root / 'icons' / 'roLabelImg.ico'), ...)
```

`packaging/installer.iss`：

```ini
[Setup]
SetupIconFile=..\icons\roLabelImg.ico
UninstallDisplayIcon={app}\roLabelImg.exe
```

程序文件、安装包/卸载程序、快捷方式与卸载列表使用这套应用图标。
重建后才会改变产物，GitHub 上的 2.0.0 附件不会自动变化。

以后换成你自己的 logo，有两种做法：

- 直接将标准 ICO 放到 `icons/roLabelImg.ico`，推荐包含 16、32、48、64、256 尺寸。
- 将正方形 PNG 转成 ICO：

```powershell
.\.build-venv\Scripts\python.exe tools\make_windows_icon.py --source "D:\MyLogo\logo.png"
```

转换工具保留原图案和尺寸，不把旧 48×48 图片伪装成高清图。
如果同时想更换应用窗口和任务栏的图案，还应把新窗口图放到 icons/expert2.png，重新生成资源：

```powershell
.\.build-venv\Scripts\pyrcc5.exe -o resources.py resources.qrc
```

再重新构建 EXE 和安装包，把 ICO、PNG 和 resources.py 一起提交。

安装向导右上角图片和欢迎页左侧插图是独立设置：

```ini
WizardSmallImageFile=..\icons\installer-small.bmp
WizardImageFile=..\icons\installer-welcome.bmp
```

上面是可选示例，当前未配置这两张图片。不要在文件不存在时直接添加。
Inno Setup 6.4.3 使用 BMP 兼容性更好；6.5.2 及以后才支持在这两个位置直接使用 PNG。
欢迎页图片应按 164:314 比例准备，不能把正方形 logo 拉伸成竖图。
若 Windows 资源管理器仍显示旧图标，先确认正在查看 2.0.1 文件，刷新或重启资源管理器，
再检查图标缓存；不要因此反复重新上传正式版本。

## 六、发布前先上传源码

当前本地已经初始化 Git、关联 origin、设置用户信息；这些步骤不需要重复执行。
如果在 GitHub 网页上修改过文件，先在工作目录干净时同步 main：

```powershell
git fetch origin
git merge origin/main
```

有未提交修改时，先提交本次工作，再合并 origin/main；遇到冲突应解决后再上传。
不要强制覆盖 main。

本次版本准备好后：

```powershell
git add .
git status
git commit -m "Release roLabelImg 2.0.1 with application icons"
git push origin main
```

确认提交中包含 icons/roLabelImg.ico、spec、installer.iss、版本号、构建工具和文档。
.build-venv、build、dist、release 均被忽略；它们留在本地，不进入代码仓库。

## 七、发布方式 1：GitHub 自动构建，推荐用于日常版本

适用于希望每次发版按相同流程测试、打包并生成草稿的情况。

1. 完成上一节的提交和 main 上传。
2. 确认 Actions 中 Windows release 工作流处于启用状态。
3. 推送与 APP_VERSION 对应的标签：

```powershell
git tag -a v2.0.1 -m "roLabelImg 2.0.1"
git push origin v2.0.1
```

4. 打开 <https://github.com/YG817/rolabelImg-master/actions>，进入新的 Windows release 任务。
5. 等 Test source、Build client and installer、Create draft release 均成功。
6. 登录 YG817，打开 <https://github.com/YG817/rolabelImg-master/releases>，查看 Draft 草稿。
7. 下载草稿中的安装包，测试安装和升级；检查五个发布附件和版本说明。
8. 不勾选预发布，将其设为最新版本，点击 Publish release。

这个方式会在 GitHub 的 Windows 环境重新构建；不需要上传本机的 release 文件。
Artifacts 是构建下载区；Releases 是面向用户的发布区。草稿只有有权限的登录账号能看到。
推送普通 main 提交不会触发当前发布工作流，也不会通知客户端升级。

## 八、发布方式 2：本地构建，网页手动上传

适用于你要发布已经在本机生成并测试的五个文件。

为了避免标签推送触发另一套云端构建，先在 Actions → Windows release → 菜单中选择
Disable workflow。只在这次手动发布期间暂停，结束后重新启用。

1. 完成本地构建和安装测试。
2. 上传源码到 main，确保本地生成文件的版本和代码与这次提交一致。
3. 创建并上传版本标签：

```powershell
git tag -a v2.0.1 -m "roLabelImg 2.0.1"
git push origin v2.0.1
```

4. Releases → Draft a new release。
5. Choose a tag 选择已经上传的 v2.0.1；标题写 roLabelImg 2.0.1。
6. 填写版本说明，拖入 release 下本版本的五个文件：

```text
roLabelImg-Setup-2.0.1-win-x64.exe
roLabelImg-2.0.1-win-x64-portable.zip
SHA256SUMS.txt
build-info.json
update.json
```

7. 等上传完成，检查附件，点击 Publish release。
8. 返回 Actions，Enable workflow，供后续自动发布使用。

不要把整个 release 文件夹上传到 Code 页面，也不要上传 dist 的零散运行库。
release 文件夹可能保留以前版本的产物，手动选择本版本这五个文件。这里的 2.0.1 是历史示例，实际发布当前本地版本时替换为 2.0.2；不要修改已经发布的旧版附件。
标签已经存在时不要重复创建；先核对它指向的提交。正式版本不覆盖、不移动旧标签。

## 九、发布方式 3：本地构建，GitHub CLI 上传

这和方式 2 使用相同的本地文件，只是用 gh 命令代替网页拖拽。
Git 与 gh 是两个工具；只有 Git 无法上传 Release 附件。

首次安装 GitHub CLI 并登录：

```powershell
winget install --id GitHub.cli -e
```

安装后重新打开 PowerShell，再执行：

```powershell
cd D:\roLabelImg-master
gh auth login --hostname github.com --git-protocol https --web
gh auth status
```

按提示在浏览器登录 YG817。不要把访问令牌写入项目文件。
先完成本地构建、源码上传。暂停自动工作流、推送标签，然后创建草稿：

```powershell
gh workflow disable windows-release.yml --repo YG817/rolabelImg-master

git tag -a v2.0.1 -m "roLabelImg 2.0.1"
git push origin v2.0.1

gh release create v2.0.1 --repo YG817/rolabelImg-master --verify-tag --draft --title "roLabelImg 2.0.1" --notes-file packaging/RELEASE_NOTES.md

gh release upload v2.0.1 release/roLabelImg-Setup-2.0.1-win-x64.exe release/roLabelImg-2.0.1-win-x64-portable.zip release/SHA256SUMS.txt release/build-info.json release/update.json --repo YG817/rolabelImg-master

gh release view v2.0.1 --repo YG817/rolabelImg-master --web
```

核对附件并测试通过后，正式发布并恢复自动工作流：

```powershell
gh release edit v2.0.1 --repo YG817/rolabelImg-master --draft=false --latest
gh workflow enable windows-release.yml --repo YG817/rolabelImg-master
```

每一步成功后再执行下一步。上传失败时保留草稿，完成附件后再正式发布。
草稿已存在时使用 gh release upload，不重复 create；同名附件替换应限于未发布草稿，
并将对应 ZIP、SHA256SUMS 和 build-info 一起保持一致。

## 十、只想在云端试打包：Run workflow

Actions → Windows release → Run workflow → 选择 main → Run workflow。
成功后到任务底部下载 windows-release 附件。
当前配置的这种手动运行只生成构建附件，不创建 Release 草稿；正式发布仍选上面的方式之一。
试构建是检验构建配置，不会让客户端收到更新提示。

## 十一、版本更新如何到达用户

```text
发布正式 2.0.1，带精确命名的 Setup 附件
  → 2.0.0 客户端检查 GitHub 最新正式版本
  → 提示有新版本
  → 新客户端在更新窗口显示日志，并直接下载、显示进度
  → 用户点“退出并安装”，处理未保存标注、退出软件
  → 运行 Setup，覆盖安装
```

客户端自动检查在打包版启动后触发，按 24 小时间隔限制请求；也可以打开“版本与更新”手动检查。
它比较版本号，不会自动替换程序。草稿和预发布版不会进入正常升级提示。
新客户端优先下载 `releases/latest/download/update.json`，不使用 REST 查询接口获取该文件。旧发布缺少它时兼容 API；受限按服务器等待时间停止请求。成功查到的新版本会缓存，查询受限时仍可打开缓存日志、下载或使用已校验的本地安装包。
保留 installer.iss 的 AppId、安装目录规则和用户数据路径，升级后标签和设置才可继续使用。

## 十二、遇到问题时按阶段检查

| 现象 | 检查与处理 |
|---|---|
| nothing added to commit | 先 git add .，再 git commit |
| main 上传被拒绝 fetch first | fetch 并合并 origin/main，再正常 push |
| 找不到 ISCC.exe | 使用本机正确的 --iscc 路径 |
| EXE 自检版本不匹配 | 重建 --exe-only，再生成安装包 |
| Actions 红叉 | 打开第一个失败步骤，查看日志；test-diagnostics 保存测试记录 |
| 没有草稿 | 检查是标签触发还是 Run workflow；后者当前不会建草稿 |
| 创建草稿成功但列表看不到 | 登录有权限的 YG817 账号，打开 Releases 列表 |
| 客户端没提示新版本 | 检查版本更高、正式发布、最新版本与 Setup 文件名一致 |
| 文件图标仍旧 | 查看新版本产物并刷新资源管理器；向导插图是另一个配置 |

旧任务的 Re-run 使用旧提交。修复之后应提交并触发包含修复代码的新版本。
正式发布后使用下一个版本号，不用强制推送改写发布标签。

## 官方资料

- PyInstaller 图标与构建：https://pyinstaller.org/en/stable/usage.html
- Inno Setup 安装包图标：https://jrsoftware.org/ishelp/topic_setup_setupiconfile.htm
- Inno Setup 向导右上角图片：https://jrsoftware.org/ishelp/topic_setup_wizardsmallimagefile.htm
- Inno Setup 欢迎页图片：https://jrsoftware.org/ishelp/topic_setup_wizardimagefile.htm
- GitHub Releases：https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository
- GitHub CLI 创建草稿：https://cli.github.com/manual/gh_release_create
- GitHub CLI 上传附件：https://cli.github.com/manual/gh_release_upload
