# roLabelImg 2.0.2 构建、上传与发布命令

命令适用于本项目和 Windows PowerShell。每一步成功后再执行下一步；遇到报错先停下来处理。版本保持 2.0.2。

## 1. EXE（已完成）

2026-10-12 已使用当前源码构建，生成 `D:\roLabelImg-master\dist\roLabelImg\roLabelImg.exe`，版本信息为 2.0.2，打包自检通过。

如需重新构建：

```powershell
cd D:\roLabelImg-master
.\.build-venv\Scripts\python.exe tools\build_windows.py --exe-only
```

打开程序进行人工检查：

```powershell
& ".\dist\roLabelImg\roLabelImg.exe"
```

这是目录形式的程序，必须保留整个 `dist\roLabelImg`，尤其是同目录的 `_internal`。不能只复制一个 EXE。

## 2. 使用现有 EXE 构建 Setup 和绿色版

本机已检测到 Inno Setup 编译器 `D:\Inno Setup 7\ISCC.exe`。先检查程序运行正常，再执行：

```powershell
cd D:\roLabelImg-master
.\.build-venv\Scripts\python.exe tools\build_windows.py --installer-only --iscc "D:\Inno Setup 7\ISCC.exe"
```

脚本会检查 EXE 版本并进行打包自检，然后生成以下五个发布文件：

| 文件 | 用途 |
| --- | --- |
| `release\roLabelImg-Setup-2.0.2-win-x64.exe` | 安装包 |
| `release\roLabelImg-2.0.2-win-x64-portable.zip` | 绿色版，完整解压后使用 |
| `release\SHA256SUMS.txt` | 文件校验值 |
| `release\build-info.json` | 构建信息 |
| `release\update.json` | 软件内检查版本和下载更新使用的清单 |

看到 `Release artifacts:` 才表示这一阶段成功。当前目录还有以前生成的同名安装包，不能把文件存在当作本次构建成功；必须以上述命令的成功结果为准。

查看生成时间：

```powershell
Get-Item .\release\roLabelImg-Setup-2.0.2-win-x64.exe, .\release\roLabelImg-2.0.2-win-x64-portable.zip, .\release\SHA256SUMS.txt, .\release\build-info.json, .\release\update.json | Select-Object Name, Length, LastWriteTime
```

安装前关闭正在运行的 roLabelImg。需要测试安装时执行：

```powershell
& ".\release\roLabelImg-Setup-2.0.2-win-x64.exe"
```

也可以以后一次构建 EXE、Setup 和绿色版：

```powershell
.\.build-venv\Scripts\python.exe tools\build_windows.py --iscc "D:\Inno Setup 7\ISCC.exe"
```

## 3. 上传源码：所有发布方式共用

仓库已经初始化并配置 origin，不要再次执行 `git init` 或 `git remote add origin`。

```powershell
cd D:\roLabelImg-master
git add .
git status
git commit -m "Release roLabelImg 2.0.2"
git fetch origin
git merge origin/main
git push origin main
```

`git status` 中应包含本轮新增的 `libs`、`tests`、文档与已有源码修改。`.gitignore` 已排除构建环境、`dist`、`build` 和 `release`，安装包通过 Release 附件上传。

先提交再合并，可保留本轮本地修改。若有冲突，解决后提交再推送，不要强制推送。若合并带来了程序源码、依赖或打包配置变化，重新执行上一节的一次性构建命令，以保证产物与最终提交一致。

这次本机读取 GitHub 远程时连接 443 端口失败。如 `fetch` 或 `push` 仍因网络失败，请恢复 GitHub 连接后重试，不要继续发布步骤。

## 4A. 方式一：GitHub 自动构建并生成草稿（推荐）

完成源码上传后：

```powershell
git tag -a v2.0.2 -m "roLabelImg 2.0.2"
git push origin v2.0.2
```

这会触发项目的 `Windows release` 工作流。仅推送 main 不会触发它。工作流会测试源码、重新构建 EXE 和安装包、上传发布附件并创建草稿。

1. 打开 https://github.com/YG817/rolabelImg-master/actions ，等待这次 `Windows release` 全部成功。
2. 打开 https://github.com/YG817/rolabelImg-master/releases ，找到 2.0.2 草稿。
3. 检查标签为 `v2.0.2`，日志正确，附件包含上述五个文件。
4. 确认后点击 **Publish release**，取消预发布选项，并将它设为 Latest。

这个方式的附件由 GitHub 构建，不需要再上传本地生成的同名文件。草稿期间普通用户的客户端不会收到新版本。

若要用命令发布已经由工作流准备好的草稿，在安装并登录 GitHub CLI 后执行：

```powershell
gh release view v2.0.2 --repo YG817/rolabelImg-master --web
gh release edit v2.0.2 --repo YG817/rolabelImg-master --draft=false --latest
```

## 4B. 方式二：上传本地构建的文件，全程使用命令

和方式一二选一。本机当前没有 GitHub CLI；先安装：

```powershell
winget install --id GitHub.cli -e
```

关闭并重新打开 PowerShell，然后：

```powershell
cd D:\roLabelImg-master
gh auth login --hostname github.com --git-protocol https --web
gh auth status
```

在浏览器登录 YG817。不要把登录令牌写进客户端或源码。

已完成第 2 节的最新本地构建、第 3 节的源码推送后，先暂停工作流，避免推送标签同时触发另一套自动构建：

```powershell
gh workflow disable windows-release.yml --repo YG817/rolabelImg-master
git tag -a v2.0.2 -m "roLabelImg 2.0.2"
git push origin v2.0.2
```

创建草稿并上传明确的五个文件，不能上传 `release/*`，因为目录中还有旧版本：

```powershell
gh release create v2.0.2 --repo YG817/rolabelImg-master --verify-tag --draft --title "roLabelImg 2.0.2" --notes-file packaging/RELEASE_NOTES.md
gh release upload v2.0.2 .\release\roLabelImg-Setup-2.0.2-win-x64.exe .\release\roLabelImg-2.0.2-win-x64-portable.zip .\release\SHA256SUMS.txt .\release\build-info.json .\release\update.json --repo YG817/rolabelImg-master
gh release view v2.0.2 --repo YG817/rolabelImg-master --web
```

检查草稿后正式发布，并恢复工作流：

```powershell
gh release edit v2.0.2 --repo YG817/rolabelImg-master --draft=false --latest
gh workflow enable windows-release.yml --repo YG817/rolabelImg-master
```

若中途失败，可先恢复工作流，再处理失败原因。若标签或 Release 已经存在，先查看当前状态；不要重复创建标签、移动远程标签或覆盖已发布版本。若走过方式一且已经生成正确的草稿，直接检查并发布即可。

## 4C. 方式三：网页上传本地文件

先按方式二暂停自动工作流并推送版本标签。然后到仓库 Releases 页面点击 **Draft a new release**，选择已有标签 `v2.0.2`，填写标题与 `packaging/RELEASE_NOTES.md` 内容，拖入本轮新生成的五个文件。

先保存草稿检查；确认后发布并设为 Latest。最后恢复 `windows-release.yml` 工作流。不要把安装包上传到仓库 Code 页面。

## 5. 发布后的检查

发布页应为 https://github.com/YG817/rolabelImg-master/releases/tag/v2.0.2 。检查安装包和 `update.json` 均可下载。

可在旧版客户端检查更新，核对更新日志与下载入口；当前 2.0.2 客户端检查 2.0.2 应显示已是最新版本。旧客户端是否能在软件内直接下载取决于旧版是否已具备下载模块；未具备时从发布页下载安装即可。

CLI 参数说明：[创建 Release](https://cli.github.com/manual/gh_release_create)、[上传附件](https://cli.github.com/manual/gh_release_upload)、[发布草稿及设为 Latest](https://cli.github.com/manual/gh_release_edit)。
