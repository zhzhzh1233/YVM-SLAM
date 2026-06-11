# 已知依赖说明

本文列出 ORB-SLAM3 及本项目中包含或链接的第三方代码与库。以下内容主要用于说明代码来源和许可证背景。

## `src/` 与 `include/` 中的第三方来源

- `ORBextractor.cc`：基于 OpenCV 库中的 `orb.cpp` 修改，原始代码使用 BSD 许可证。
- `PnPsolver.h`、`PnPsolver.cc`：基于 Vincent Lepetit 的 `epnp.h` 和 `epnp.cc` 修改。相关实现也可见于 BSD 许可证的计算机视觉库，例如 [OpenCV](https://github.com/Itseez/opencv/blob/master/modules/calib3d/src/epnp.cpp) 和 [OpenGV](https://github.com/laurentkneip/opengv/blob/master/src/absolute_pose/modules/Epnp.cpp)。原始代码使用 FreeBSD 许可证。
- `MLPnPsolver.h`、`MLPnPsolver.cc`：基于 Steffen Urban 的 [MLPnP 实现](https://github.com/urbste/opengv) 修改，原始代码使用 BSD 许可证。
- `ORBmatcher.cc` 中的 `ORBmatcher::DescriptorDistance`：代码来源为位运算统计方法说明页 `http://graphics.stanford.edu/~seander/bithacks.html#CountBitsSetParallel`，该代码属于公有领域。

## `Thirdparty/` 中的第三方代码

- `DBoW2/`：基于 [DBoW2](https://github.com/dorian3d/DBoW2) 和 [DLib](https://github.com/dorian3d/DLib) 修改，包含文件使用 BSD 许可证。
- `g2o/`：基于 [g2o](https://github.com/RainerKuemmerle/g2o) 修改，包含文件使用 BSD 许可证。
- `Sophus/`：基于 [Sophus](https://github.com/strasdat/Sophus) 修改，使用 [MIT 许可证](https://en.wikipedia.org/wiki/MIT_License)。
- `onnxruntime/`、`onnxruntime-jetson/`：用于 ONNX 模型推理。不同平台的动态库可能存在差异，缺失的大型 CUDA Provider 动态库说明见 `README.md`。

## 外部库依赖

- Pangolin：用于可视化和用户界面，使用 MIT 许可证。
- OpenCV：使用 BSD 许可证。
- Eigen3：3.1.1 之后版本使用 MPL2，早期版本使用 LGPLv3。
- ROS：可选依赖，仅在构建 `Examples/ROS` 时需要。相关包包括 `roscpp`、`tf`、`sensor_msgs`、`image_transport`、`cv_bridge`，均为 BSD 许可证。

## 大文件依赖

仓库没有直接上传以下超过 GitHub 普通限制的大文件：

- `Vocabulary/ORBvoc.txt`
- `Thirdparty/onnxruntime-jetson/lib/libonnxruntime_providers_cuda.so`

克隆仓库后的恢复方式见根目录 `README.md`。
