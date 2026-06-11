# YVM-SLAM

YVM-SLAM 是基于 ORB-SLAM3 的视觉 SLAM 工程，并集成了 YOLOv8/ONNX Runtime 相关的语义感知能力。仓库包含核心 C++ 源码、示例程序、配置文件、第三方依赖源码、模型文件和评估脚本。

## 目录说明

- `src/`：核心 C++ 实现。
- `include/`：核心头文件。
- `Examples/`：常用数据集和相机的运行入口与配置文件。
- `Examples_old/`：旧版配置格式示例。
- `Thirdparty/`：DBoW2、g2o、Sophus、ONNX Runtime 等第三方依赖。
- `Vocabulary/`：ORB 词袋文件压缩包。
- `models/`：YOLO/ONNX 模型文件。
- `evaluation/`：轨迹评估脚本和参考数据。
- `picture/`：说明文档和实验图示相关图片。

## 未上传的大文件

GitHub 普通仓库不允许上传单个超过 100 MB 的文件，因此以下文件没有提交到仓库，但运行时可能需要：

| 文件 | 原始大小 | 目标路径 | 说明 |
| --- | ---: | --- | --- |
| `ORBvoc.txt` | 约 130 MB | `Vocabulary/ORBvoc.txt` | ORB-SLAM3 运行所需的 ORB 词袋文本文件。 |
| `libonnxruntime_providers_cuda.so` | 约 280 MB | `Thirdparty/onnxruntime-jetson/lib/libonnxruntime_providers_cuda.so` | Jetson/CUDA 版本 ONNX Runtime 的 CUDA Provider 动态库。 |

### 恢复 `Vocabulary/ORBvoc.txt`

仓库已经保留了压缩包 `Vocabulary/ORBvoc.txt.tar.gz`，克隆仓库后在项目根目录执行：

```bash
tar -xf Vocabulary/ORBvoc.txt.tar.gz -C Vocabulary
```

也可以直接运行 `./build.sh`，脚本会在构建过程中解压该文件。

本地原文件 SHA256：

```text
DA988C03A1EC9E3F3F50EF3741AC0CB024E39E8F3E86155A21FCB4A31B153806
```

压缩包 `Vocabulary/ORBvoc.txt.tar.gz` 的 SHA256：

```text
24F353B3276EC3A8E4EA9F8CD329494BAAD9A7413B584C73E8B32236C4F499D2
```

### 恢复 `libonnxruntime_providers_cuda.so`

该文件与设备架构、CUDA 版本、ONNX Runtime 版本强相关，仓库中没有直接上传。获取方式有两种：

1. 从当前项目交付包或原开发环境复制该文件到：

```text
Thirdparty/onnxruntime-jetson/lib/libonnxruntime_providers_cuda.so
```

2. 在目标 Jetson/CUDA 环境中安装或编译匹配版本的 ONNX Runtime GPU/Jetson 包，然后把生成的 `libonnxruntime_providers_cuda.so` 放到上述路径。

本项目当前同目录下保留的 ONNX Runtime 主库版本文件为：

```text
Thirdparty/onnxruntime-jetson/lib/libonnxruntime.so.1.17.3
```

因此重新获取 CUDA Provider 时，建议优先匹配 ONNX Runtime `1.17.3` 及目标设备的 CUDA/cuDNN 环境。

本地原文件 SHA256：

```text
0E927B796BB7FDC95C6DB9C553F6959FD3A175BF58B0D63B07C79F32C10B3780
```

## 构建

在 Linux/Jetson 环境中执行：

```bash
chmod +x build.sh
./build.sh
```

手动构建示例：

```bash
mkdir -p build
cd build
cmake -DCMAKE_BUILD_TYPE=Release ..
make rgbd_tum -j4
```

## 运行 TUM RGB-D

以下命令以 TUM RGB-D 数据集为例。请先准备好 TUM RGB-D 数据集，例如 `rgbd_dataset_freiburg1_xyz`、`rgbd_dataset_freiburg1_desk`、`rgbd_dataset_freiburg2_xyz` 或 `rgbd_dataset_freiburg3_office`。

1. 恢复 ORB 词袋文件：

```bash
tar -xf Vocabulary/ORBvoc.txt.tar.gz -C Vocabulary
```

2. 编译 `rgbd_tum`：

```bash
chmod +x build.sh
./build.sh
```

编译完成后，可执行文件位于：

```text
Examples/RGB-D/rgbd_tum
```

3. 按数据集选择配置文件和关联文件：

| 数据集示例 | 配置文件 | 关联文件 |
| --- | --- | --- |
| `rgbd_dataset_freiburg1_xyz` | `Examples/RGB-D/TUM1.yaml` | `Examples/RGB-D/associations/fr1_xyz.txt` |
| `rgbd_dataset_freiburg1_desk` | `Examples/RGB-D/TUM1.yaml` | `Examples/RGB-D/associations/fr1_desk.txt` |
| `rgbd_dataset_freiburg1_room` | `Examples/RGB-D/TUM1.yaml` | `Examples/RGB-D/associations/fr1_room.txt` |
| `rgbd_dataset_freiburg2_xyz` | `Examples/RGB-D/TUM2.yaml` | `Examples/RGB-D/associations/fr2_xyz.txt` |
| `rgbd_dataset_freiburg3_office` | `Examples/RGB-D/TUM3.yaml` | `Examples/RGB-D/associations/fr3_office.txt` |

4. 运行示例：

```bash
./Examples/RGB-D/rgbd_tum Vocabulary/ORBvoc.txt Examples/RGB-D/TUM1.yaml /path/to/rgbd_dataset_freiburg1_xyz Examples/RGB-D/associations/fr1_xyz.txt
```

如果使用其他序列，请把 `/path/to/rgbd_dataset_freiburg1_xyz` 替换为本地数据集目录，并同步替换对应的 `TUM*.yaml` 和 `associations/*.txt`。

5. 运行结束后，程序会在项目目录生成轨迹结果文件，常见输出包括：

```text
CameraTrajectory.txt
KeyFrameTrajectory.txt
```

## 注意事项

- 克隆仓库后，先恢复未上传的大文件，再构建和运行。
- 如果目标设备不是 Jetson，可能需要调整 `CMakeLists.txt` 中的 ONNX Runtime 路径。
- `Vocabulary/ORBvoc.txt`、ONNX Runtime CUDA 动态库、编译产物和运行结果文件都应保持在 `.gitignore` 中，不建议直接提交到 GitHub 普通仓库。
