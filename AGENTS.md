# Repository Guidelines

## Project Structure & Module Organization
- `src/` and `include/` hold the core C++ implementation and headers (ORB-SLAM3 core plus YOLOv8-Seg integration).
- `Examples/` contains runnable entry points and dataset configs (e.g., `Examples/RGB-D/rgbd_tum.cc`).
- `Vocabulary/` stores the ORB vocabulary archive used at runtime.
- `Thirdparty/` vendors dependencies (DBoW2, g2o, Sophus, onnxruntime).
- `models/` contains YOLO/ONNX assets; `evaluation/` holds scripts/results; `Examples_old/` is legacy.

## Build, Test, and Development Commands
- `./build.sh` builds third-party libs, unpacks the vocabulary, and builds the `rgbd_tum` target in `build/`.
- Manual build (equivalent):
  - `mkdir build && cd build && cmake -DCMAKE_BUILD_TYPE=Release .. && make rgbd_tum -j4`
- Run (TUM RGB-D):
  - `./Examples/RGB-D/rgbd_tum Vocabulary/ORBvoc.txt Examples/RGB-D/TUMX.yaml PATH_TO_SEQUENCE ASSOCIATIONS_FILE`

## Coding Style & Naming Conventions
- Language: C++14 (see `CMakeLists.txt`).
- Follow existing ORB-SLAM3 conventions: class names in `CamelCase`, methods in `CamelCase`, and files in `.cc`/`.h`.
- No repository-wide formatter is configured; keep changes consistent with nearby code.

## Testing Guidelines
- There are no first-party tests in this repository. Third-party libs may include their own tests under `Thirdparty/`.
- If adding new functionality, include a minimal reproduction path (example config or dataset command) in your PR description.

## Commit & Pull Request Guidelines
- Recent commit messages are short and direct (e.g., "Update README.md", "Fix #8: ..."). Use concise, imperative summaries.
- PRs should include: purpose, build/run steps, and any dataset or model assumptions. Add screenshots or short clips for visual SLAM changes.

## Configuration & Assets
- Update `CMakeLists.txt` paths if your ONNX Runtime install differs from `Thirdparty/onnxruntime-*`.
- Keep large binary assets (vocab, models) in their existing directories and avoid duplicating them in `src/`.
