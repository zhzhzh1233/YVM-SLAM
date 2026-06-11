from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess, OpaqueFunction
from launch.substitutions import LaunchConfiguration


def launch_setup(context, *_args, **_kwargs):
    vocab = LaunchConfiguration("vocab").perform(context)
    settings = LaunchConfiguration("settings").perform(context)
    sequence = LaunchConfiguration("sequence").perform(context)
    associations = LaunchConfiguration("associations").perform(context)
    venv = LaunchConfiguration("venv").perform(context)
    api_key = LaunchConfiguration("api_key").perform(context)
    model_path = LaunchConfiguration("model_path").perform(context)

    rgbd_cmd = (
        "/home/zh/workspaces/YVM-SLAM/Examples/RGB-D/rgbd_tum "
        f"{vocab} {settings} {sequence} {associations} --ros"
    )

    yolo_cmd = (
        f"source {venv}/bin/activate && export PYTHONNOUSERSITE=1 && "
        "ULTRALYTICS_AUTOUPDATE=0 python3 "
        "/home/zh/workspaces/YVM-SLAM/Examples/ROS2/yolo_world_mask_node.py "
        "--ros-args "
        f"-p model_path:={model_path} "
        "-p device:=cuda:0 -p imgsz:=640 -p half:=false "
        "-p image_topic:=/color/image "
        "-p mask_topic:=/dynamic_mask "
        "-p detection_topic:=/dynamic_detections "
        "-p clean_image_topic:=/yolo/clean_image "
        "-p prompt_topic:=/yolo_world/prompts "
        "-p vlm_topic:=/vlm/prompts_json "
        "-p use_default_prompts:=false"
    )

    vlm_cmd = (
        f"source {venv}/bin/activate && export PYTHONNOUSERSITE=1 && "
        "unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy; "
        "python3 /home/zh/workspaces/YVM-SLAM/Examples/ROS2/vlm_supervisor_node.py "
        "--ros-args -p auto_analyze:=false -p require_user_query:=true"
    )
    if api_key:
        vlm_cmd += f" --ros-args -p api_key:={api_key}"

    ui_cmd = (
        f"source {venv}/bin/activate && export PYTHONNOUSERSITE=1 && "
        "python3 /home/zh/workspaces/YVM-SLAM/Examples/ROS2/vlm_web_ui.py"
    )

    return [
        ExecuteProcess(cmd=["bash", "-lc", rgbd_cmd], output="screen"),
        ExecuteProcess(cmd=["bash", "-lc", yolo_cmd], output="screen"),
        ExecuteProcess(cmd=["bash", "-lc", vlm_cmd], output="screen"),
        ExecuteProcess(cmd=["bash", "-lc", ui_cmd], output="screen"),
        ExecuteProcess(
            cmd=[
                "bash",
                "-lc",
                "ros2 run rtabmap_slam rtabmap --ros-args "
                "--params-file /home/zh/workspaces/YVM-SLAM/Examples/ROS2/rtabmap_clean.yaml "
                "-r rgb/image:=/yolo/clean_image "
                "-r depth/image:=/depth/image "
                "-r rgb/camera_info:=/color/camera_info "
                "-r odom:=/odom",
            ],
            output="screen",
        ),
        ExecuteProcess(
            cmd=[
                "bash",
                "-lc",
                "ros2 run rtabmap_viz rtabmap_viz --ros-args "
                "-p subscribe_depth:=true "
                "-p subscribe_odom:=true "
                "-p approx_sync:=true "
                "-p topic_queue_size:=30 "
                "-p sync_queue_size:=30 "
                "-r rgb/image:=/yolo/clean_image "
                "-r depth/image:=/depth/image "
                "-r rgb/camera_info:=/color/camera_info "
                "-r odom:=/odom",
            ],
            output="screen",
        ),
    ]


def generate_launch_description():
    return LaunchDescription(
        [
            DeclareLaunchArgument("vocab"),
            DeclareLaunchArgument("settings"),
            DeclareLaunchArgument("sequence"),
            DeclareLaunchArgument("associations"),
            DeclareLaunchArgument("venv", default_value="~/venv_yolo"),
            DeclareLaunchArgument("api_key", default_value=""),
            DeclareLaunchArgument(
                "model_path",
                default_value="/home/zh/workspaces/YVM-SLAM/models/yolov8s-worldv2.pt",
            ),
            OpaqueFunction(function=launch_setup),
        ]
    )
