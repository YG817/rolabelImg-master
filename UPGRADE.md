# 大影像加载、COCO 与标签管理

本次修改使用 Python 3、PyQt5 和 Rasterio。在已安装依赖的 Python 环境中运行 `python roLabelImg.py`。

新环境安装：

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe roLabelImg.py
```

## 大影像

- 图像读取、解码放在后台线程。状态栏右侧显示旋转圆圈，窗口仍可拖动、缩放。
- TIFF / GeoTIFF / BigTIFF、IMG、VRT、JP2 使用 Rasterio。先生成最长边不超过 2048 像素的预览；放大、滚动时后台读取可见区域，输出最长边最多 4096 像素。
- 普通小图使用 Qt 后台解码，超过 6400 万像素的图像转交 Rasterio。
- 画布、框、旋转框、导出的图像宽高始终使用**原图像素坐标**。地理坐标系不参与标注坐标转换。
- GDAL 块缓存设为 64 MiB，最多同时有一个预览读取和一个细节读取；快速切图仅保留最新待加载任务，并忽略旧图结果。
- 优先使用影像声明的 RGB 波段，否则使用前三波段；单波段显示为灰度。非 8 位数据依据预览的 2%–98% 范围拉伸，细节沿用相同范围。原影像不会被改写。
- 没有金字塔的压缩影像、特别大的条带/块、网络磁盘仍可能读取较慢。缩略显示并不意味着所有 TIFF 编码都具有固定内存开销；GDAL 仍需解码文件内部的数据块。

## 导出与读取

右侧可选择 COCO JSON 或 Pascal VOC XML，首次默认 COCO，后续记住上次格式。当前的保存保护、路径规则与新操作详见 `USER_GUIDE.md`。

- 保留原项目每张影像一个标注文件的保存方式，例如 `scene.tif` 对应 `scene.json` 或 `scene.xml`。COCO 文件包含 `images`、`annotations`、`categories`，不是整个目录合并为一个文件。
- COCO `bbox` 是 `[x, y, width, height]`，`segmentation` 保存四个顶点，`area` 使用多边形实际面积。旋转方向、是否旋转、difficult 保存在 `attributes` 中，供本软件重新编辑。
- COCO 框允许零坐标，保留浮点精度；VOC 保持项目原有整数普通框和 `robndbox` 旋转框约定。
- 打开影像时读取最近修改的匹配标注，两种格式同时间时优先当前格式，不做合并；保存前检查来源以防覆盖其他影像。
- “Open Annotation” 可以选择 JSON 或 XML。支持从包含多张图的 COCO 中按文件名读取当前图像；普通 bbox-only 标注也可读取。非四点分割会以 bbox 导入，因为该编辑器仅支持矩形。
- COCO 类别 ID 来自本地类别库，重命名保留 ID，删除后不复用 ID。同一类别库导出的不同文件类别 ID 保持一致。
- 保存 VOC 不再重新解码原图；COCO 和 VOC 均采用临时文件写入后替换。

## 调整框

角点可点击范围为约 14 个屏幕像素，不受缩放比例影响，角点显示尺寸也已增大。选中框后，或者从右侧列表选中框后，可以直接左键拖动角点调整大小；选中框的角点优先响应。旋转框的直角约束使用向量投影，适用于 90° 等方向。

## 类别库

点击右侧 **Manage labels / 管理标签**，可以新增、重命名、删除以及修改类别颜色。新建标注使用的新类别会自动保存，下次打开仍可选择；同类别默认使用相同颜色。

- Windows 默认文件位置：`%APPDATA%\roLabelImg\labels.json`（Qt 的 AppDataLocation）。备份此文件即可备份类别名称、ID、颜色。
- 重命名同步更新当前影像的对应标注，需要保存当前影像以更新导出文件。
- 当前影像仍在使用的类别不能直接删除；先修改或删除相应标注后即可删除类别。
- 类别管理不会批量改写其他影像已有的标注文件；重新打开包含旧类别的历史标注时，该类别会重新进入类别库。
- 预定义类别文件只在本地类别库不存在时导入，避免已删除类别在重启后重新出现。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pip install pytest
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe tests\benchmark_large_raster.py
```

基准脚本在临时目录生成实际写入的 1,812,013,322 字节无压缩 RGB TIFF，24576×24576 像素，完成后清理测试影像。结果写入 `tests/benchmark_result.json`。本机一次运行预览 1.906 秒，细节 0.359 秒，采样工作集峰值 214.54 MiB，界面定时器最大间隔 109 ms。该结果来自刚生成的合成影像与本机缓存环境，不代表所有遥感格式或磁盘的性能保证。
