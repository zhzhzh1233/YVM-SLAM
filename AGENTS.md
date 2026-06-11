# 仓库协作说明

## 项目结构

- `src/` 和 `include/` 保存核心 C++ 实现与头文件，主要包含 ORB-SLAM3 核心逻辑以及 YOLOv8/ONNX Runtime 相关集成。
- `Examples/` 保存可运行示例、数据集配置和相机配置。
- `Examples_old/` 保存旧版配置格式示例，仅用于兼容或参考。
- `Vocabulary/` 保存 ORB 词袋压缩包，运行前需要解压出 `ORBvoc.txt`。
- `Thirdparty/` 保存 DBoW2、g2o、Sophus、ONNX Runtime 等第三方依赖。
- `models/` 保存 YOLO/ONNX 模型文件。
- `evaluation/` 保存轨迹评估脚本和参考数据。

## 构建与运行

构建命令：

```bash
chmod +x build.sh
./build.sh
```

等价的手动构建命令：

```bash
mkdir -p build
cd build
cmake -DCMAKE_BUILD_TYPE=Release ..
make rgbd_tum -j4
```

TUM RGB-D 示例运行命令：

```bash
./Examples/RGB-D/rgbd_tum Vocabulary/ORBvoc.txt Examples/RGB-D/TUMX.yaml PATH_TO_SEQUENCE ASSOCIATIONS_FILE
```

## 代码风格

- 项目使用 C++14，具体配置见 `CMakeLists.txt`。
- 保持 ORB-SLAM3 原有命名风格：类名使用 `CamelCase`，方法名使用 `CamelCase`，源码文件主要使用 `.cc`、`.cpp`、`.h`。
- 仓库没有统一格式化工具，修改代码时应尽量保持与周围代码一致。

## 测试建议

- 当前仓库没有统一的一方测试套件。
- 第三方库自身测试位于 `Thirdparty/` 下，通常不作为本项目日常验证入口。
- 添加新功能时，应在说明中写清楚可复现实验命令、数据集路径假设和模型文件要求。

## 提交说明

- 提交信息建议简短明确，例如 `更新中文说明文档`、`修复 RGB-D 运行配置`。
- 合并请求或交付说明中应包含：修改目的、构建方式、运行方式、数据集和模型依赖。

## 大文件说明

仓库未直接上传超过 GitHub 普通限制的大文件。缺失文件、恢复方式和校验值见根目录 `README.md` 的“未上传的大文件”章节。
