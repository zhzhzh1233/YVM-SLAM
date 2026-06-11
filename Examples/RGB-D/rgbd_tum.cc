/**
* This file is part of ORB-SLAM3
*
* Copyright (C) 2017-2021 Carlos Campos, Richard Elvira, Juan J. Gómez Rodríguez, José M.M. Montiel and Juan D. Tardós, University of Zaragoza.
* Copyright (C) 2014-2016 Raúl Mur-Artal, José M.M. Montiel and Juan D. Tardós, University of Zaragoza.
*
* ORB-SLAM3 is free software: you can redistribute it and/or modify it under the terms of the GNU General Public
* License as published by the Free Software Foundation, either version 3 of the License, or
* (at your option) any later version.
*
* ORB-SLAM3 is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even
* the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
* GNU General Public License for more details.
*
* You should have received a copy of the GNU General Public License along with ORB-SLAM3.
* If not, see <http://www.gnu.org/licenses/>.
*/

#include<iostream>
#include<algorithm>
#include<fstream>
#include<chrono>
#include<vector>
#include<atomic>
#include<csignal>
#include<mutex>

#include<opencv2/core/core.hpp>
#include<opencv2/imgcodecs.hpp>

#include<System.h>

#ifdef USE_ROS2
#include<rclcpp/rclcpp.hpp>
#include<sensor_msgs/msg/image.hpp>
#include<sensor_msgs/msg/camera_info.hpp>
#include<nav_msgs/msg/odometry.hpp>
#include<vision_msgs/msg/detection2_d_array.hpp>
#include<std_msgs/msg/string.hpp>
#include<geometry_msgs/msg/transform_stamped.hpp>
#include<tf2/LinearMath/Quaternion.h>
#include<tf2_ros/transform_broadcaster.h>
#endif

using namespace std;

namespace {
std::atomic<bool> g_request_shutdown{false};
void HandleSigint(int)
{
    g_request_shutdown.store(true, std::memory_order_relaxed);
}

#ifdef USE_ROS2
bool DecodeMaskImage(const sensor_msgs::msg::Image &msg, cv::Mat &out)
{
    if (msg.data.empty() || msg.height == 0 || msg.width == 0)
        return false;

    if (msg.encoding == "mono8" || msg.encoding == "8UC1")
    {
        cv::Mat view(msg.height, msg.width, CV_8UC1,
                     const_cast<unsigned char *>(msg.data.data()), msg.step);
        out = view.clone();
        return true;
    }

    if (msg.encoding == "bgr8" || msg.encoding == "rgb8")
    {
        cv::Mat view(msg.height, msg.width, CV_8UC3,
                     const_cast<unsigned char *>(msg.data.data()), msg.step);
        cv::cvtColor(view, out, msg.encoding == "bgr8" ? cv::COLOR_BGR2GRAY : cv::COLOR_RGB2GRAY);
        return true;
    }

    if (msg.encoding == "bgra8" || msg.encoding == "rgba8")
    {
        cv::Mat view(msg.height, msg.width, CV_8UC4,
                     const_cast<unsigned char *>(msg.data.data()), msg.step);
        cv::cvtColor(view, out, msg.encoding == "bgra8" ? cv::COLOR_BGRA2GRAY : cv::COLOR_RGBA2GRAY);
        return true;
    }

    return false;
}

std::string TrimToken(const std::string &token)
{
    size_t start = token.find_first_not_of(" \t\r\n\"'");
    if (start == std::string::npos)
        return std::string();
    size_t end = token.find_last_not_of(" \t\r\n\"'");
    return token.substr(start, end - start + 1);
}

std::vector<std::string> ParsePromptList(const std::string &data)
{
    std::string s = data;
    if (s.empty())
        return {};
    if (s.front() == '[' && s.back() == ']')
        s = s.substr(1, s.size() - 2);
    std::vector<std::string> result;
    std::stringstream ss(s);
    std::string item;
    while (std::getline(ss, item, ','))
    {
        std::string token = TrimToken(item);
        if (!token.empty())
            result.push_back(token);
    }
    return result;
}
#endif
}  // namespace

void LoadImages(const string &strAssociationFilename, vector<string> &vstrImageFilenamesRGB,
                vector<string> &vstrImageFilenamesD, vector<double> &vTimestamps);

int main(int argc, char **argv)
{
    std::signal(SIGINT, HandleSigint);
    bool enable_ros = false;
    vector<string> args;
    args.reserve(static_cast<size_t>(argc));
    for (int i = 1; i < argc; ++i)
    {
        string arg = argv[i];
        if (arg == "--ros")
            enable_ros = true;
        else
            args.push_back(arg);
    }

    if(args.size() != 4)
    {
        cerr << endl << "Usage: ./rgbd_tum path_to_vocabulary path_to_settings path_to_sequence path_to_association [--ros]" << endl;
        return 1;
    }

    // Retrieve paths to images
    vector<string> vstrImageFilenamesRGB;
    vector<string> vstrImageFilenamesD;
    vector<double> vTimestamps;
    string strAssociationFilename = args[3];
    LoadImages(strAssociationFilename, vstrImageFilenamesRGB, vstrImageFilenamesD, vTimestamps);

    // Check consistency in the number of images and depthmaps
    int nImages = vstrImageFilenamesRGB.size();
    if(vstrImageFilenamesRGB.empty())
    {
        cerr << endl << "No images found in provided path." << endl;
        return 1;
    }
    else if(vstrImageFilenamesD.size()!=vstrImageFilenamesRGB.size())
    {
        cerr << endl << "Different number of images for rgb and depth." << endl;
        return 1;
    }

    // Create SLAM system. It initializes all system threads and gets ready to process frames.
    ORB_SLAM3::System SLAM(args[0],args[1],ORB_SLAM3::System::RGBD,true);
    float imageScale = SLAM.GetImageScale();

    float depth_factor = 1.0f;
    float fx = ORB_SLAM3::Frame::fx;
    float fy = ORB_SLAM3::Frame::fy;
    float cx = ORB_SLAM3::Frame::cx;
    float cy = ORB_SLAM3::Frame::cy;
    {
        cv::FileStorage fsSettings(args[1], cv::FileStorage::READ);
        if(fsSettings.isOpened())
        {
            if(!fsSettings["RGBD.DepthMapFactor"].empty())
                depth_factor = static_cast<float>(fsSettings["RGBD.DepthMapFactor"]);
            if(!fsSettings["Camera1.fx"].empty()) fx = static_cast<float>(fsSettings["Camera1.fx"]);
            if(!fsSettings["Camera1.fy"].empty()) fy = static_cast<float>(fsSettings["Camera1.fy"]);
            if(!fsSettings["Camera1.cx"].empty()) cx = static_cast<float>(fsSettings["Camera1.cx"]);
            if(!fsSettings["Camera1.cy"].empty()) cy = static_cast<float>(fsSettings["Camera1.cy"]);
        }
    }

#ifdef USE_ROS2
    std::shared_ptr<rclcpp::Node> ros_node;
    rclcpp::Publisher<sensor_msgs::msg::Image>::SharedPtr pub_color;
    rclcpp::Publisher<sensor_msgs::msg::Image>::SharedPtr pub_depth;
    rclcpp::Publisher<sensor_msgs::msg::CameraInfo>::SharedPtr pub_color_info;
    rclcpp::Publisher<sensor_msgs::msg::CameraInfo>::SharedPtr pub_depth_info;
    rclcpp::Publisher<nav_msgs::msg::Odometry>::SharedPtr pub_odom;
    std::shared_ptr<tf2_ros::TransformBroadcaster> tf_broadcaster;
    std::unique_ptr<rclcpp::executors::SingleThreadedExecutor> ros_exec;
    rclcpp::Subscription<sensor_msgs::msg::Image>::SharedPtr sub_dynamic_mask;
    rclcpp::Subscription<vision_msgs::msg::Detection2DArray>::SharedPtr sub_detections;
    rclcpp::Subscription<std_msgs::msg::String>::SharedPtr sub_active_prompts;
    std::mutex mask_mutex;
    cv::Mat latest_mask;
    bool has_mask = false;
    std::mutex detections_mutex;
    std::map<std::string, std::vector<cv::Rect2i>> latest_detections;
    bool has_detections = false;
    bool has_pending_msgs = false;
    sensor_msgs::msg::Image pending_color_msg;
    sensor_msgs::msg::Image pending_depth_msg;
    sensor_msgs::msg::CameraInfo pending_color_info;
    sensor_msgs::msg::CameraInfo pending_depth_info;

    if(enable_ros)
    {
        int ros_argc = 1;
        char *ros_argv[1] = {argv[0]};
        rclcpp::init(ros_argc, ros_argv);
        ros_node = std::make_shared<rclcpp::Node>("orbslam_rgbd_publisher");
        pub_color = ros_node->create_publisher<sensor_msgs::msg::Image>("/color/image", 10);
        pub_depth = ros_node->create_publisher<sensor_msgs::msg::Image>("/depth/image", 10);
        pub_color_info = ros_node->create_publisher<sensor_msgs::msg::CameraInfo>("/color/camera_info", 10);
        pub_depth_info = ros_node->create_publisher<sensor_msgs::msg::CameraInfo>("/depth/camera_info", 10);
        pub_odom = ros_node->create_publisher<nav_msgs::msg::Odometry>("/odom", 10);
        tf_broadcaster = std::make_shared<tf2_ros::TransformBroadcaster>(ros_node);
        sub_dynamic_mask = ros_node->create_subscription<sensor_msgs::msg::Image>(
            "/dynamic_mask", 10,
            [&](sensor_msgs::msg::Image::ConstSharedPtr msg)
            {
                cv::Mat mask;
                if (!DecodeMaskImage(*msg, mask))
                    return;
                std::lock_guard<std::mutex> lock(mask_mutex);
                latest_mask = mask;
                has_mask = true;
            });
        sub_detections = ros_node->create_subscription<vision_msgs::msg::Detection2DArray>(
            "/dynamic_detections", 10,
            [&](vision_msgs::msg::Detection2DArray::ConstSharedPtr msg)
            {
                std::map<std::string, std::vector<cv::Rect2i>> dets;
                for (const auto &det : msg->detections)
                {
                    if (det.results.empty())
                        continue;
                    const auto &hyp = det.results.front().hypothesis;
                    const std::string label = hyp.class_id.empty() ? "object" : hyp.class_id;
                    const float cx = det.bbox.center.position.x;
                    const float cy = det.bbox.center.position.y;
                    const float w = det.bbox.size_x;
                    const float h = det.bbox.size_y;
                    const int x = static_cast<int>(cx - 0.5f * w);
                    const int y = static_cast<int>(cy - 0.5f * h);
                    const int width = static_cast<int>(w);
                    const int height = static_cast<int>(h);
                    if (width <= 0 || height <= 0)
                        continue;
                    dets[label].push_back(cv::Rect2i(x, y, width, height));
                }
                std::lock_guard<std::mutex> lock(detections_mutex);
                latest_detections = std::move(dets);
                has_detections = true;
            });
        sub_active_prompts = ros_node->create_subscription<std_msgs::msg::String>(
            "/yolo_world/active_prompts", 10,
            [&](std_msgs::msg::String::ConstSharedPtr msg)
            {
                std::vector<std::string> prompts = ParsePromptList(msg->data);
                SLAM.SetActivePrompts(prompts);
            });
        ros_exec = std::make_unique<rclcpp::executors::SingleThreadedExecutor>();
        ros_exec->add_node(ros_node);
    }
#else
    if(enable_ros)
    {
        cerr << "ROS2 publishing requested but rgbd_tum was built without USE_ROS2." << endl;
        enable_ros = false;
    }
#endif

    // Vector for tracking time statistics
    vector<float> vTimesTrack;
    vTimesTrack.resize(nImages);

    cout << endl << "-------" << endl;
    cout << "Start processing sequence ..." << endl;
    cout << "Images in the sequence: " << nImages << endl << endl;

    // Main loop
    cv::Mat imRGB, imD;
    for(int ni=0; ni<nImages; ni++)
    {
        if(g_request_shutdown.load(std::memory_order_relaxed))
            break;
        // Read image and depthmap from file
        imRGB = cv::imread(args[2]+"/"+vstrImageFilenamesRGB[ni],cv::IMREAD_UNCHANGED);
        imD = cv::imread(args[2]+"/"+vstrImageFilenamesD[ni],cv::IMREAD_UNCHANGED);
        double tframe = vTimestamps[ni];

        if(imRGB.empty())
        {
            cerr << endl << "Failed to load image at: "
                 << args[2] << "/" << vstrImageFilenamesRGB[ni] << endl;
            return 1;
        }

        if(imageScale != 1.f)
        {
            int width = imRGB.cols * imageScale;
            int height = imRGB.rows * imageScale;
            cv::resize(imRGB, imRGB, cv::Size(width, height));
            if(!imD.empty())
                cv::resize(imD, imD, cv::Size(width, height), 0, 0, cv::INTER_NEAREST);
        }

#ifdef COMPILEDWITHC14
        std::chrono::steady_clock::time_point t1 = std::chrono::steady_clock::now();
#else
        std::chrono::steady_clock::time_point t1 = std::chrono::steady_clock::now();
#endif

        if (enable_ros)
        {
            cv::Mat mask;
            {
                std::lock_guard<std::mutex> lock(mask_mutex);
                if (!latest_mask.empty())
                    mask = latest_mask.clone();
            }
            if (!mask.empty())
            {
                if (mask.size() != imRGB.size())
                    cv::resize(mask, mask, imRGB.size(), 0, 0, cv::INTER_NEAREST);
                SLAM.SetExternalMask(mask);
            }

            std::map<std::string, std::vector<cv::Rect2i>> dets;
            {
                std::lock_guard<std::mutex> lock(detections_mutex);
                if (!latest_detections.empty())
                    dets = latest_detections;
            }
            if (!dets.empty())
                SLAM.SetExternalDetections(dets);
        }

        // Pass the image to the SLAM system
        Sophus::SE3f Tcw = SLAM.TrackRGBD(imRGB,imD,tframe);

#ifdef USE_ROS2
        if(enable_ros)
        {
            const rclcpp::Time stamp = ros_node->get_clock()->now();
            const std::string frame_id = "base_link";
            float fx_pub = fx;
            float fy_pub = fy;
            float cx_pub = cx;
            float cy_pub = cy;
            if(imageScale != 1.f)
            {
                fx_pub *= imageScale;
                fy_pub *= imageScale;
                cx_pub *= imageScale;
                cy_pub *= imageScale;
            }

            Sophus::SE3f Twc = Tcw.inverse();
            Eigen::Matrix3f Rwc = Twc.rotationMatrix();
            Eigen::Quaternionf q(Rwc);

            nav_msgs::msg::Odometry odom_msg;
            odom_msg.header.stamp = stamp;
            odom_msg.header.frame_id = "odom";
            odom_msg.child_frame_id = frame_id;
            odom_msg.pose.pose.position.x = Twc.translation().x();
            odom_msg.pose.pose.position.y = Twc.translation().y();
            odom_msg.pose.pose.position.z = Twc.translation().z();
            odom_msg.pose.pose.orientation.x = q.x();
            odom_msg.pose.pose.orientation.y = q.y();
            odom_msg.pose.pose.orientation.z = q.z();
            odom_msg.pose.pose.orientation.w = q.w();
            pub_odom->publish(odom_msg);

            geometry_msgs::msg::TransformStamped tf_msg;
            tf_msg.header.stamp = stamp;
            tf_msg.header.frame_id = "odom";
            tf_msg.child_frame_id = frame_id;
            tf_msg.transform.translation.x = Twc.translation().x();
            tf_msg.transform.translation.y = Twc.translation().y();
            tf_msg.transform.translation.z = Twc.translation().z();
            tf_msg.transform.rotation.x = q.x();
            tf_msg.transform.rotation.y = q.y();
            tf_msg.transform.rotation.z = q.z();
            tf_msg.transform.rotation.w = q.w();
            tf_broadcaster->sendTransform(tf_msg);

            sensor_msgs::msg::Image color_msg;
            color_msg.header.stamp = stamp;
            color_msg.header.frame_id = frame_id;
            color_msg.height = static_cast<uint32_t>(imRGB.rows);
            color_msg.width = static_cast<uint32_t>(imRGB.cols);
            color_msg.encoding = "bgr8";
            color_msg.step = static_cast<sensor_msgs::msg::Image::_step_type>(imRGB.step);
            color_msg.data.assign(imRGB.data, imRGB.data + imRGB.step * imRGB.rows);
            pub_color->publish(color_msg);

            cv::Mat depth_float;
            if(depth_factor > 0.0f && depth_factor != 1.0f)
                imD.convertTo(depth_float, CV_32F, 1.0f / depth_factor);
            else if(imD.type() == CV_32F)
                depth_float = imD;
            else
                imD.convertTo(depth_float, CV_32F);

            sensor_msgs::msg::Image depth_msg;
            depth_msg.header.stamp = stamp;
            depth_msg.header.frame_id = frame_id;
            depth_msg.height = static_cast<uint32_t>(depth_float.rows);
            depth_msg.width = static_cast<uint32_t>(depth_float.cols);
            depth_msg.encoding = "32FC1";
            depth_msg.step = static_cast<sensor_msgs::msg::Image::_step_type>(depth_float.step);
            depth_msg.data.assign(depth_float.data, depth_float.data + depth_float.step * depth_float.rows);
            pub_depth->publish(depth_msg);

            sensor_msgs::msg::CameraInfo color_info;
            color_info.header.stamp = stamp;
            color_info.header.frame_id = frame_id;
            color_info.height = static_cast<uint32_t>(imRGB.rows);
            color_info.width = static_cast<uint32_t>(imRGB.cols);
            color_info.distortion_model = "plumb_bob";
            color_info.d = {0.0, 0.0, 0.0, 0.0, 0.0};
            color_info.k = {fx_pub, 0.0, cx_pub,
                            0.0, fy_pub, cy_pub,
                            0.0, 0.0, 1.0};
            color_info.r = {1.0, 0.0, 0.0,
                            0.0, 1.0, 0.0,
                            0.0, 0.0, 1.0};
            color_info.p = {fx_pub, 0.0, cx_pub, 0.0,
                            0.0, fy_pub, cy_pub, 0.0,
                            0.0, 0.0, 1.0, 0.0};
            pub_color_info->publish(color_info);

            sensor_msgs::msg::CameraInfo depth_info = color_info;
            depth_info.height = static_cast<uint32_t>(depth_float.rows);
            depth_info.width = static_cast<uint32_t>(depth_float.cols);
            pub_depth_info->publish(depth_info);

            if (ros_exec)
                ros_exec->spin_some();
        }
#endif

#ifdef COMPILEDWITHC14
        std::chrono::steady_clock::time_point t2 = std::chrono::steady_clock::now();
#else
        std::chrono::steady_clock::time_point t2 = std::chrono::steady_clock::now();
#endif

        double ttrack= std::chrono::duration_cast<std::chrono::duration<double> >(t2 - t1).count();

        vTimesTrack[ni]=ttrack;

        // Wait to load the next frame
        double T=0;
        if(ni<nImages-1)
            T = vTimestamps[ni+1]-tframe;
        else if(ni>0)
            T = tframe-vTimestamps[ni-1];

        if(ttrack<T)
            usleep((T-ttrack)*10);
    }

    // Stop all threads
    SLAM.Shutdown();

    // Tracking time statistics
    sort(vTimesTrack.begin(),vTimesTrack.end());
    float totaltime = 0;
    for(int ni=0; ni<nImages; ni++)
    {
        totaltime+=vTimesTrack[ni];
    }
    cout << "-------" << endl << endl;
    cout << "median tracking time: " << vTimesTrack[nImages/2] << endl;
    cout << "mean tracking time: " << totaltime/nImages << endl;

    std:: string folderPath = args[2];
    std:: string trajectoryPath = folderPath + "/Results" + "/CameraTrajectory.txt";
    std:: string keyFrameTrajectoryPath = folderPath + "/Results" "/KeyFrameTrajectory.txt";

    // Save camera trajectory
    SLAM.SaveTrajectoryTUM(trajectoryPath);
    SLAM.SaveKeyFrameTrajectoryTUM(keyFrameTrajectoryPath);   

#ifdef USE_ROS2
    if(enable_ros)
    {
        ros_exec.reset();
        rclcpp::shutdown();
    }
#endif

    return 0;
}

void LoadImages(const string &strAssociationFilename, vector<string> &vstrImageFilenamesRGB,
                vector<string> &vstrImageFilenamesD, vector<double> &vTimestamps)
{
    ifstream fAssociation;
    fAssociation.open(strAssociationFilename.c_str());
    while(!fAssociation.eof())
    {
        string s;
        getline(fAssociation,s);
        if(!s.empty())
        {
            stringstream ss;
            ss << s;
            double t;
            string sRGB, sD;
            ss >> t;
            vTimestamps.push_back(t);
            ss >> sRGB;
            vstrImageFilenamesRGB.push_back(sRGB);
            ss >> t;
            ss >> sD;
            vstrImageFilenamesD.push_back(sD);

        }
    }
}
